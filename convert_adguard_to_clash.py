#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re       # 用于正则表达式匹配
import sys      # 用于获取脚本参数和退出
import requests # 用于 HTTP 请求


def fetch_remote(url):
    """
    从指定 URL 拉取文本内容，并按行返回。
    :param url: 远程文件链接
    :return: 文本按行拆分后的列表
    """
    # 发起 GET 请求，设置超时时间为 10 秒
    resp = requests.get(url, timeout=10)
    # 如果状态码不是 200，会抛出异常并停止脚本
    resp.raise_for_status()
    # 将响应内容按行拆分并返回列表
    return resp.text.splitlines()


def parse_adguard(lines):
    """
    解析 AdGuard 规则行，提取域名。
    只处理以 "||域名^" 开头的规则。
    :param lines: 文本行列表
    :return: 提取出的域名列表
    """
    domains = []
    # 正则：匹配以 || 开头，中间非 ^ 字符，结尾 ^
    pattern = re.compile(r"^\|\|([^\^]+)\^")
    for line in lines:
        line = line.strip()          # 去除首尾空白
        if not line or line.startswith('#'):
            continue                 # 跳过空行或注释行
        m = pattern.match(line)
        if m:
            domains.append(m.group(1))
    return domains


def write_clash_list(domains, output_path):
    """
    将域名列表写入 Clash 列表文件，格式：DOMAIN,域名
    :param domains: 域名列表
    :param output_path: 输出文件路径
    """
    # 去重并排序，保证一致性
    unique_domains = sorted(set(domains))
    with open(output_path, 'w', encoding='utf-8') as f:
        for d in unique_domains:
            # 写入每一行，格式为 "DOMAIN,域名"
            f.write(f"DOMAIN,{d}\n")


def main():
    """
    脚本入口：
    接收两个参数：远程 URL 和 输出文件名。
    """
    if len(sys.argv) != 3:
        # 参数错误时打印用法并退出
        print("用法: python convert_adguard_to_clash.py <远程URL> <输出文件>")
        sys.exit(1)

    url = sys.argv[1]          # 远程 AdGuard 规则链接
    output_file = sys.argv[2]  # 输出文件，如 clash_list.list

    # 拉取远程规则并解析域名
    lines = fetch_remote(url)
    domains = parse_adguard(lines)

    # 生成 Clash 列表文件
    write_clash_list(domains, output_file)
    print(f"已生成 Clash 列表: {output_file}，共 {len(domains)} 条记录。")


if __name__ == '__main__':
    main()
