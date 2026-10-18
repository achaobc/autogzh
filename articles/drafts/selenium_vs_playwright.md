---
title: "干了十年自动化，我劝你别再盲目用 Selenium 搞批量任务了"
author: "阿超"
digest: "很多新手做自动化还在死磕 Selenium，遇到内存泄漏与无头指纹封控焦头烂额。聊聊为什么现代工程全面转向轻量化架构。"
cover: "assets/cover.png"
style: "tech"
pygments_style: "monokai"
status: "scheduled"
scheduled_date: "2026-10-21"
enable_footnotes: true
content_source_url: "https://github.com/achaobc/autogzh"
tags: ["Selenium", "Playwright", "架构设计"]
---

# 干了十年自动化，我劝你别再盲目用 Selenium 搞批量任务了

很多刚入行自动化测试或者爬虫的朋友，第一反应往往都是直接 `pip install selenium`。

然而，一旦进入每天需要稳定处理成千上万个任务的生产环境，Selenium 往往最先暴露出严重弊端：

- 内存开销巨大，多开几个实例服务器直接宕机；
- 浏览器指纹暴露严重，极其容易触发平台的各类风控拦截；
- 异步支持孱弱，高并发下连接经常死锁。

---

## 01. 内存黑洞：并发场景下的致命短板

Selenium 底层依赖独立的 WebDriver 驱动二进制进程，每次与浏览器通信都走一次外部 HTTP 请求。

在单任务调试时这没问题，但在批量并发任务中，这种架构会带来剧烈的进程开销与不可预测的内存泄漏：

```text
Selenium:   [Python Code] -> HTTP -> [chromedriver.exe] -> Chrome DevTools -> [Browser]
Playwright: [Python Code] ------------ WebSocket (直接直连) -------------> [Browser]
```

> ⚠️ **实战经验**：同等并发规模下，切换到基于 CDP 协议的直连架构，服务器内存开销能直接降低 60% 以上。

---

## 02. 指纹特征：现代风控的第一道防线

现在的平台反爬系统，早就不仅仅看 IP 和 User-Agent 了：

1. `navigator.webdriver` 标识侦测；
2. Canvas / WebGL 硬件指纹一致性；
3. 鼠标轨迹与时序分布分析。

Selenium 默认启动的浏览器实例，会带有极其显眼的自动化指纹特征，这也是为什么新手写出来的脚本即便换了代理 IP 还是秒封的原因。

---

## ✦ 总结建议

技术选型没有绝对的好坏，但要有敬畏之心。做大规模数据任务，请优先考虑轻量化协议直连方案与现代化的异步执行引擎。

---

> 💡 扩展阅读：
> - 现代自动化协议规范：[Chrome DevTools Protocol (CDP)](https://chromedevtools.github.io/devtools-protocol/)
> - 开源自动化排版工具：[AutoGZH GitHub](https://github.com/achaobc/autogzh)
