#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
脚本: merge_ads.py
功能: 从多个 Clash 广告列表抓取规则，合并并去重，
     优先保留国内规则，输出合并后的列表文件。
"""

import requests
import os

# 定义所有规则列表的 URL
urls = {
    "BanEasyListChina": "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/BanEasyListChina.list",
    "BanAD":            "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/BanAD.list",
    "BanProgramAD":     "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/BanProgramAD.list",
   # "BanEasyList":      "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/BanEasyList.list",
    "BanEasyPrivacy":   "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/BanEasyPrivacy.list"
}

# 用于保存所有已收集规则的集合，方便去重
seen_rules = set()
# 最终的规则列表（有序保存输出顺序）
merged_rules = []

# 如果不存在输出目录则创建
os.makedirs("Ruleset", exist_ok=True)

# 先处理国内广告列表，优先保留国内规则
print("开始下载国内广告规则列表 ...")
resp = requests.get(urls["BanEasyListChina"])
resp.encoding = 'utf-8'
china_lines = resp.text.splitlines()
for line in china_lines:
    line = line.strip()
    # 跳过空行和注释
    if not line or line.startswith("#"):
        continue
    # 如果还没有见过该规则，则添加
    if line not in seen_rules:
        seen_rules.add(line)
        merged_rules.append(line)

# 处理其他所有广告规则列表
for name in ["BanAD", "BanProgramAD", "BanEasyPrivacy"]:
    print(f"开始下载规则列表: {name} ...")
    resp = requests.get(urls[name])
    resp.encoding = 'utf-8'
    lines = resp.text.splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # 只有不在已收集集合中的规则才添加
        if line not in seen_rules:
            seen_rules.add(line)
            merged_rules.append(line)

# 将合并后的规则写入输出文件，每行一个规则
output_path = "Ruleset/AdsUnified.list"
with open(output_path, "w", encoding="utf-8") as f:
    for rule in merged_rules:
        f.write(rule + "\n")

print(f"合并完成，输出文件：{output_path} (共 {len(merged_rules)} 条规则)")
