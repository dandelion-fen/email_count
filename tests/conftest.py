"""
测试夹具 — 匿名邮件数据
"""
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import pytest
import os
import sqlite3

# 当前用户邮箱
MY_EMAIL = "test_user@163.com"


def make_email(from_addr: str = "teacher@example.edu.cn",
               from_name: str = "张教授",
               to_addr: str = MY_EMAIL,
               to_name: str = "杜同学",
               subject: str = "Re: 保研自荐",
               body: str = "欢迎报名",
               date: str = "Thu, 01 Jun 2025 10:00:00 +0800",
               message_id: str = "<msg001@example.edu.cn>",
               in_reply_to: str = "",
               references: str = "",
               content_type: str = "text/plain",
               charset: str = "utf-8",
               auto_submitted: str = "",
               is_html: bool = False) -> bytes:
    """创建匿名测试邮件"""
    if is_html:
        msg = MIMEText(body, "html", charset)
    else:
        msg = MIMEText(body, "plain", charset)

    msg["From"] = f"{from_name} <{from_addr}>"
    msg["To"] = f"{to_name} <{to_addr}>"
    msg["Subject"] = subject
    msg["Date"] = date
    msg["Message-ID"] = message_id

    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references
    if auto_submitted:
        msg["Auto-Submitted"] = auto_submitted

    return msg.as_bytes()


def make_gbk_email(subject: str = "保研自荐",
                   body: str = "您好", **kwargs) -> bytes:
    """创建 GBK 编码的邮件"""
    msg = MIMEText(body.encode("gbk"), "plain", "gbk")
    from email.header import Header
    msg["Subject"] = Header(subject, "gbk")
    msg["From"] = kwargs.get("from_addr", f"student <{MY_EMAIL}>")
    msg["To"] = kwargs.get("to_addr", "teacher <prof@example.edu.cn>")
    msg["Date"] = kwargs.get("date", "Mon, 02 Jun 2025 09:00:00 +0800")
    msg["Message-ID"] = kwargs.get("message_id", "<gbk001@163.com>")
    return msg.as_bytes()


def make_multipart_email(text_body: str = "纯文本内容",
                         html_body: str = "<p>HTML内容</p>",
                         **kwargs) -> bytes:
    """创建 multipart 邮件"""
    msg = MIMEMultipart("alternative")
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    msg["From"] = kwargs.get("from_addr", f"teacher <prof@example.edu.cn>")
    msg["To"] = kwargs.get("to_addr", f"student <{MY_EMAIL}>")
    msg["Subject"] = kwargs.get("subject", "Re: 保研自荐")
    msg["Date"] = kwargs.get("date", "Wed, 03 Jun 2025 14:00:00 +0800")
    msg["Message-ID"] = kwargs.get("message_id", "<multi001@example.edu.cn>")
    return msg.as_bytes()


# ── 预定义测试场景 ──

# 场景1: 首次套磁无回复
SENT_NO_REPLY = make_email(
    from_addr=MY_EMAIL, from_name="杜子坤", to_addr="prof_wang@pku.edu.cn",
    to_name="王教授", subject="【硕士保研自荐】湖北工业大学-微电子科学与工程-杜子坤-专业前3%-附简历",
    body="尊敬的王教授您好，我是湖北工业大学微电子科学与工程专业的杜子坤...",
    date="Mon, 01 Apr 2025 09:00:00 +0800",
    message_id="<sent001@163.com>",
)

# 场景2: 导师回复后我已回复
TEACHER_REPLY_POSITIVE = make_email(
    from_addr="prof_li@tsinghua.edu.cn", from_name="李教授",
    to_addr=MY_EMAIL, to_name="杜同学",
    subject="Re: 硕士保研自荐",
    body="杜同学你好，欢迎报名我们夏令营，可以先加微信详聊。",
    date="Tue, 02 Apr 2025 15:00:00 +0800",
    message_id="<reply001@tsinghua.edu.cn>",
    in_reply_to="<sent002@163.com>",
)

MY_REPLY_TO_TEACHER = make_email(
    from_addr=MY_EMAIL, from_name="杜子坤",
    to_addr="prof_li@tsinghua.edu.cn", to_name="李教授",
    subject="Re: Re: 硕士保研自荐",
    body="李教授您好，非常感谢！我的微信号是...",
    date="Tue, 02 Apr 2025 18:00:00 +0800",
    message_id="<sent003@163.com>",
    in_reply_to="<reply001@tsinghua.edu.cn>",
)

# 场景3: 导师回复但我未回复
TEACHER_REPLY_UNREPLIED = make_email(
    from_addr="prof_chen@zju.edu.cn", from_name="陈教授",
    to_addr=MY_EMAIL,
    subject="Re: 保研自荐-杜子坤",
    body="杜同学你好，欢迎申请，请发一下你的成绩单和推荐信。",
    date="Wed, 03 Apr 2025 10:00:00 +0800",
    message_id="<reply002@zju.edu.cn>",
    in_reply_to="<sent004@163.com>",
)

# 场景4: 只有我发出的 Re: 但没有导师原始来信
MY_RE_NO_TEACHER = make_email(
    from_addr=MY_EMAIL, from_name="杜子坤",
    to_addr="prof_zhang@fudan.edu.cn",
    subject="Re: 硕士保研自荐",
    body="张教授您好，请问您是否收到我之前的邮件？",
    date="Fri, 05 Apr 2025 09:00:00 +0800",
    message_id="<sent005@163.com>",
)

# 场景5: 名额已满
TEACHER_REPLY_FULL = make_email(
    from_addr="prof_zhao@sjtu.edu.cn", from_name="赵教授",
    to_addr=MY_EMAIL,
    subject="Re: 硕士保研自荐",
    body="同学你好，感谢你的关注，但今年的名额已满，建议联系其他老师。",
    date="Mon, 08 Apr 2025 11:00:00 +0800",
    message_id="<reply003@sjtu.edu.cn>",
)

# 场景6: 欢迎报名但仍需考核
TEACHER_WELCOME_EXAM = make_email(
    from_addr="prof_sun@nju.edu.cn", from_name="孙教授",
    to_addr=MY_EMAIL,
    subject="回复：保研自荐",
    body="杜同学你好，欢迎报名我们的预推免，通过考核后可以接收。",
    date="Tue, 09 Apr 2025 14:00:00 +0800",
    message_id="<reply004@nju.edu.cn>",
)

# 场景7: 加微信
TEACHER_WECHAT = make_email(
    from_addr="prof_wu@ustc.edu.cn", from_name="吴教授",
    to_addr=MY_EMAIL,
    subject="Re: 硕士保研自荐",
    body="你好，可以加微信详聊，我的微信号是 wuprof888",
    date="Wed, 10 Apr 2025 09:00:00 +0800",
    message_id="<reply005@ustc.edu.cn>",
)

# 场景8: 自动回复
AUTO_REPLY = make_email(
    from_addr="prof_liu@hit.edu.cn", from_name="刘教授",
    to_addr=MY_EMAIL,
    subject="自动回复：已收到您的邮件",
    body="您好，我目前不在办公室，将于7月1日后回复您的邮件。",
    date="Thu, 11 Apr 2025 08:00:00 +0800",
    message_id="<auto001@hit.edu.cn>",
    auto_submitted="auto-replied",
)

# 场景9: 退信
BOUNCE_EMAIL = make_email(
    from_addr="mailer-daemon@163.com", from_name="Mail Delivery Subsystem",
    to_addr=MY_EMAIL,
    subject="Delivery Status Notification (Failure)",
    body="Your message to wrong_addr@nonexist.edu.cn was not delivered.",
    date="Fri, 12 Apr 2025 06:00:00 +0800",
    message_id="<bounce001@163.com>",
)

# 场景10: 导师修改主题回复
TEACHER_CHANGED_SUBJECT = make_email(
    from_addr="prof_ma@bit.edu.cn", from_name="马教授",
    to_addr=MY_EMAIL,
    subject="关于你的申请",
    body="杜同学你好，看了你的简历，欢迎参加我们的夏令营面试。",
    date="Mon, 15 Apr 2025 16:00:00 +0800",
    message_id="<reply006@bit.edu.cn>",
    references="<sent010@163.com>",
)

# 场景11: 导师使用另一邮箱回复
TEACHER_ALT_EMAIL = make_email(
    from_addr="qian_personal@gmail.com", from_name="钱教授",
    to_addr=MY_EMAIL,
    subject="Re: 硕士保研自荐",
    body="你好，我用私人邮箱回复你，有名额可以接收，请联系我。",
    date="Tue, 16 Apr 2025 20:00:00 +0800",
    message_id="<reply007@gmail.com>",
    in_reply_to="<sent011@163.com>",
)

# 场景12: 同姓不同导师
SENT_TO_ZHANG_A = make_email(
    from_addr=MY_EMAIL, from_name="杜子坤",
    to_addr="zhang_wei@pku.edu.cn", to_name="张伟教授",
    subject="【硕士保研自荐】湖北工业大学-杜子坤",
    body="尊敬的张伟教授...",
    date="Wed, 17 Apr 2025 09:00:00 +0800",
    message_id="<sent012@163.com>",
)

SENT_TO_ZHANG_B = make_email(
    from_addr=MY_EMAIL, from_name="杜子坤",
    to_addr="zhang_wei@tsinghua.edu.cn", to_name="张伟教授",
    subject="【硕士保研自荐】湖北工业大学-杜子坤",
    body="尊敬的张伟教授...",
    date="Wed, 17 Apr 2025 10:00:00 +0800",
    message_id="<sent013@163.com>",
)


@pytest.fixture
def temp_db(tmp_path):
    """创建临时测试数据库"""
    db_path = str(tmp_path / "test.db")
    from src.database import init_db, reset_connection
    reset_connection(db_path)
    init_db(db_path)
    yield db_path
    from src.database import close_db
    close_db()


@pytest.fixture
def populated_db(temp_db):
    """填充了测试数据的数据库"""
    from src.database import (
        upsert_account, upsert_folder, insert_message,
        get_connection, reset_connection,
    )
    from src.mime_parser import parse_mime_message
    from src.subject_normalizer import normalize_subject

    reset_connection(temp_db)

    account_id = upsert_account(MY_EMAIL, db_path=temp_db)
    sent_folder_id = upsert_folder(account_id, "已发送", folder_type="sent", db_path=temp_db)
    inbox_folder_id = upsert_folder(account_id, "收件箱", folder_type="inbox", db_path=temp_db)

    # 添加测试邮件
    test_emails = [
        (SENT_NO_REPLY, sent_folder_id, 1),
        (TEACHER_REPLY_POSITIVE, inbox_folder_id, 2),
        (MY_REPLY_TO_TEACHER, sent_folder_id, 3),
        (TEACHER_REPLY_UNREPLIED, inbox_folder_id, 4),
        (MY_RE_NO_TEACHER, sent_folder_id, 5),
        (TEACHER_REPLY_FULL, inbox_folder_id, 6),
        (TEACHER_WELCOME_EXAM, inbox_folder_id, 7),
        (TEACHER_WECHAT, inbox_folder_id, 8),
        (AUTO_REPLY, inbox_folder_id, 9),
        (BOUNCE_EMAIL, inbox_folder_id, 10),
        (SENT_TO_ZHANG_A, sent_folder_id, 11),
        (SENT_TO_ZHANG_B, sent_folder_id, 12),
    ]

    for raw_bytes, folder_id, uid in test_emails:
        parsed = parse_mime_message(raw_bytes, folder="test", uid=uid, my_email=MY_EMAIL)
        insert_message({
            "account_id": account_id,
            "folder_id": folder_id,
            "uid": uid,
            "message_id": parsed.message_id,
            "in_reply_to": parsed.in_reply_to,
            "references_str": parsed.references_str,
            "date": parsed.date.isoformat() if parsed.date else "",
            "subject": parsed.subject,
            "subject_normalized": parsed.subject_normalized,
            "from_email": parsed.from_addr.email,
            "from_name": parsed.from_addr.name,
            "to_addrs": "; ".join(f"{a.name} <{a.email}>" for a in parsed.to_addrs),
            "cc_addrs": "",
            "reply_to": "",
            "body_text": parsed.body_text,
            "body_html_text": parsed.body_html_text,
            "has_attachments": int(parsed.has_attachments),
            "attachment_names": "",
            "attachment_types": "",
            "is_sent_by_me": int(parsed.is_sent_by_me),
            "is_auto_reply": int(parsed.is_auto_reply),
            "is_bounce": int(parsed.is_bounce),
            "is_system_notification": int(parsed.is_system_notification),
            "content_hash": parsed.content_hash,
        }, db_path=temp_db)

    yield temp_db, account_id
