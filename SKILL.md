---
name: sakurafrp-daily-checkin
description: SakuraFrp（natfrp.com）内网穿透平台每日自动签到。当用户需要为 SakuraFrp 账号实现每日自动签到、自动领取免费流量（1~4 GiB），或复用/维护本仓库的 GitHub Actions 自动化签到流程时使用。覆盖 Playwright 登录、GeeTest 九宫格验证码 AI 视觉识别、页面广告弹窗移除、签到前后流量统计对比、SMTP 结果邮件通知全流程。
---

# SakuraFrp 每日自动签到（可复用 Skill）

为 SakuraFrp 账号搭建每日自动签到，签到奖励为免费流量（1~4 GiB/天），用于内网穿透。

## 何时使用

- 用户要求给 SakuraFrp / natfrp.com 账号做"自动签到 / 每日签到 / 流量领取自动化"。
- 用户想复用/维护本仓库的 GitHub Actions 自动化签到方案（改时间、换账号、改邮件、排障）。
- 用户遇到 SakuraFrp 登录、九宫格验证码、广告弹窗遮挡、Actions/邮件配置相关报错需要排障。

## 核心事实（部署前必须确认）

| 项 | 值 |
|---|---|
| SakuraFrp 官网 | `https://www.natfrp.com` |
| 登录页 | `https://www.natfrp.com/user/`（账号密码直接登录，**无 MFA 邮箱验证码**） |
| 年龄确认弹窗 | `div.yes a`，文字"是，我已满18岁"（首次访问出现，点击通过） |
| 广告弹窗 | 黑色红边框"【查看帮助文档】立刻自助解决99%的问题"，**位置循环滚动移动**，可能遮挡签到按钮/统计信息，必须移除 |
| 签到按钮 | "点击这里签到"（已签到显示"今天已经签到过啦"） |
| 统计信息弹窗 | 鼠标 hover/点击"统计信息"按钮触发：`总计签到N天 / 共获得流量X.X GiB / 上次签到于YYYY-MM-DD`；流量与天数以此为准 |
| 签到奖励 | 流量（GiB），非积分；每次 1~4 GiB |
| 结果通知 | SMTP 邮件发送流量明细到 SMTP_TO（免登录确认签到成败）；标题 `【SakuraFrp签到成功】时间` / `【SakuraFrp签到失败】时间` 一眼可辨成败；正文干净格式**不含验证过程日志** |
| 验证码 | GeeTest **九宫格点选**（AI 识别 9 格物品 + 参考图 → 点击匹配格 → 确认），比 ChmlFrp 的极验4代简单，单次运行约 50s |
| 定时 | workflow cron `5 16 * * *` = 北京时间每日 0:05 |

## 架构与执行流程

```text
GitHub Actions (cron 5 16 * * * = 北京 0:05)
  └─ main.py → automation.py (Playwright，CI 下 headless)
      1. 打开 https://www.natfrp.com/user/ → 填 #username/#password → 点 #login
      2. 年龄确认弹窗(如有) → 广告弹窗移除（JS 删 DOM + 兜底点"关闭"）
      3. 签到前：hover"统计信息"→ 读【共获得流量 / 总计签到N天】→ Escape 关闭
      4. 若已签到（"今天已经签到过啦"）→ 直接记为成功，本次获得 0.00 GiB
      5. 点"点击这里签到" → GeeTest 九宫格验证码 AI 识别点击 → reload
      6. 签到后：再读【共获得流量 / 总计签到N天】
      7. 本次获得流量 = 签到后共获得 − 签到前共获得（GiB，统一单位换算）
      8. 结果写入 sign_result.json
  └─ send_email.py → 读 sign_result.json → SMTP 发干净结果邮件（无日志）
```

## 部署步骤（对新账号 / 新仓库）

1. **Fork 本仓库**到目标 GitHub 账号。
2. **开启 Actions**：Fork 后定时任务默认禁用，必须在 Actions 页手动 Enable workflow 一次。
3. **配置 Secrets**（Settings → Secrets and variables → Actions → New repository secret）：

   | Secret | 必填 | 值 |
   |---|---|---|
   | `SAKURAFRP_USER` | ✅ | SakuraFrp 用户名 |
   | `SAKURAFRP_PASS` | ✅ | SakuraFrp 密码 |
   | `BASE_URL` | ✅ | OpenAI 兼容 API 地址，如 `https://dashscope.aliyuncs.com/compatible-mode/v1` |
   | `API_KEY` | ✅ | 视觉模型 API Key（通义千问 bailian.console.aliyun.com 获取） |
   | `MODEL` | ✅ | 多模态模型名，如 `qwen-vl-plus` |
   | `SMTP_HOST` | ✅ 推荐 | 结果邮件发件 SMTP，QQ 邮箱 `smtp.qq.com` |
   | `SMTP_USER` | ✅ 推荐 | 发件邮箱账号（QQ 邮箱） |
   | `SMTP_PASS` | ✅ 推荐 | 发件 SMTP 授权码（QQ 邮箱 SMTP/IMAP 授权码通用，非登录密码） |
   | `SMTP_TO` | ✅ 推荐 | 接收签到结果邮件的邮箱（免登录确认） |
   | `IMAGE_AS_BASE64` | ⬜ | 第三方适配器不支持图片 URL 时设 `true`（默认 false） |
   | `MAX_RETRIES` | ⬜ | 签到/验证码最大重试次数（默认 10） |
   | `CHROME_BINARY_PATH` | ⬜ | 本地运行指定 Chrome 路径；留空自动查找系统 Chrome |

4. **开启 QQ 邮箱 SMTP**：mail.qq.com → 设置 → 账户 → 开启 SMTP → 生成授权码。
5. **手动触发测试**：Actions → Run workflow → 约 1 分钟看 Success。
6. **验证**：查收 SMTP_TO 结果邮件（含签到前/后共获得流量、本次获得 GiB、累计天数）；或登录面板 hover"统计信息"核对。

## 必须遵守的约束 / 规范

- **账号密码、API Key、邮箱授权码只能放 GitHub Secrets**，严禁写入代码或公开仓库；脚本只通过环境变量读取。
- GeeTest 无法用纯 API 绕过，必须走浏览器自动化 + AI 视觉；识别失败要按 `MAX_RETRIES` 重试，模型 API 错误（`ModelApiError`）不可重试，直接终止退出。
- **流量数据以"统计信息"弹窗为准**（hover 触发），不要取页面其他卡片数值（有延迟/口径不同）。
- **本次获得流量 = 签到后 − 签到前**，单位统一 GiB（MiB/GB→÷1024，TiB/TB→×1024）。
- 每次修改脚本后，验证方式必须是从 Actions 真实运行 + 回读日志文字输出，不能只看 exit code。
- 邮件正文只放结果（状态/时间/前后流量/本次获得/天数/备注），**禁止附带验证过程日志或日志附件**。

## 关键实现细节（踩坑点与解决方案）

1. **广告弹窗滚动移动遮挡签到按钮/统计信息** → 每次关键操作前调用 `_close_ad_popup()`：JS 遍历 DOM 找 textContent 含"查看帮助文档/立刻自助解决"且 <200 字符的元素，向上追溯 fixed/absolute/zIndex≥100 的祖先并 remove；兜底点"关闭"按钮。
2. **统计信息读取** → `page.get_by_text("统计信息", exact=True).last.hover()` → `page.inner_text("body")` 正则提取 `总计签到(\d+)天`、`共获得流量([\d.]+)\s*(GiB|MiB|TiB|GB|MB|TB)?`、`上次签到于([\d\-]+)`；读完按 Escape 关闭 popover 防遮挡。
3. **已签到场景** → 页面出现"今天已经签到过啦"时直接判定成功，本次获得固定 `0.00 GiB`（避免再触发签到）。
4. **流量单位换算** → 统计统一折算 GiB 数值后再做减法，防止 MiB/GiB 混算错误。
5. **九宫格验证码** → `captcha_handler.py` 调视觉模型识别 9 格 + 参考图（索引10），按名称匹配点击格子，点 `.geetest_commit` 确认；模型 API 错误直接终止不刷新重试。
6. **年龄确认弹窗** → 登录后先点 `div.yes a`（"是，我已满18岁"），超时则忽略。
7. **本地运行优先系统 Chrome** → 不强制 `playwright install chromium`；`CHROME_BINARY_PATH` 留空时自动查找系统 Chrome。Actions 环境执行 `python -m playwright install-deps chromium` 装 Linux 依赖即可（不下载 Playwright 大包）。
8. **workflow 环境变量注入** → `env:` 必须与 `run:` 同级缩进，否则 Secrets 不注入，脚本会因缺 `SAKURAFRP_USER` 等抛 `ValueError`。
9. **send_email.py 兼容旧命名** → `SMTP_SERVER` / `EMAIL_USERNAME` / `EMAIL_PASSWORD` / `RECEIVER_EMAIL` 仍可回退使用，但新仓库统一用 `SMTP_*`。
10. **结果文件耦合** → automation.py 在**所有**失败路径（登录失败/跳转失败/签到失败/ModelApiError/异常/最外层兜底）都写 `sign_result.json`，send_email.py 只读该文件，保证失败也有邮件。
11. **Fork 后 cron 不跑** → Actions 页手动 Enable workflow；GitHub 会对 60 天不活动的 cron 自动暂停，保持仓库活跃。

## 排障速查（按日志关键字）

| 日志/报错 | 含义 | 处理 |
|---|---|---|
| `ValueError: 环境变量 SAKURAFRP_USER 未设置` | Secrets 没注入 | 检查 workflow env 缩进、Secrets 名称 |
| `未检测到 GeeTest 验证码窗口` | 验证码未弹出 | 检查按钮点击是否被弹窗遮挡；重试 |
| `模型 API 返回错误` / `ModelApiError` | 视觉模型 API 异常 | 检查 API_KEY/BASE_URL/MODEL；此类不可重试 |
| `读取统计信息失败` | 统计弹窗没读到 | 检查广告弹窗是否移除成功；确认 hover 选择器 |
| `本次签到获得：--` | 前后流量缺任一 | 看日志"统计信息: {...}"原始解析；确认弹窗文案 |
| `[邮件] 未完整配置 SMTP` | SMTP secrets 缺失 | 配置 SMTP_HOST/USER/PASS/TO |
| `登录页面元素加载超时` | 登录页未加载 | 检查网络/用户名密码；本地可设 HEADLESS=false 观察 |
| 截图乱码 | Actions 容器缺中文字体 | 当前不传截图；若调试截图需在 workflow 装 fonts-noto-cjk |

## 交付要求

- 交付物：可运行的 GitHub 仓库（main.py + automation.py + captcha_handler.py + config.py + human_simulator.py + send_email.py + requirements.txt + .github/workflows/sakurafrp_sign.yml + README + 本 SKILL）。
- 交付后必须让用户验证一次真实运行：手动 Run workflow → **查收 SMTP_TO 结果邮件**（核对"签到前/后共获得流量、本次获得 GiB、累计天数"与面板 hover"统计信息"一致，且时间戳为北京时间）。
- 若签到失败，要求用户提供 Actions 日志中 `统计信息: {...}` 与"签到结果已写入"段，据此精确定位（按钮文案/弹窗/验证码/单位），再改脚本重跑。
