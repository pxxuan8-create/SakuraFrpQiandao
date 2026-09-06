import json
import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone


def bj_now():
    """北京时间（UTC+8），精确到秒"""
    return datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')


def load_result():
    """
    读取 automation.py 写入的签到结果 sign_result.json。
    返回 dict（success/status/time/before_flow/gained_flow/days/after_flow/note）。
    """
    try:
        if os.path.exists("sign_result.json"):
            with open("sign_result.json", "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"读取 sign_result.json 失败: {e}")
    return None


def build_mail_body(result):
    """构造干净的结果邮件正文（无验证过程日志）"""
    status = result.get("status", "成功") if result.get("success") else "失败"
    time_str = result.get("time") or bj_now()
    before = result.get("before_flow") or "--"
    gained = result.get("gained_flow") or "--"
    days = result.get("days")
    days_str = f"{days} 天" if days is not None else "--"
    after = result.get("after_flow") or "--"
    note = result.get("note") or ""

    lines = [
        "SakuraFrp 每日自动签到",
        "==============================",
        f"签到状态：{status}",
        f"签到时间：{time_str}",
        f"签到前共获得流量：{before}",
        f"本次签到获得：{gained}",
        f"累计签到天数：{days_str}",
        f"签到后共获得流量：{after}",
    ]
    if note:
        lines.append(f"备注：{note}")
    lines.append("==============================")
    lines.append("(流量数据以页面'统计信息'为准)")
    return "\n".join(lines)


def send_log_email():
    """
    发送签到结果邮件（免登录确认签到成败）。
    标题：【SakuraFrp签到成功】时间 / 【SakuraFrp签到失败】时间
    环境变量：SMTP_HOST / SMTP_USER / SMTP_PASS / SMTP_TO（兼容旧命名回退）
    """
    smtp_host = os.getenv('SMTP_HOST') or os.getenv('SMTP_SERVER') or ''
    smtp_port = int(os.getenv('SMTP_PORT', '465'))
    sender_email = os.getenv('SMTP_USER') or os.getenv('EMAIL_USERNAME', '')
    sender_password = os.getenv('SMTP_PASS') or os.getenv('EMAIL_PASSWORD', '')
    receiver_email = os.getenv('SMTP_TO') or os.getenv('RECEIVER_EMAIL', sender_email)

    if not all([smtp_host, sender_email, sender_password, receiver_email]):
        print("邮件配置未完整设置，本次不发送（需 SMTP_HOST / SMTP_USER / SMTP_PASS / SMTP_TO）")
        print(f"[邮件] 邮件主题: 【SakuraFrp签到(成功/失败)】{bj_now()}")
        print(f"[邮件] 收件人应为: {receiver_email or '(未设置 SMTP_TO)'}")
        return False

    # 读取签到结果
    result = load_result()
    if result is None:
        print("未找到 sign_result.json，无法构造结果邮件")
        return False

    status_text = "成功" if result.get("success") else "失败"
    subject = f"【SakuraFrp签到{status_text}】{result.get('time') or bj_now()}"
    body = build_mail_body(result)

    try:
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = subject

        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port)
            server.starttls()
        with server:
            server.login(sender_email, sender_password)
            server.send_message(msg)

        print(f"邮件发送成功: {receiver_email}")
        print(f"[邮件] 主题: {subject}")
        print(f"[邮件] 正文:\n{body}")
        return True

    except Exception as e:
        print(f"邮件发送失败: {e}")
        return False


if __name__ == "__main__":
    send_log_email()
