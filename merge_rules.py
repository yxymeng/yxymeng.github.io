import os
import json
import requests
from urllib.parse import urlparse

# 输出目录
OUTPUT_DIR = os.path.join("Ruleset", "Merged")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 获取规则类型
def rule_type(line):
    return line.split(",", 1)[0] if "," in line else None

# 获取规则内容（去除类型前缀）
def rule_content(line):
    return line.split(",", 1)[1] if "," in line else line

# 拉取规则集合
def fetch_rules(url):
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return [ln.strip() for ln in r.text.splitlines() if ln.strip() and not ln.startswith("#")]

# 分类规则
def classify_rules(rules):
    classified = {
        "DOMAIN-KEYWORD": set(),
        "DOMAIN-SUFFIX": set(),
        "DOMAIN": set(),
        "OTHERS": set()
    }
    for rule in rules:
        r_type = rule_type(rule)
        content = rule_content(rule)
        if r_type in classified:
            classified[r_type].add(content)
        else:
            classified["OTHERS"].add(rule)
    return classified

# 合并规则，包含去重和优化
def merge_rules(rules_list):
    seen = set()
    final = []

    # 先处理 DOMAIN-KEYWORD
    keyword_set = set()
    for rules in rules_list:
        for rule in rules:
            if rule_type(rule) == "DOMAIN-KEYWORD":
                content = rule_content(rule)
                if content not in keyword_set:
                    keyword_set.add(content)
                    if rule not in seen:
                        seen.add(rule)
                        final.append(rule)

    # 处理 DOMAIN-SUFFIX 和 DOMAIN，避免与 DOMAIN-KEYWORD 冲突
    suffix_set = set()
    domain_set = set()
    for rules in rules_list:
        for rule in rules:
            r_type = rule_type(rule)
            content = rule_content(rule)
            if r_type == "DOMAIN-SUFFIX":
                if any(kw in content for kw in keyword_set):
                    continue
                if content not in suffix_set:
                    suffix_set.add(content)
                    if rule not in seen:
                        seen.add(rule)
                        final.append(rule)
            elif r_type == "DOMAIN":
                if any(kw in content for kw in keyword_set):
                    continue
                if any(content.endswith(suf) for suf in suffix_set):
                    continue
                if content not in domain_set:
                    domain_set.add(content)
                    if rule not in seen:
                        seen.add(rule)
                        final.append(rule)

    # 处理其他类型
    for rules in rules_list:
        for rule in rules:
            r_type = rule_type(rule)
            if r_type not in ["DOMAIN-KEYWORD", "DOMAIN-SUFFIX", "DOMAIN"]:
                if rule not in seen:
                    seen.add(rule)
                    final.append(rule)

    return final

# 排除规则
def exclude_rules(rules, exclude_rules_list, mode):
    if mode == "exact":
        exclude_set = set()
        for ex_rules in exclude_rules_list:
            exclude_set.update(ex_rules)
        return [rule for rule in rules if rule not in exclude_set]
    elif mode == "type":
        # 分类排除规则
        ex_classified = {
            "DOMAIN-KEYWORD": set(),
            "DOMAIN-SUFFIX": set(),
            "DOMAIN": set()
        }
        for ex_rules in exclude_rules_list:
            for rule in ex_rules:
                r_type = rule_type(rule)
                content = rule_content(rule)
                if r_type in ex_classified:
                    ex_classified[r_type].add(content)

        # 排除规则
        result = []
        for rule in rules:
            r_type = rule_type(rule)
            content = rule_content(rule)
            if r_type == "DOMAIN-KEYWORD":
                if content in ex_classified["DOMAIN-KEYWORD"]:
                    continue
            elif r_type == "DOMAIN-SUFFIX":
                if any(kw in content for kw in ex_classified["DOMAIN-KEYWORD"]):
                    continue
                if content in ex_classified["DOMAIN-SUFFIX"]:
                    continue
            elif r_type == "DOMAIN":
                if any(kw in content for kw in ex_classified["DOMAIN-KEYWORD"]):
                    continue
                if any(content.endswith(suf) for suf in ex_classified["DOMAIN-SUFFIX"]):
                    continue
                if content in ex_classified["DOMAIN"]:
                    continue
            else:
                if rule in ex_classified.get("OTHERS", set()):
                    continue
            result.append(rule)
        return result
    else:
        return rules

# 主函数
def main():
    with open("merge_config.json", encoding="utf-8") as f:
        config = json.load(f)

    for name, info in config.items():
        include_urls = info.get("include", [])
        exclude_urls = info.get("exclude", [])
        exclude_mode = info.get("exclude_mode", "exact")

        # 拉取包含规则
        include_rules_list = []
        for url in include_urls:
            try:
                rules = fetch_rules(url)
                include_rules_list.append(rules)
            except Exception as e:
                print(f"Failed to fetch {url}: {e}")

        # 合并规则
        merged_rules = merge_rules(include_rules_list)

        # 拉取排除规则
        exclude_rules_list = []
        for url in exclude_urls:
            try:
                rules = fetch_rules(url)
                exclude_rules_list.append(rules)
            except Exception as e:
                print(f"Failed to fetch {url}: {e}")

        # 排除规则
        final_rules = exclude_rules(merged_rules, exclude_rules_list, exclude_mode)

        # 写入文件
        output_path = os.path.join(OUTPUT_DIR, f"{name}.list")
        with open(output_path, "w", encoding="utf-8") as f:
            for rule in final_rules:
                f.write(rule + "\n")
        print(f"Generated {output_path} with {len(final_rules)} rules.")

if __name__ == "__main__":
    main()
