import os
import json
import requests

# 定义输出目录和配置文件路径
OUTPUT_DIR = os.path.join("Ruleset", "Merged")
CONFIG_FILE = "merge_config.json"
os.makedirs(OUTPUT_DIR, exist_ok=True)  # 如果目录不存在则创建

# 判断规则的类型，例如 DOMAIN-SUFFIX、DOMAIN 等
def rule_type(line):
    parts = line.split(",", 1)
    return parts[0] if len(parts) == 2 else None

# 从 URL 获取规则列表（去除注释和空行）
def fetch_rules(url):
    try:
        print(f"Fetching rules from: {url}")
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        # 提取非注释和非空白行的规则
        rules = {ln.strip() for ln in r.text.splitlines() if ln.strip() and not ln.startswith("#")}
        print(f"Fetched {len(rules)} rules from {url}")
        return rules
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return set()

# 对规则进行类型级别的过滤（根据 DOMAIN-KEYWORD 剔除相关域）
def type_based_filter(rules, exclude_rules):
    print("Applying type-based exclusion filter...")
    # 提取所有 DOMAIN-KEYWORD 的关键词部分
    keywords = {r.split(",",1)[1] for r in exclude_rules if rule_type(r) == "DOMAIN-KEYWORD"}
    filtered = []
    removed = 0
    for r in rules:
        if rule_type(r) in ("DOMAIN-SUFFIX", "DOMAIN"):
            domain = r.split(",", 1)[1]
            # 如果当前域名中包含任意关键字，则过滤
            if any(kw in domain for kw in keywords):
                removed += 1
                continue
        filtered.append(r)
    print(f"Filtered out {removed} rules based on DOMAIN-KEYWORD match")
    return filtered

# 合并规则并应用排除逻辑
def merge_category(name, include_urls, exclude_urls=None, mode="exact"):
    print(f"\nProcessing category: {name} (mode={mode})")
    exclude_urls = exclude_urls or []
    exclude_set = set()

    # 获取所有排除规则集合
    for url in exclude_urls:
        exclude_set |= fetch_rules(url)

    seen = set()     # 去重集合
    ordered = []     # 保留顺序的列表

    # 遍历每个包含规则的 URL
    for url in include_urls:
        rules = fetch_rules(url)
        before_filter = len(rules)

        # 根据排除模式进行处理
        if mode == "exact":
            rules = {r for r in rules if r not in exclude_set}  # 精确排除
        elif mode == "type":
            rules = set(type_based_filter(list(rules), exclude_set))  # 类型级排除

        after_filter = len(rules)
        print(f"{url}: {before_filter - after_filter} rules filtered")

        # 添加到最终列表中（保持顺序并去重）
        for r in rules:
            if r not in seen:
                seen.add(r)
                ordered.append(r)

    # 写入合并后的规则到文件
    fname = f"{name.capitalize()}Unified.list"
    output_path = os.path.join(OUTPUT_DIR, fname)
    with open(output_path, 'w', encoding='utf-8') as f:
        for ln in ordered:
            f.write(ln + "\n")
    print(f"Wrote {len(ordered)} rules to {output_path}")

# 读取配置文件
with open(CONFIG_FILE, encoding='utf-8') as f:
    cfg = json.load(f)

print("Starting rule merging process...")
# 遍历每个分类并执行合并流程
for cat, info in cfg.items():
    inc = info.get('include', [])  # 包含规则的 URL 列表
    exc = info.get('exclude', [])  # 排除规则的 URL 列表
    mode = info.get('exclude_mode', 'exact')  # 排除模式（exact 或 type）
    merge_category(cat, inc, exc, mode)

print("All categories processed.")
