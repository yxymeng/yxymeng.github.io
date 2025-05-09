#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
脚本: merge_ads.py
功能: 从多个 Clash 广告列表抓取规则，合并并去重，
     优先保留中国广告规则，并对 DOMAIN-SUFFIX 规则做父域合并优化，
     输出最终的纯文本规则文件：Ruleset/AdsUnified.list
"""
import requests
import os

# 1. 定义规则源 URL
urls = {
    # 优先保留中国版 EasyList
    "BanEasyListChina": "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/BanEasyListChina.list",
    # 其他广告规则列表
    "BanAD":          "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/BanAD.list",
    "BanProgramAD":   "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/BanProgramAD.list",
    "BanEasyList":    "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/BanEasyList.list",
    "BanEasyPrivacy": "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/BanEasyPrivacy.list"
}

# 2. 存储不同类型的规则
domain_rules = set()       # 保存 DOMAIN 规则
keyword_rules = set()      # 保存 DOMAIN-KEYWORD 规则
suffix_rules = []          # 暂存所有 DOMAIN-SUFFIX 域名，用于后续优化
suffix_rules_set = set()   # 辅助集合，用以快速判重

# 3. 下载并分类规则
for name, url in urls.items():
    try:
        print(f"下载规则: {name} 从 {url}")
        resp = requests.get(url, timeout=15)
        resp.encoding = 'utf-8'
    except Exception as e:
        print(f"无法获取 {name}: {e}")
        continue
    for line in resp.text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue  # 跳过空行和注释
        parts = line.split(',', 1)
        if len(parts) != 2:
            continue
        rtype, domain = parts[0].strip(), parts[1].strip()
        if rtype == 'DOMAIN':
            domain_rules.add(domain)
        elif rtype == 'DOMAIN-KEYWORD':
            keyword_rules.add(domain)
        elif rtype == 'DOMAIN-SUFFIX':
            # 去重同一列表内重复域名
            if domain not in suffix_rules_set:
                suffix_rules.append(domain)
                suffix_rules_set.add(domain)

# 4. 对 DOMAIN-SUFFIX 规则进行父域合并优化
optimized_suffix = []
for domain in sorted(suffix_rules, key=len):
    skip = False
    for kept in optimized_suffix.copy():
        # 如果 kept 是 domain 的子域，则移除 kept
        if kept.endswith('.' + domain):
            optimized_suffix.remove(kept)
        # 如果 domain 是 kept 的子域，则跳过添加 domain
        elif domain.endswith('.' + kept):
            skip = True
            break
    if not skip:
        optimized_suffix.append(domain)

# 5. 根据关键字规则清理 DOMAIN-SUFFIX
final_suffix = []
for suf in optimized_suffix:
    remove = False
    for kw in keyword_rules:
        if kw in suf:
            remove = True
            break
    if not remove:
        final_suffix.append(suf)

# 6. 输出到最终文件
out_dir = 'Ruleset'
os.makedirs(out_dir, exist_ok=True)
out_file = os.path.join(out_dir, 'AdsUnified.list')
with open(out_file, 'w', encoding='utf-8') as f:
    # 写入 DOMAIN 规则
    for d in sorted(domain_rules):
        f.write(f"DOMAIN,{d}\n")
    # 写入 DOMAIN-KEYWORD 规则
    for kw in sorted(keyword_rules):
        f.write(f"DOMAIN-KEYWORD,{kw}\n")
    # 写入优化后的 DOMAIN-SUFFIX 规则
    for suf in sorted(final_suffix):
        f.write(f"DOMAIN-SUFFIX,{suf}\n")

print(f"合并并优化完成，输出文件：{out_file} (共 {len(domain_rules) + len(keyword_rules) + len(final_suffix)} 条规则)")
