import os
import json
import requests
from datetime import datetime

# 定义输出目录，用于存放合并并排除后的规则文件
OUTPUT_DIR = os.path.join("Ruleset", "Merged")
# 如果目录不存在，则创建之
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 获取规则类型（例如 "DOMAIN-SUFFIX"、"IP-CIDR" 等）
def rule_type(line):
    return line.split(",", 1)[0] if "," in line else None

# 获取规则内容（逗号之后的部分，例如域名或 IP）
def rule_content(line):
    return line.split(",", 1)[1] if "," in line else line

# 从指定 URL 拉取规则列表，返回去除注释和空行后的规则行列表，并打印日志
def fetch_rules(url):
    try:
        print(f"[{datetime.now()}] Fetching rules from {url}")
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        # 过滤掉空行和注释行
        lines = [ln.strip() for ln in r.text.splitlines() if ln.strip() and not ln.startswith("#")]
        print(f"[{datetime.now()}] Retrieved {len(lines)} rules from {url}")
        return lines
    except Exception as e:
        print(f"[{datetime.now()}] Error fetching {url}: {e}")
        return []

# 合并多个来源的规则，保留顺序并进行 DOMAIN-KEYWORD、DOMAIN-SUFFIX、DOMAIN 优先级去重优化
def merge_rules(rules_list):
    seen = set()      # 已添加规则集合，用于去重
    final = []        # 最终合并后的规则列表

    # 1. 先处理 DOMAIN-KEYWORD，保证其优先级最高
    keywords = [r for rules in rules_list for r in rules if rule_type(r) == "DOMAIN-KEYWORD"]
    print(f"[{datetime.now()}] Merging DOMAIN-KEYWORD: {len(keywords)} found")
    for rule in keywords:
        if rule not in seen:
            seen.add(rule)
            final.append(rule)

    # 2. 再处理 DOMAIN-SUFFIX（跳过被关键词覆盖的）
    suffixes = [r for rules in rules_list for r in rules if rule_type(r) == "DOMAIN-SUFFIX"]
    print(f"[{datetime.now()}] Merging DOMAIN-SUFFIX: {len(suffixes)} found")
    for rule in suffixes:
        content = rule_content(rule)
        # 若域名中包含任何关键词，则跳过
        if any(rule_content(kw) in content for kw in keywords):
            continue
        if rule not in seen:
            seen.add(rule)
            final.append(rule)

    # 3. 再处理 DOMAIN（跳过被关键词或后缀覆盖的）
    domains = [r for rules in rules_list for r in rules if rule_type(r) == "DOMAIN"]
    print(f"[{datetime.now()}] Merging DOMAIN: {len(domains)} found")
    for rule in domains:
        content = rule_content(rule)
        # 跳过被关键词覆盖的或后缀匹配的
        if any(rule_content(kw) in content for kw in keywords):
            continue
        if any(content.endswith(rule_content(s)) for s in final if rule_type(s) == "DOMAIN-SUFFIX"):
            continue
        if rule not in seen:
            seen.add(rule)
            final.append(rule)

    # 4. 最后处理其他类型（IP-CIDR、PROCESS-NAME、URL-REGEX 等），仅去重
    others = [r for rules in rules_list for r in rules if rule_type(r) not in ("DOMAIN-KEYWORD", "DOMAIN-SUFFIX", "DOMAIN")]
    print(f"[{datetime.now()}] Merging other rules: {len(others)} found")
    for rule in others:
        if rule not in seen:
            seen.add(rule)
            final.append(rule)

    print(f"[{datetime.now()}] Total merged rules: {len(final)}")
    return final

# 根据排除策略（exact 或 type）过滤合并后的规则
def exclude_rules(rules, exclude_rules_list, mode):
    print(f"[{datetime.now()}] Excluding with mode={mode}")

    # 精确匹配模式：排除与排除集完全相同的规则
    if mode == "exact":
        exclude_set = set(r for ex in exclude_rules_list for r in ex)
        filtered = [rule for rule in rules if rule not in exclude_set]
        print(f"[{datetime.now()}] Exact exclude removed {len(rules) - len(filtered)} rules")
        return filtered

    # 类型匹配模式：按照关键词、后缀、主域分别过滤
    print(f"[{datetime.now()}] Building exclude sets for type matching")
    ex_kw, ex_suf, ex_dom = set(), set(), set()
    for ex in exclude_rules_list:
        for rule in ex:
            t, c = rule_type(rule), rule_content(rule)
            if t == "DOMAIN-KEYWORD": ex_kw.add(c)
            elif t == "DOMAIN-SUFFIX": ex_suf.add(c)
            elif t == "DOMAIN": ex_dom.add(c)

    filtered, removed = [], 0
    for rule in rules:
        t, c = rule_type(rule), rule_content(rule)
        # DOMAIN-KEYWORD：匹配关键词
        if t == "DOMAIN-KEYWORD" and c in ex_kw:
            removed += 1
            continue
        # DOMAIN-SUFFIX：关键词或完全后缀匹配
        if t == "DOMAIN-SUFFIX" and (c in ex_suf or any(k in c for k in ex_kw)):
            removed += 1
            continue
        # DOMAIN：关键词、后缀或完全主域匹配
        if t == "DOMAIN" and (c in ex_dom or any(k in c for k in ex_kw) or any(c.endswith(s) for s in ex_suf)):
            removed += 1
            continue
        filtered.append(rule)

    print(f"[{datetime.now()}] Type exclude removed {removed} rules")
    return filtered

# 主流程：读取配置，执行合并与排除，并写入结果文件
def main():
    try:
        with open("merge_config.json", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        print(f"[{datetime.now()}] Error reading merge_config.json: {e}")
        return

    for name, info in cfg.items():
        print(f"[{datetime.now()}] Processing category: {name}")
        inc = info.get("include", [])      # 待合并的规则 URL 列表
        exc = info.get("exclude", [])      # 待排除的规则 URL 列表
