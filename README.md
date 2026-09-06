# SakuraFrp 自动签到脚本

使用 Playwright 驱动浏览器，并通过 AI 视觉识别完成 SakuraFrp 九宫格验证码签到。

## 功能特性

- 自动登录 SakuraFrp 账户
- AI 视觉识别九宫格验证码
- 自动点击匹配的验证码格子
- 失败自动重试，默认最多 10 次
- 支持 GitHub Actions 定时执行
- 支持邮件通知和日志归档

## 本地运行

### 1. 环境准备

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

本项目默认优先使用本机已安装的 Chrome，不需要下载 ChromeDriver，也不强制执行 `playwright install chromium`。

如果本机没有 Chrome，或希望使用 Playwright 托管浏览器，可以执行：

```bash
python -m playwright install chromium
```

### 2. 配置环境变量

创建 `.env` 文件：

```env
SAKURAFRP_USER=your_username
SAKURAFRP_PASS=your_password

BASE_URL=https://api.example.com/v1
API_KEY=your_api_key
MODEL=your_model_name

MAX_RETRIES=10
HEADLESS=false
CHROME_BINARY_PATH=

# 是否将验证码图片转换为 base64（可选）
# 可接受：true/false, 1/0, yes/no, on/off
# 通过第三方适配器接入的服务可能不支持直接使用图片 URL，此时设为 true。
IMAGE_AS_BASE64=false
```

`CHROME_BINARY_PATH` 可选。留空时会自动查找系统 Chrome；如果你的 Chrome 不在默认位置，可以显式指定：

```env
CHROME_BINARY_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
```

Playwright 只复用 Chrome 可执行文件，不会读取你日常 Chrome 的用户目录、Cookie、历史记录或扩展。

### 3. 运行脚本

```bash
python main.py
```

## GitHub Actions 部署

工作流文件位于 `.github/workflows/sakurafrp_sign.yml`，默认每天北京时间 0:05 执行，也支持手动触发。

需要配置以下 Secrets：

| 名称 | 说明 |
| --- | --- |
| `SAKURAFRP_USER` | SakuraFrp 用户名 |
| `SAKURAFRP_PASS` | SakuraFrp 密码 |
| `BASE_URL` | OpenAI 兼容 API 地址 |
| `API_KEY` | API 密钥 |
| `MODEL` | 多模态模型名称 |

邮件通知为可选配置（推荐配置，签到结果一眼可辨）：

| 名称 | 说明 |
| --- | --- |
| `SMTP_HOST` | SMTP 服务器，QQ 邮箱填 `smtp.qq.com` |
| `SMTP_USER` | 发件邮箱（如 QQ 邮箱） |
| `SMTP_PASS` | 邮箱 SMTP 授权码（非登录密码） |
| `SMTP_TO` | 收件邮箱（签到结果邮件收件人） |

邮件标题格式：`【SakuraFrp签到成功】2026-09-07 00:05:06` / `【SakuraFrp签到失败】2026-09-07 00:05:06`（北京时间，免登录确认签到成败）。

> 兼容旧命名：`SMTP_SERVER` / `EMAIL_USERNAME` / `EMAIL_PASSWORD` / `RECEIVER_EMAIL` 仍可回退使用，但推荐统一用上面 `SMTP_*`。

Actions 使用 GitHub runner 自带 Chrome，并执行 `python -m playwright install-deps chromium` 安装 Linux 运行依赖，避免每次下载 Playwright Chromium 大包。

## 项目结构

```text
SakuraFrp-Qiandao/
├── .github/workflows/sakurafrp_sign.yml
├── automation.py          # Playwright 签到主流程
├── captcha_handler.py     # GeeTest 验证码识别和点击
├── config.py              # 环境变量和日志配置
├── human_simulator.py     # 简单人类操作模拟
├── main.py                # 程序入口
├── send_email.py          # 邮件通知
├── requirements.txt       # Python 依赖
└── README.md
```

## 配置说明

### 定时任务时间

修改 `.github/workflows/sakurafrp_sign.yml` 中的 cron 表达式：

```yaml
schedule:
  - cron: '5 16 * * *'  # UTC 16:05 = 北京时间 0:05
```

常用时间对照：
- `5 16 * * *` - 每天 0:05（北京时间）
- `0 16 * * *` - 每天 0:00（北京时间）
- `0 1 * * *` - 每天 9:00（北京时间）
- `0 13 * * *` - 每天 21:00（北京时间）

### AI 模型推荐

支持任何兼容 OpenAI API 的多模态模型：

- OpenAI: `gpt-4o`
- 阿里通义: `qwen-vl-plus`, `qwen-vl-max`
- 智谱 AI: `glm-4v`
- GitHub Copilot: 可通过第三方 OpenAI 兼容适配层接入
- ModelScope: 各种开源视觉模型

## 故障排查

### 验证码识别失败

尝试更换更强的视觉模型，或增加 `MAX_RETRIES`。模型需要支持图片输入，并兼容 OpenAI Chat Completions API。

### 模型返回非标准响应

脚本会记录完整响应结构。如果响应中包含 `error` 或 `errors`，会直接终止，因为刷新验证码无法修复模型 API 错误。

### Playwright 下载 Chromium 失败

如果出现 `timed out`、`ECONNRESET` 或 `Failed to download Chrome for Testing`，通常是网络到 Playwright/CDN 下载源不稳定。推荐直接使用系统 Chrome，并在 `.env` 中按需设置 `CHROME_BINARY_PATH`。

### 登录失败

检查 `SAKURAFRP_USER` 和 `SAKURAFRP_PASS` 是否正确，必要时关闭无头模式查看页面行为：

```env
HEADLESS=false
```

### 未收到邮件

确认邮箱开启 SMTP，并使用授权码或应用专用密码，不要直接使用普通登录密码。

## 注意事项

请勿频繁触发签到，避免被限流。妥善保管账号密码、API Key 和邮箱授权码。

## 相关链接

- [SakuraFrp 官网](https://www.natfrp.com/)
- [Playwright 文档](https://playwright.dev/python/)
- [GitHub Actions 文档](https://docs.github.com/en/actions)
- [copilot-api](https://github.com/caozhiyuan/copilot-api)
- [LiteLLM](https://github.com/BerriAI/litellm)

