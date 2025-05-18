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
    :param output_path: ### 输出文件路径
脚本会将生成的 `convert_adguard_to_clash` 文件写入当前工作目录（即仓库根目录）。在本地或 GitHub Actions 中，输出路径均为仓库根目录下的 `convert_adguard_to_clash`。
