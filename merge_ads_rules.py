import requests

os.makedirs("Ruleset", exist_ok=True)

urls = [
    "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/BanAD.list",
    "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/BanProgramAD.list",
    "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/BanEasyList.list",
    "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/BanEasyListChina.list",
    "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/BanEasyPrivacy.list"
]
rules_set = set()
for url in urls:
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        for line in res.text.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            rules_set.add(line)
    except Exception as e:
        print(f"无法获取 {url}: {e}")

unified_rules = sorted(rules_set)
with open("AdsUnified.list", "w", encoding="utf-8") as f:
    f.write("\n".join(unified_rules))
print(f"共合并 {len(unified_rules)} 条规则，输出到 AdsUnified.list")
