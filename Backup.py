import os
import json
import requests

# 根目录和配置文件
OUTPUT_DIR = os.path.join("Ruleset", "Merged")  
CONFIG_FILE = "merge_config.json"                 
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 获取规则类型
def rule_type(line):
    return line.split(",", 1)[0] if "," in line else None

# 拉取规则集合
def fetch_rules(url):
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return {ln.strip() for ln in r.text.splitlines() if ln.strip() and not ln.startswith("#")}

# 类型级过滤函数（参照 DOMAIN-KEYWORD 优化逻辑）
def type_based_filter(rules, exclude_rules):
    keywords = {r.split(",",1)[1] for r in exclude_rules if rule_type(r)=="DOMAIN-KEYWORD"}
    filtered = []
    for r in rules:
        if rule_type(r) in ("DOMAIN-SUFFIX","DOMAIN"):
            domain = r.split(",",1)[1]
            # 如果任何关键词匹配该域，则排除
            if any(kw in domain for kw in keywords):
                continue  # 排除模式匹配规则  # <== 新增逻辑注释
        filtered.append(r)
    return filtered

# 核心合并逻辑，支持动态排除模式
def merge_category(name, include_urls, exclude_urls=None, mode="exact"):
    exclude_urls = exclude_urls or []
    exclude_set = set()
    for url in exclude_urls:
        try:
            exclude_set |= fetch_rules(url)
        except:
            pass

    seen = set()
    ordered = []
    for url in include_urls:
        try:
            rules = fetch_rules(url)
        except:
            continue
        # 排除集过滤
        if mode == "exact":
            rules = {r for r in rules if r not in exclude_set}  # 精确匹配排除  # <== 新增逻辑注释
        elif mode == "type":
            rules = set(type_based_filter(list(rules), exclude_set))  # 类型级排除  # <== 新增逻辑注释
        for r in rules:
            if r not in seen:
                seen.add(r)
                ordered.append(r)

    # 写入文件
    fname = f"{name.capitalize()}Unified.list"
    with open(os.path.join(OUTPUT_DIR, fname), 'w', encoding='utf-8') as f:
        for ln in ordered:
            f.write(ln + "\n")
    print(f"{name}: 共 {len(ordered)} 条规则 (模式={mode}) 已写入")

# 主入口
with open(CONFIG_FILE, encoding='utf-8') as f:
    cfg = json.load(f)
for cat, info in cfg.items():
    inc = info.get('include', [])
    exc = info.get('exclude', [])
    mode = info.get('exclude_mode', 'exact')  # 从配置获取排除模式  # <== 新增逻辑注释
    merge_category(cat, inc, exc, mode)
