import os
import json
import requests

# 输出根目录及合并规则配置路径
OUTPUT_DIR = os.path.join("Ruleset", "Merged")
CONFIG_FILE = "merge_config.json"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 判断规则类型
def rule_type(line):
    return line.split(",", 1)[0] if "," in line else None

# 合并并优化函数
def merge_and_optimize(category, urls):
    seen = set()
    ordered = []
    # 拉取并去重
    for url in urls:
        r = requests.get(url, timeout=15); r.raise_for_status()
        for ln in r.text.splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#") or ln in seen: continue
            seen.add(ln); ordered.append(ln)

    # 类别分组
    keywords = [r for r in ordered if rule_type(r)=="DOMAIN-KEYWORD"]
    suffixes = [r for r in ordered if rule_type(r)=="DOMAIN-SUFFIX"]
    domains  = [r for r in ordered if rule_type(r)=="DOMAIN"]
    others   = [r for r in ordered if rule_type(r) not in ("DOMAIN-KEYWORD","DOMAIN-SUFFIX","DOMAIN")]

    # 如果含有 DOMAIN-KEYWORD,xxx，则可移除所有 DOMAIN-SUFFIX 包含关键词的规则
    optimized_suffix = []
    for s in suffixes:
        domain = s.split(",",1)[1]
        # 保留如果关键词列表中无一词出现在域名中
        if not any(kw.split(",",1)[1] in domain for kw in keywords):
            optimized_suffix.append(s)
    # 同理，DOMAIN 也可移除
    optimized_domains = []
    for d in domains:
        dom = d.split(",",1)[1]
        if not any(kw.split(",",1)[1] in dom for kw in keywords):
            optimized_domains.append(d)

    final = keywords + optimized_suffix + optimized_domains + others
    # 写入文件
    fname = f"{category.capitalize()}Unified.list"
    with open(os.path.join(OUTPUT_DIR, fname), "w", encoding="utf-8") as f:
        for rule in final:
            f.write(rule + "\n")
    print(f"{category}: {len(final)} 条规则生成完毕.")

# 主流程
with open(CONFIG_FILE, encoding="utf-8") as jf:
    cfg = json.load(jf)
for cat, urls in cfg.items():
    merge_and_optimize(cat, urls)
