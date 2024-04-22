# 简介
此仓库主要使用的是[Ruleset](https://github.com/yxymeng/yxymeng.github.io/tree/master/Ruleset)文件夹里的[Clash.ini](https://github.com/yxymeng/yxymeng.github.io/blob/master/Ruleset/Clash.ini)，使用[ACL4SSR](https://acl4ssr-sub.github.io/)来进行节点转换。Parsers预处理配置的方式可以搁置，对于多端使用不是很方便。

1. 需要用到的链接或网站：[在线订阅转换网站](https://acl4ssr-sub.github.io/)、[URLEncode](https://www.urlencoder.org/)处理网站以及你自己的机场订阅链接等。
2. 可能用到的Github仓库：本仓库[Ruleset](https://github.com/yxymeng/yxymeng.github.io/tree/master/Ruleset)里的`.ini`后缀的文档链接、[Subconverter](https://github.com/tindy2013/subconverter/tree/master)、[ACL4SSR](https://github.com/ACL4SSR/ACL4SSR)

自己用的一个Clash for Windows的预处理配置，完全定制化的规则集、规则、策略组。原文是来自[Iridescent-me](https://github.com/Fndroid/clash_for_windows_pkg/issues/2193)的parser分享。
以及根据[Wzieee 的配置](https://github.com/Fndroid/clash_for_windows_pkg/issues/2729)慢慢调整的自己的配置文件。

---

## 需要注意的点：

1. 不添加DIRECT节点发现策略组筛选条件无法匹配机场节点时候会报错，所以如果报错的话可以给策略组添加个DIRECT。

>举个例子：策略组筛选所有带“香”字的节点，但是机场节点没有香港节点，这个时候clash就会报错，提示`proxy group:use or proxy is missinig`

2. 因为分流规则比较多，可能会提示网络错误，多试几次就行了。或者去[分流规则作者](https://github.com/Loyalsoldier/clash-rules)那边下载规则放在clash目录ruleset文件里。或者用raw.staticdn.net替换provider里的链接的raw.githubusercontent.com，此为反代，手机上想更新规则只能用此反代
以上为使用parsers来预处理配置需要注意的地方
---
