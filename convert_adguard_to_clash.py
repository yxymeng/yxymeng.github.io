import requests
import re

# 设置远程 AdGuard 规则的 URL
ADGUARD_RULE_URL = "https://raw.githubusercontent.com/hululu1068/AdGuard-Rule/main/rule/domain.txt"

# 设置输出文件名
OUTPUT_FILE = "convert_adguard_to_clash.list"

def fetch_rules(url):
    """从远程 URL 拉取规则内容"""
    response = requests.get(url)
    response.raise_for_status()
    return response.text

def extract_domains(text):
    """从 AdGuard 规则文本中提取域名并格式化为 Clash 的 DOMAIN 规则格式"""
    domain_rules = []
    for line in text.splitlines():
        line = line.strip()
        # 跳过注释或空行
        if not line or line.startswith("!") or line.startswith("#"):
            continue

        # 处理 AdGuard 的 plain domain 规则，如 "||example.com^"
        if line.startswith("||") and line.endswith("^"):
            domain = line[2:-1]
            domain_rules.append(f"DOMAIN,{domain}")
        # 处理直接写域名的行，如 "example.com"
        elif re.match(r"^([a-zA-Z0-9_.-]+\.[a-zA-Z]{2,})$", line):
            domain_rules.append(f"DOMAIN,{line}")
        # 可根据需要添加更多解析规则
    return domain_rules

def save_to_file(rules, filename):
    """将提取的规则保存到文件中"""
    with open(filename, "w", encoding="utf-8") as f:
        for rule in rules:
            f.write(rule + "\n")

def main():
    text = fetch_rules(ADGUARD_RULE_URL)
    rules = extract_domains(text)
    save_to_file(rules, OUTPUT_FILE)

if __name__ == "__main__":
    main()
