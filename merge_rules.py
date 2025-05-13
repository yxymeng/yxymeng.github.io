import os
import json
import requests
from datetime import datetime

# === 配置说明 ===
# merge_config.json 文件格式示例：
# {
#   "ads": {
#     "include": {
#       "https://.../link1.list": ["IP-CIDR"],
#       "https://.../link2.list": ["DOMAIN"]
#     },
#     "exclude": ["https://.../unban.list"],
#     "exclude_mode": "type"
#   }
# }

# 输出目录，用于存放合并并排除后的规则文件
OUTPUT_DIR = os.path.join("Ruleset", "Merged")
# 确保输出目录存在
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 获取当前时间字符串，用于日志输出
def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# 解析规则类型（如 "DOMAIN-SUFFIX"、"IP-CIDR" 等）
def rule_type(line):
    return line.split(",", 1)[0] if "," in line else None

# 获取规则参数部分（逗号后面内容）
def rule_content(line):
    return line.split(",", 1)[1] if "," in line else line

# 从 URL 拉取规则，支持按类型跳过(skip_types)，并打印日志
def fetch_rules(url, skip_types):
    print(f"[{now()}] Fetching {url}, skipping types: {skip_types}")
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        lines = []
        for ln in r.text.splitlines():
            ln = ln.strip()
            if not ln or ln.startswith('#'): continue
            t = rule_type(ln)
            # 跳过指定类型规则
            if t in skip_types:
                continue
            lines.append(ln)
        print(f"[{now()}] Retrieved {len(lines)} clean rules from {url}")
        return lines
    except Exception as e:
        print(f"[{now()}] Error fetching {url}: {e}")
        return []

# 合并规则：按类型优先级合并并去重
def merge_rules(rules_list):
    print(f"[{now()}] Starting merge of {len(rules_list)} sources")
    seen, final = set(), []
    # 1. DOMAIN-KEYWORD 优先
    kws = [r for rules in rules_list for r in rules if rule_type(r)=='DOMAIN-KEYWORD']
    print(f"[{now()}] DOMAIN-KEYWORD found: {len(kws)}")
    for r in kws:
        if r not in seen:
            seen.add(r)
            final.append(r)
    # 2. DOMAIN-SUFFIX
    sfx = [r for rules in rules_list for r in rules if rule_type(r)=='DOMAIN-SUFFIX']
    print(f"[{now()}] DOMAIN-SUFFIX found: {len(sfx)}")
    kept_sfx=[]
    for r in sfx:
        c = rule_content(r)
        if any(rule_content(k) in c for k in kws): continue
        if r not in seen:
            seen.add(r); final.append(r); kept_sfx.append(r)
    print(f"[{now()}] DOMAIN-SUFFIX kept: {len(kept_sfx)}")
    # 3. DOMAIN
    dom = [r for rules in rules_list for r in rules if rule_type(r)=='DOMAIN']
    print(f"[{now()}] DOMAIN found: {len(dom)}")
    kept_dom=[]
    for r in dom:
        c = rule_content(r)
        if any(rule_content(k) in c for k in kws): continue
        if any(c.endswith(rule_content(s)) for s in kept_sfx): continue
        if r not in seen:
            seen.add(r); final.append(r); kept_dom.append(r)
    print(f"[{now()}] DOMAIN kept: {len(kept_dom)}")
    # 4. 其他类型(IP-CIDR,PROCESS-NAME,URL-REGEX 等)
    oth = [r for rules in rules_list for r in rules if rule_type(r) not in ('DOMAIN-KEYWORD','DOMAIN-SUFFIX','DOMAIN')]
    print(f"[{now()}] Other types found: {len(oth)}")
    kept_oth=[]
    for r in oth:
        if r not in seen:
            seen.add(r); final.append(r); kept_oth.append(r)
    print(f"[{now()}] Other types kept: {len(kept_oth)}")
    print(f"[{now()}] Merge result total: {len(final)} rules")
    return final

# 排除规则：exact(精确) 或 type(类型匹配+精确其他)
def exclude_rules(rules, exclude_lists, mode):
    print(f"[{now()}] Excluding with mode={mode}")
    # exact 模式：完全字符串匹配
    if mode=='exact':
        ex_set = set(r for ex in exclude_lists for r in ex)
        res = [r for r in rules if r not in ex_set]
        print(f"[{now()}] Exact exclude removed: {len(rules)-len(res)} rules")
        return res
    # type 模式：域名类型按类型匹配，其他类型精确匹配
    ex_kw,ex_suf,ex_dom,ex_oth=set(),set(),set(),set()
    for ex in exclude_lists:
        for r in ex:
            t,c = rule_type(r),rule_content(r)
            if t=='DOMAIN-KEYWORD': ex_kw.add(c)
            elif t=='DOMAIN-SUFFIX': ex_suf.add(c)
            elif t=='DOMAIN': ex_dom.add(c)
            else: ex_oth.add(r)
    res=[]; removed=0
    for r in rules:
        t,c=rule_type(r),rule_content(r)
        if t=='DOMAIN-KEYWORD' and c in ex_kw: removed+=1; continue
        if t=='DOMAIN-SUFFIX' and (c in ex_suf or any(k in c for k in ex_kw)): removed+=1; continue
        if t=='DOMAIN' and (c in ex_dom or any(k in c for k in ex_kw) or any(c.endswith(s) for s in ex_suf)): removed+=1; continue
        if t not in ('DOMAIN-KEYWORD','DOMAIN-SUFFIX','DOMAIN') and r in ex_oth: removed+=1; continue
        res.append(r)
    print(f"[{now()}] Type exclude removed: {removed} rules")
    return res

# 主流程：依配置合并、排除并输出
if __name__=='__main__':
    try:
        cfg=json.load(open('merge_config.json',encoding='utf-8'))
    except Exception as e:
        print(f"[{now()}] Config load error: {e}"); exit(1)
    for name,info in cfg.items():
        print(f"[{now()}] === {name} start ===")
        include_cfg=info.get('include',{})
        lists=[fetch_rules(u,skip) for u,skip in include_cfg.items()]
        merged=merge_rules(lists)
        exclude_cfg=info.get('exclude',[])
        excl=[fetch_rules(u,[]) for u in exclude_cfg]
        final=exclude_rules(merged,excl,info.get('exclude_mode','exact'))
        path=os.path.join(OUTPUT_DIR,f"{name}.list")
        try:
            with open(path,'w',encoding='utf-8') as f:
                f.write('\n'.join(final))
            print(f"[{now()}] Wrote {len(final)} rules to {path}")
        except Exception as e:
            print(f"[{now()}] Write error {path}: {e}")
    print(f"[{now()}] All categories processed.")
