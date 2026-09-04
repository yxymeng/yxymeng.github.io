# -*- coding: utf-8 -*-
"""
Clash 通用规则合并脚本 V2

功能：
1. 按 merge_config.json 中的分类和 URL 顺序读取规则。
2. 每个 include URL 可单独跳过指定规则类型。
3. 合并阶段保持原始先后顺序，只删除冗余规则，不重新按类型排序。
4. DOMAIN-KEYWORD 可覆盖相关 DOMAIN-SUFFIX / DOMAIN。
5. DOMAIN-SUFFIX 可覆盖更具体的 DOMAIN-SUFFIX / DOMAIN，但绝不自行推导不存在的父域规则。
6. DOMAIN 之间不做泛化优化，仅做完全相同字符串去重。
7. exclude 支持每个来源单独选择 exact / type 模式。
8. type 模式对三类域名规则做类型级覆盖，对 IP-CIDR、PROCESS-NAME 等其他类型只做完全匹配。
9. exclude 支持 @分类 引用本轮已经生成的分类结果，避免读取 GitHub 上一轮旧文件。
10. 所有远程源必须成功获取；失败会重试，最终失败则整个任务退出，不覆盖旧规则。
11. 输出文件带规则统计头；规则无变化时不更新 UPDATED，也不改写文件。
"""

import json
import logging
import os
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

CONFIG_FILE = Path("merge_config.json")
OUTPUT_DIR = Path("Ruleset") / "Merged"
AUTHOR = "yxymeng"
REPO = "https://github.com/yxymeng/yxymeng.github.io"
FETCH_TIMEOUT = 20
FETCH_RETRIES = 3
DOMAIN_TYPES = {"DOMAIN-KEYWORD", "DOMAIN-SUFFIX", "DOMAIN"}
STAT_ORDER = [
    "DOMAIN",
    "DOMAIN-KEYWORD",
    "DOMAIN-SUFFIX",
    "IP-CIDR",
    "IP-CIDR6",
    "PROCESS-NAME",
]
BEIJING_TZ = timezone(timedelta(hours=8))

# GitHub Actions 的 runner 默认使用 UTC。日志固定成 UTC，便于不同运行环境下统一排查。
logging.Formatter.converter = time.gmtime
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)sZ %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "yxymeng-clash-rule-merger-v2"})


def normalize_type(value):
    """统一规则类型写法；IP_CIDR 也会被识别为 IP-CIDR。"""
    return str(value).strip().upper().replace("_", "-")


def rule_type(line):
    """返回 Clash 规则类型；无逗号的异常/特殊行归为 OTHER。"""
    head, sep, _ = line.partition(",")
    return normalize_type(head) if sep else "OTHER"


def rule_value(line):
    """只取得规则第二字段，用于域名匹配；后续 no-resolve 等参数不会参与域名比较。"""
    parts = line.split(",", 2)
    return parts[1].strip() if len(parts) >= 2 else ""


def normalize_domain(value):
    """域名比较不区分大小写，并去除首尾多余的点。"""
    return value.strip().strip(".").lower()


def keyword_matches(domain, keywords):
    """模拟 DOMAIN-KEYWORD：关键词只要出现在目标域名字符串中即视为覆盖。"""
    domain = normalize_domain(domain)
    return bool(domain) and any(keyword and keyword in domain for keyword in keywords)


def suffix_matches(domain, suffixes):
    """严格按域名标签边界判断后缀，避免 notasdf.com 被 asdf.com 错误覆盖。"""
    domain = normalize_domain(domain)
    if not domain:
        return False
    if domain in suffixes:
        return True
    parts = domain.split(".")
    return any(".".join(parts[i:]) in suffixes for i in range(1, len(parts)))


def has_parent_suffix(domain, suffixes):
    """判断 DOMAIN-SUFFIX 是否存在更上级且明确出现在源规则中的父后缀。"""
    domain = normalize_domain(domain)
    parts = domain.split(".")
    return any(".".join(parts[i:]) in suffixes for i in range(1, len(parts)))


def clean_rules(text, source, skip_types=None):
    """过滤空行/注释，并仅针对当前来源跳过指定类型；不在这里改变规则顺序。"""
    skip_types = {normalize_type(item) for item in (skip_types or [])}
    rules = []
    skipped = Counter()
    ignored = 0
    raw_lines = text.splitlines()

    for raw in raw_lines:
        line = raw.strip().lstrip("\ufeff")
        if not line or line.startswith("#"):
            ignored += 1
            continue
        current_type = rule_type(line)
        if current_type in skip_types:
            skipped[current_type] += 1
            continue
        rules.append(line)

    skipped_text = ", ".join(f"{k}={v}" for k, v in sorted(skipped.items())) or "无"
    logging.info(
        "SOURCE %s | 原始行=%d | 空行/注释=%d | 按类型跳过=%s | 接收规则=%d",
        source,
        len(raw_lines),
        ignored,
        skipped_text,
        len(rules),
    )
    return rules


def fetch_remote(url):
    """下载远程规则。失败最多尝试 3 次；全部失败后抛错，禁止生成残缺输出。"""
    last_error = None
    for attempt in range(1, FETCH_RETRIES + 1):
        try:
            logging.info("DOWNLOAD %s | 第 %d/%d 次", url, attempt, FETCH_RETRIES)
            response = SESSION.get(url, timeout=FETCH_TIMEOUT)
            response.raise_for_status()
            return response.content.decode("utf-8-sig")
        except (requests.RequestException, UnicodeDecodeError) as exc:
            last_error = exc
            logging.warning("DOWNLOAD FAILED %s | %s", url, exc)
            if attempt < FETCH_RETRIES:
                time.sleep(2 ** (attempt - 1))
    raise RuntimeError(f"远程规则连续 {FETCH_RETRIES} 次获取失败：{url} | {last_error}")


def load_source(source, skip_types=None):
    """include/exclude 均可读取 HTTP(S) URL 或仓库内本地文本文件。"""
    if source.startswith(("https://", "http://")):
        text = fetch_remote(source)
    else:
        path = Path(source)
        if not path.is_file():
            raise FileNotFoundError(f"本地规则文件不存在：{source}")
        text = path.read_text(encoding="utf-8-sig")
    return clean_rules(text, source, skip_types)


def merge_rules(source_lists, category):
    """按全局原始顺序去重和优化；只删除冗余项，不重排剩余规则。"""
    raw_rules = [rule for source in source_lists for rule in source]
    raw_type_counts = Counter(rule_type(rule) for rule in raw_rules)

    # 第一阶段只做完全相同字符串去重，保留第一次出现的位置。
    unique_rules = []
    seen = set()
    exact_duplicates = 0
    for rule in raw_rules:
        if rule in seen:
            exact_duplicates += 1
            continue
        seen.add(rule)
        unique_rules.append(rule)

    # 全局建立 DOMAIN-KEYWORD 索引。关键词自身之间不做模糊合并，只做前面的精确去重。
    keywords = []
    keyword_seen = set()
    for rule in unique_rules:
        if rule_type(rule) == "DOMAIN-KEYWORD":
            keyword = normalize_domain(rule_value(rule))
            if keyword and keyword not in keyword_seen:
                keyword_seen.add(keyword)
                keywords.append(keyword)

    # 建立所有未被 KEYWORD 覆盖的 DOMAIN-SUFFIX，之后再找明确存在的父后缀。
    suffix_candidates = {
        normalize_domain(rule_value(rule))
        for rule in unique_rules
        if rule_type(rule) == "DOMAIN-SUFFIX"
        and normalize_domain(rule_value(rule))
        and not keyword_matches(rule_value(rule), keywords)
    }
    kept_suffixes = {
        suffix for suffix in suffix_candidates if not has_parent_suffix(suffix, suffix_candidates)
    }

    final = []
    removed = Counter()

    # 第二遍重新按原顺序扫描，因此最终文件仍保持 URL 顺序 + 每个文件内部原顺序。
    for rule in unique_rules:
        current_type = rule_type(rule)
        value = rule_value(rule)

        if current_type == "DOMAIN-SUFFIX":
            if keyword_matches(value, keywords):
                removed["KEYWORD→DOMAIN-SUFFIX"] += 1
                continue
            if normalize_domain(value) not in kept_suffixes:
                removed["SUFFIX→DOMAIN-SUFFIX"] += 1
                continue

        elif current_type == "DOMAIN":
            if keyword_matches(value, keywords):
                removed["KEYWORD→DOMAIN"] += 1
                continue
            if suffix_matches(value, kept_suffixes):
                removed["SUFFIX→DOMAIN"] += 1
                continue

        final.append(rule)

    logging.info(
        "MERGE [%s] | 输入=%d | 精确重复=%d | 去重后=%d | 最终=%d",
        category,
        len(raw_rules),
        exact_duplicates,
        len(unique_rules),
        len(final),
    )
    logging.info(
        "MERGE [%s] | KEYWORD覆盖SUFFIX=%d | SUFFIX父域覆盖SUFFIX=%d | KEYWORD覆盖DOMAIN=%d | SUFFIX覆盖DOMAIN=%d",
        category,
        removed["KEYWORD→DOMAIN-SUFFIX"],
        removed["SUFFIX→DOMAIN-SUFFIX"],
        removed["KEYWORD→DOMAIN"],
        removed["SUFFIX→DOMAIN"],
    )
    logging.info(
        "MERGE [%s] | 输入类型统计：%s",
        category,
        ", ".join(f"{k}={v}" for k, v in sorted(raw_type_counts.items())) or "无",
    )
    return final


def apply_exact_exclude(rules, exclude_rules, label):
    """exact：所有规则类型都只按完整字符串完全相同进行排除。"""
    exclude_set = set(exclude_rules)
    result = [rule for rule in rules if rule not in exclude_set]
    removed = len(rules) - len(result)
    logging.info("EXCLUDE %s | mode=exact | 删除=%d | 剩余=%d", label, removed, len(result))
    return result


def apply_type_exclude(rules, exclude_rules, label):
    """
    type：
    - DOMAIN-KEYWORD：只精确匹配相同关键词；
    - DOMAIN-SUFFIX：可被排除源 KEYWORD 或父/同级 SUFFIX 覆盖；
    - DOMAIN：可被排除源 KEYWORD、父/同级 SUFFIX 或相同 DOMAIN 覆盖；
    - 其他类型：IP-CIDR、IP-CIDR6、PROCESS-NAME、URL-REGEX 等仅完整字符串精确匹配。
    """
    ex_keywords = {
        normalize_domain(rule_value(rule))
        for rule in exclude_rules
        if rule_type(rule) == "DOMAIN-KEYWORD" and normalize_domain(rule_value(rule))
    }
    ex_suffixes = {
        normalize_domain(rule_value(rule))
        for rule in exclude_rules
        if rule_type(rule) == "DOMAIN-SUFFIX" and normalize_domain(rule_value(rule))
    }
    ex_domains = {
        normalize_domain(rule_value(rule))
        for rule in exclude_rules
        if rule_type(rule) == "DOMAIN" and normalize_domain(rule_value(rule))
    }
    ex_others = {rule for rule in exclude_rules if rule_type(rule) not in DOMAIN_TYPES}

    result = []
    removed = Counter()
    for rule in rules:
        current_type = rule_type(rule)
        value = rule_value(rule)
        normalized_value = normalize_domain(value)

        if current_type == "DOMAIN-KEYWORD":
            if normalized_value in ex_keywords:
                removed["DOMAIN-KEYWORD"] += 1
                continue

        elif current_type == "DOMAIN-SUFFIX":
            if keyword_matches(value, ex_keywords):
                removed["KEYWORD→DOMAIN-SUFFIX"] += 1
                continue
            if suffix_matches(value, ex_suffixes):
                removed["SUFFIX→DOMAIN-SUFFIX"] += 1
                continue

        elif current_type == "DOMAIN":
            if keyword_matches(value, ex_keywords):
                removed["KEYWORD→DOMAIN"] += 1
                continue
            if suffix_matches(value, ex_suffixes):
                removed["SUFFIX→DOMAIN"] += 1
                continue
            if normalized_value in ex_domains:
                removed["DOMAIN"] += 1
                continue

        elif rule in ex_others:
            removed["OTHER精确"] += 1
            continue

        result.append(rule)

    logging.info(
        "EXCLUDE %s | mode=type | 删除=%d | 剩余=%d | 明细=%s",
        label,
        sum(removed.values()),
        len(result),
        ", ".join(f"{k}={v}" for k, v in removed.items()) or "无",
    )
    return result


def apply_excludes(rules, exclude_config, generated, category):
    """按 JSON 中 exclude 的书写顺序逐个执行，每个来源拥有自己的 exact/type 模式。"""
    result = list(rules)
    for source, mode in exclude_config.items():
        mode = mode.lower()
        if source.startswith("@"):
            ref_name = source[1:]
            if ref_name not in generated:
                raise ValueError(
                    f"{category} 的 exclude 引用了 @{ref_name}，但该分类尚未生成；"
                    "请把被引用分类放到 merge_config.json 更前面。"
                )
            exclude_rules = generated[ref_name]
            logging.info(
                "EXCLUDE [%s] | 使用本轮内存结果 @%s | 规则=%d | mode=%s",
                category,
                ref_name,
                len(exclude_rules),
                mode,
            )
        else:
            exclude_rules = load_source(source)

        label = f"[{category}] {source}"
        if mode == "exact":
            result = apply_exact_exclude(result, exclude_rules, label)
        elif mode == "type":
            result = apply_type_exclude(result, exclude_rules, label)
        else:
            raise ValueError(f"未知 exclude 模式：{mode}（{source}）")
    return result


def validate_config(config):
    """在任何下载和写文件前完整校验配置，尽早暴露 JSON 写法问题。"""
    if not isinstance(config, dict) or not config:
        raise ValueError("merge_config.json 顶层必须是非空 JSON 对象。")

    previous_categories = set()
    for category, info in config.items():
        if not isinstance(category, str) or not category.strip():
            raise ValueError("分类名不能为空。")
        if category in {".", ".."} or "/" in category or "\\" in category:
            raise ValueError(f"分类名不能包含路径字符：{category}")
        if not isinstance(info, dict):
            raise ValueError(f"分类 {category} 的配置必须是 JSON 对象。")

        if "include" not in info or "exclude" not in info:
            raise ValueError(f"分类 {category} 必须同时包含 include 和 exclude。")
        if "exclude_mode" in info:
            raise ValueError(
                f"分类 {category} 仍在使用旧版 exclude_mode。V2 请把 exclude 写成 "
                '{"来源": "type/exact"}，让每个排除源单独指定模式。'
            )

        include = info["include"]
        exclude = info["exclude"]
        if not isinstance(include, dict) or not include:
            raise ValueError(f"分类 {category} 的 include 必须是非空 JSON 对象。")
        if not isinstance(exclude, dict):
            raise ValueError(f"分类 {category} 的 exclude 必须是 JSON 对象；无排除时写 {{}}。")

        for source, skip_types in include.items():
            if not isinstance(source, str) or not source.strip() or source.startswith("@"):
                raise ValueError(f"分类 {category} 的 include 来源无效：{source!r}")
            if not isinstance(skip_types, list) or not all(isinstance(x, str) for x in skip_types):
                raise ValueError(f"include 来源 {source} 的跳过类型必须写成字符串数组。")

        for source, mode in exclude.items():
            if not isinstance(source, str) or not source.strip():
                raise ValueError(f"分类 {category} 的 exclude 来源无效：{source!r}")
            if not isinstance(mode, str) or mode.lower() not in {"exact", "type"}:
                raise ValueError(f"exclude 来源 {source} 的模式只能是 exact 或 type。")
            if source.startswith("@") and source[1:] not in previous_categories:
                raise ValueError(
                    f"分类 {category} 引用了 {source}，V2 只允许引用前面已经定义的分类。"
                )

        previous_categories.add(category)


def beijing_now():
    """输出文件 UPDATED 使用北京时间，便于直接查看每天凌晨任务的更新时间。"""
    return datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")


def build_header(category, rules, updated):
    """按固定常用顺序输出统计；未知/其他规则类型会自动追加。"""
    stats = Counter(rule_type(rule) for rule in rules)
    ordered_types = [item for item in STAT_ORDER if stats.get(item)]
    ordered_types += sorted(item for item in stats if item not in STAT_ORDER)

    lines = [
        f"# NAME: {category}",
        f"# AUTHOR: {AUTHOR}",
        f"# REPO: {REPO}",
        f"# UPDATED: {updated}",
    ]
    lines.extend(f"# {item}: {stats[item]}" for item in ordered_types)
    lines.append(f"# TOTAL: {len(rules)}")
    return lines


def render_output(category, rules, updated):
    header = build_header(category, rules, updated)
    body = "\n".join(rules)
    return "\n".join(header) + "\n\n" + body + ("\n" if body else "")


def comparable_content(text):
    """比较时忽略 UPDATED 行；只有规则或其他头部真正变化才更新文件。"""
    return "\n".join(
        line for line in text.splitlines() if not line.startswith("# UPDATED:")
    ).rstrip() + "\n"


def write_if_changed(category, rules):
    """使用临时文件 + os.replace 原子替换；无实际变化时保持旧 UPDATED 不动。"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{category}.list"
    candidate = render_output(category, rules, beijing_now())

    if path.exists():
        old = path.read_text(encoding="utf-8-sig")
        if comparable_content(old) == comparable_content(candidate):
            logging.info("WRITE [%s] | 无规则变化，保留原文件和原 UPDATED", category)
            return False

    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(candidate, encoding="utf-8", newline="\n")
    os.replace(temp_path, path)
    logging.info("WRITE [%s] | 已更新 %s | TOTAL=%d", category, path, len(rules))
    return True


def log_final_stats(category, rules):
    stats = Counter(rule_type(rule) for rule in rules)
    logging.info(
        "FINAL [%s] | TOTAL=%d | %s",
        category,
        len(rules),
        ", ".join(f"{k}={v}" for k, v in sorted(stats.items())) or "无规则",
    )


def main():
    try:
        with CONFIG_FILE.open("r", encoding="utf-8-sig") as file:
            config = json.load(file)
        validate_config(config)

        # 所有分类先在内存中完成。只要任一下载/计算失败，就不会写任何输出文件。
        generated = {}
        for category, info in config.items():
            logging.info("=" * 72)
            logging.info("CATEGORY [%s] START", category)

            source_lists = []
            for source, skip_types in info["include"].items():
                source_lists.append(load_source(source, skip_types))

            merged = merge_rules(source_lists, category)
            final = apply_excludes(merged, info["exclude"], generated, category)
            generated[category] = final
            log_final_stats(category, final)
            logging.info("CATEGORY [%s] READY", category)

        changed = 0
        for category, rules in generated.items():
            changed += int(write_if_changed(category, rules))

        logging.info("=" * 72)
        logging.info("ALL DONE | 分类=%d | 实际更新文件=%d", len(generated), changed)

    except Exception as exc:
        logging.exception("FATAL | 本轮任务失败，未提交新的规则结果：%s", exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
