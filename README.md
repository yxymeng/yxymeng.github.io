# yxymeng.github.io
自己用的一个Clash for Windows的预处理配置，完全定制化的规则集、规则、策略组。原文是来自[Iridescent-me的parser分享](https://github.com/Fndroid/clash_for_windows_pkg/issues/2193)。
以及根据[Wzieee 的配置](https://github.com/Fndroid/clash_for_windows_pkg/issues/2729)慢慢调整的自己的配置文件。
---
## 需要注意的点：
1.策略组设置的是延迟优先，默认的延迟地址是可以检测DIRECT的，所以我把延迟检测地址换成了谷歌的，避免软件代理走DIRECT。最好在clash设置里面把延迟检测地址改成谷歌的。  

2.不添加DIRECT节点发现策略组筛选条件无法匹配机场节点时候会报错，所以如果报错的话可以给策略组添加个DIRECT。
>举个例子：策略组筛选所有带“香”字的节点，但是机场节点没有香港节点，这个时候clash就会报错，提示"proxy group:use or proxy is missinig"。

3、目前这个分流规则对于epic、steam不是很好，我刚刚更新游戏的时候发现epic走的是代理，节点流量不够的朋友需要注意点。换成直接模式再更新或者把分流规则添加进来。 

4、因为分流规则比较多，可能会提示网络错误，多试几次就行了。或者去[分流规则作者](https://github.com/Loyalsoldier/clash-rules)那边下载规则放在clash目录ruleset文件里。  
