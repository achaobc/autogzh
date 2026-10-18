---
title: 为什么你用 AI 写的自动化脚本跑半小时就崩？聊聊最值钱的容错与状态机
author: 阿超
digest: AI 能秒写语法，但写不出工程韧性。十年老程序员聊聊自动化脚本真正值钱的容错设计与状态机重构。
cover: assets/cover.png
style: story
pygments_style: monokai
status: scheduled
scheduled_date: '2026-10-19'
enable_footnotes: true
content_source_url: https://github.com/achaobc/autogzh
---

# 为什么你用 AI 写的自动化脚本跑半小时就崩？聊聊最值钱的容错与状态机

最近很多做爬虫、RPA 和脚本自动化的朋友跑来跟我倒苦水：

> “超哥，现在有了 AI 确实省事，动动嘴就能让大模型写出一个 Python 自动化脚本，抓数据、模拟点击一气呵成。但在我电脑上明明跑得好好的，一部署到服务器或者真机上，**跑上三四十分钟必然莫名其妙假死、报错崩溃**。这到底是为什么？”

其实答案特别残酷：**AI 只是干掉了‘写代码’的门槛，但真实运行环境里的各种烂摊子，它一个都替你擦不了屁股。**

---

## 01. 线性思维是自动化崩溃的万恶之源

绝大多数人（包括让 AI 直接生成的代码）写自动化脚本，骨子里全都是**“线性思维”**：

```text
第 1 步：打开网页或 App
第 2 步：休眠 3 秒等待加载
第 3 步：定位按钮并点击
第 4 步：读取页面数据并入库
```

在完美的理想测试环境下，这套逻辑挑不出一点毛病。

但现实世界是极其混乱而残酷的：
- 网络稍微抖动了一下，页面多加载了 1 秒，你的第 3 步就会直接抛出 `ElementNotFound` 异常，脚本卒；
- 目标平台冷不丁弹出了一个风控滑块、新手活动悬浮窗或者强制升级公告，直接把按钮挡住，脚本假死；
- 后台会话 Token 过期，接口返回了 401，后续所有循环全部在往日志里狂刷几十万行报错。

> ⚠️ **残酷真相**：线性思维写出来的脚本就像一块极脆的玻璃，任何一次非预期的微小扰动，都会导致整个流程瞬间粉碎。

---

## 02. 从“流水账脚本”进化到“有限状态机”

真正能在生产环境 7x24 小时连续运行不崩溃的自动化工程，底层绝不是长长的流水账，而是**状态机（Finite State Machine, FSM）**。

简单来说，**永远不要假设当前程序在第几步，而是让程序主动侦测当前处于什么状态**：

| 维度 | 传统线性脚本 (AI 常见生成) | 状态机驱动 (高可靠工程) |
| :--- | :--- | :--- |
| **执行逻辑** | 一条道走到黑，遇到异常直接爆栈崩溃 | 状态自检 -> 触发动作 -> 迁移到新状态 |
| **异常处理** | `try...except` 盲目打印后退出 | 状态自动回退（如重置到首页状态） |
| **环境兼容** | 依赖固定 `time.sleep()` 赌运气 | 状态轮询探活，配合指数退避保护 |
| **可维护性** | 几千行巨型函数，改一步全局牵连 | 每个状态独立封装，随时热插拔 |

无论是做网页爬虫还是做手机自动化，你只需要把核心状态抽象出来：
1. `INIT`（初始化与环境健康检查）
2. `LOGIN_CHECK`（登录态探活，失效则跳转重登）
3. `TARGET_VIEW`（主业务执行中）
4. `EXCEPTION_HANDLING`（风控识别、异常弹窗打捞与状态复位）

---

## 03. 真正值钱的容错实战：指数退避与看门狗

下面这段代码，展示了工业级脚本中标准的**“状态重试与指数退避（Exponential Backoff）”**范式。建议大家直接收藏套用：

```python
import time
import logging

logger = logging.getLogger("Watchdog")

class TaskState:
    IDLE = "IDLE"
    FETCHING = "FETCHING"
    RETRYING = "RETRYING"
    SUCCESS = "SUCCESS"
    FATAL = "FATAL"

def execute_with_resilience(action_fn, max_retries=5, base_delay=2.0):
    """
    具备指数退避与自愈能力的容错执行器
    """
    state = TaskState.FETCHING
    retries = 0

    while retries < max_retries:
        try:
            logger.info(f"当前执行状态: {state} (尝试第 {retries + 1} 次)")
            result = action_fn()
            state = TaskState.SUCCESS
            return result
        except ConnectionError as e:
            retries += 1
            state = TaskState.RETRYING
            # 指数退避：每次重试间隔翻倍，防止将对端接口打崩被封 IP
            delay = base_delay * (2 ** (retries - 1))
            logger.warning(f"网络异常: {e}，将在 {delay:.1f} 秒后重试...")
            time.sleep(delay)
        except Exception as e:
            logger.error(f"遭遇不可逆未知异常: {e}")
            state = TaskState.FATAL
            break

    raise RuntimeError("重试达到最大次数上限，任务安全熔断。")
```

学会把这套逻辑塞给 AI，让它往你的框架里填充具体抓取代码，你的自动化稳定性会直接提升一个量级。

---

## ✦ 说点掏心窝子的实话

在今天这个时代，**写代码本身正在变得极度廉价**。

你能让 AI 5 秒钟写出一个轮询，别人也能让 AI 5 秒钟写出来。但当几十台服务器上的脚本因为一次网络抖动全军覆没的时候，能够定位到底层并发死锁、能够设计出防风控状态流、能够用最小成本实现自愈的人，才是真正不可替代的核心资产。

不要把精力耗在死记硬背语法上，多去思考**“系统在什么情况下会挂”**以及**“挂了之后怎么体面地自愈”**。

---

> 💡 如果你的自动化项目也经常遇到连接中断或状态重试问题，建议深入阅读：
> - 专业的重试库指南：[Python Tenacity 官方文档](https://tenacity.readthedocs.io)
> - 现代无头浏览器自动化最佳实践：[Playwright 官方指南](https://playwright.dev)
> - 本文配套同步工具开源仓库：[AutoGZH GitHub](https://github.com/achaobc/autogzh)
