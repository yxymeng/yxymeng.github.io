# -*- coding: utf-8 -*-
# 本脚本用于合并和排除 Clash 规则，支持按 URL 及类型跳过特定规则，并输出日志

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

import os
import json
import requests
import logging
from datetime import datetime

# 初始化日志，UTC ISO8601 格式
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)sZ %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S"
)

# 输出目录
OUTPUT_DIR = os.path.join("Ruleset", "Merged")
# 确保输出目录存在
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 时间戳函数
def now():
    return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

# 解析规则类型
def rule_type(line):
    return line.split(",", 1)[0] if "," in line else 'OTHER'

# 解析规则内容
def rule_content(line):
    return line.split(",", 1)[1] if "," in line else line

# 拉取规则，按 skip_types 跳过对应类型
def fetch_rules(url, skip_types):
    logging.info(f"Fetching {url} skip {skip_types}")
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        lines = []
        for ln in r.text.splitlines():
            ln = ln.strip()
            if not ln or ln.startswith('#'): continue
            t = rule_type(ln)
            if t in skip_types: continue
            lines.append(ln)
        logging.info(f"Retrieved {len(lines)} rules from {url}")
        return lines
    except Exception as e:
        logging.error(f"Error fetching {url}: {e}")
        return []

# 合并逻辑：DOMAIN-KEYWORD > DOMAIN-SUFFIX > DOMAIN > others
def merge_rules(rules_list):
    seen, final = set(), []
    kws = [r for rules in rules_list for r in rules if rule_type(r)=='DOMAIN-KEYWORD']
    for r in kws:
        if r not in seen: seen.add(r); final.append(r)
    sfx = [r for rules in rules_list for r in rules if rule_type(r)=='DOMAIN-SUFFIX']
    kept_sfx=[]
    for r in sfx:
        c=rule_content(r)
        if any(rule_content(k) in c for k in kws): continue
        if r not in seen: seen.add(r); final.append(r); kept_sfx.append(r)
    dom = [r for rules in rules_list for r in rules if rule_type(r)=='DOMAIN']
    kept_dom=[]
    for r in dom:
        c=rule_content(r)
        if any(rule_content(k) in c for k in kws): continue
        if any(c.endswith(rule_content(s)) for s in kept_sfx): continue
        if r not in seen: seen.add(r); final.append(r); kept_dom.append(r)
    oth = [r for rules in rules_list for r in rules if rule_type(r) not in ('DOMAIN-KEYWORD','DOMAIN-SUFFIX','DOMAIN')]
    for r in oth:
        if r not in seen: seen.add(r); final.append(r)
    return final

# 排除逻辑：exact 或 type
def exclude_rules(rules, exclude_lists, mode):
    if mode=='exact':
        ex_set = set(r for ex in exclude_lists for r in ex)
        return [r for r in rules if r not in ex_set]
    ex_kw, ex_suf, ex_dom, ex_oth = set(), set(), set(), set()
    for ex in exclude_lists:
        for r in ex:
            t, c = rule_type(r), rule_content(r)
            if t=='DOMAIN-KEYWORD': ex_kw.add(c)
            elif t=='DOMAIN-SUFFIX': ex_suf.add(c)
            elif t=='DOMAIN': ex_dom.add(c)
            else: ex_oth.add(r)
    res=[]
    for r in rules:
        t, c = rule_type(r), rule_content(r)
        if t=='DOMAIN-KEYWORD' and c in ex_kw: continue
        if t=='DOMAIN-SUFFIX' and (c in ex_suf or any(k in c for k in ex_kw)): continue
        if t=='DOMAIN' and (c in ex_dom or any(k in c for k in ex_kw) or any(c.endswith(s) for s in ex_suf)): continue
        if t not in ('DOMAIN-KEYWORD','DOMAIN-SUFFIX','DOMAIN') and r in ex_oth: continue
        res.append(r)
    return res

# 校验配置
REQUIRED_KEYS=['include','exclude','exclude_mode']
def validate_cfg(name, info):
    for k in REQUIRED_KEYS:
        if k not in info:
            logging.error(f"Missing key '{k}' in config for {name}")
            return False
    return True

# 主流程
if __name__=='__main__':
    try:
        cfg=json.load(open('merge_config.json',encoding='utf-8'))
    except Exception as e:
        logging.error(f"Config load error: {e}")
        exit(1)
    for name,info in cfg.items():
        logging.info(f"=== {name} start ===")
        if not validate_cfg(name,info): exit(1)
        srcs=[fetch_rules(u,skip) for u,skip in info['include'].items()]
        merged=merge_rules(srcs)
        exc=[fetch_rules(u,[]) for u in info['exclude']]
        final=exclude_rules(merged,exc,info['exclude_mode'])
        stats={}
        for r in final: stats[rule_type(r)]=stats.get(rule_type(r),0)+1
        total=len(final)
        path=os.path.join(OUTPUT_DIR,f"{name}.list")
        with open(path,'w',encoding='utf-8') as f:
            f.write(f"# NAME: {name}\n")
            f.write(f"# AUTHOR: yxymeng\n")
            f.write(f"# REPO: https://github.com/yxymeng/yxymeng.github.io\n")
            f.write(f"# UPDATED: {now()}\n")
            for k,v in stats.items(): f.write(f"# {k}: {v}\n")
            f.write(f"# TOTAL: {total}\n\n")
            f.write("\n".join(final))
        logging.info(f"Wrote {total} rules to {path}")
