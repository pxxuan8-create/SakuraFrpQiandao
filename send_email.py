import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta, timezone


def bj_now():
    """北京时间（UTC+8），精确到秒"""
    return datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')


def send_log_email(log_file='checkin.log'):
    """
    发送签到结果邮件（免登录确认签到成败）。

    标题格式（一眼可辨成败）：
        【SakuraFrp签到成功】2026-09-07 00:05:06
        【SakuraFrp签到失败】2026-09-07 00:05:06

    环境变量（推荐命名，与 ChmlFrp 仓库一致）：
        SMTP_HOST / SMTP_USER / SMTP_PASS / SMTP_TO
    兼容旧命名（若未配置新命名则回退）：
        SMTP_SERVER / EMAIL_USERNAME / EMAIL_PASSWORD / RECEIVER_EMAIL
    """
    # 从环境变量读取配置（优先新命名，回退旧命名）
    smtp_host = os.getenv('SMTP_HOST') or os.getenv('SMTP_SERVER') or ''
    smtp_port = int(os.getenv('SMTP_PORT', '465'))
    sender_email = os.getenv('SMTP_USER') or os.getenv('EMAIL_USERNAME', '')
    sender_password = os.getenv('SMTP_PASS') or os.getenv('EMAIL_PASSWORD', '')
    receiver_email = os.getenv('SMTP_TO') or os.getenv('RECEIVER_EMAIL', sender_email)

    # 检查配置
    if not all([smtp_host, sender_email, sender_password, receiver_email]):
        print("邮件配置未完整设置，本次不发送（需 SMTP_HOST / SMTP_USER / SMTP_PASS / SMTP_TO）")
        print(f"[邮件] 邮件主题: 【SakuraFrp签到(成功/失败)】{bj_now()}")
        print(f"[邮件] 收件人应为: {receiver_email or '(未设置 SMTP_TO)'}")
        return False

    try:
        # 读取日志内容
        log_content = ""
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                log_content = f.read()
        else:
            log_content = "日志文件不存在"

        # 判断签到是否成功（自动化脚本成功时会输出"签到流程完成"）
        is_success = ("签到流程完成" in log_content) or ("验证码验证成功" in log_content)
        status_text = "成功" if is_success else "失败"

        # 标题：一眼可辨成败，含北京时间
        subject = f"【SakuraFrp签到{status_text}】{bj_now()}"

        # 邮件正文（简洁 + 关键日志）
        log_tail = log_content[-1500:] if len(log_content) > 1500 else log_content
        body = (
            "SakuraFrp 每日自动签到\n"
            "==============================\n"
            f"签到状态：{status_text}\n"
            f"签到时间：{bj_now()}\n"
            "==============================\n"
            "日志内容：\n"
            f"{log_tail}\n"
            "==============================\n"
            "(此邮件由自动签到系统发送)"
        )

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        # 附加完整日志
        if os.path.exists(log_file):
            with open(log_file, 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename= {os.path.basename(log_file)}')
            msg.attach(part)

        # 发送
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port)
            server.starttls()
        with server:
            server.login(sender_email, sender_password)
            server.send_message(msg)

        print(f"邮件发送成功: {receiver_email}")
        return True

    except Exception as e:
        print(f"邮件发送失败: {e}")
        return False


if __name__ == "__main__":
    send_log_email()
