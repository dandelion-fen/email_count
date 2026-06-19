"""
MIME 邮件解析模块
"""
from __future__ import annotations

import email
import email.header
import email.utils
import hashlib
import re
from datetime import datetime
from email.message import Message
from typing import Optional

from bs4 import BeautifulSoup

from src.models import ParsedMessage, EmailAddress
from src.subject_normalizer import normalize_subject
from src.config import (
    BOUNCE_SENDERS, BOUNCE_SUBJECTS,
    AUTO_REPLY_HEADERS, AUTO_REPLY_SUBJECTS,
)
from src.utils import setup_logger

logger = setup_logger("mime_parser")


def _clean_header(value: str) -> str:
    """清理邮件头部值，去除多余空白"""
    if not value:
        return ""
    return str(value).strip()


def parse_mime_message(raw_bytes: bytes, folder: str = "",
                       uid: int = 0, my_email: str = "") -> ParsedMessage:
    """解析原始 MIME 邮件字节为 ParsedMessage"""
    msg = email.message_from_bytes(raw_bytes)
    parsed = ParsedMessage(folder=folder, uid=uid)

    # 头部字段
    parsed.message_id = _clean_header(msg.get("Message-ID", ""))
    parsed.in_reply_to = _clean_header(msg.get("In-Reply-To", ""))
    parsed.references_str = _clean_header(msg.get("References", ""))

    # 日期
    date_str = msg.get("Date", "")
    parsed.date_str = date_str
    parsed.date = _parse_date(date_str)

    # 主题
    parsed.subject = _decode_header(msg.get("Subject", ""))
    parsed.subject_normalized = normalize_subject(parsed.subject)

    # 地址
    parsed.from_addr = _parse_address(msg.get("From", ""))
    parsed.to_addrs = _parse_address_list(msg.get("To", ""))
    parsed.cc_addrs = _parse_address_list(msg.get("Cc", ""))
    reply_to = msg.get("Reply-To", "")
    if reply_to:
        parsed.reply_to_addr = _parse_address(reply_to)

    # 正文
    text_parts, html_parts, attachments = _extract_parts(msg)
    parsed.body_text = "\n".join(text_parts)
    if html_parts:
        parsed.body_html_text = "\n".join(_html_to_text(h) for h in html_parts)

    # 如果没有纯文本但有HTML转换结果，用HTML结果
    if not parsed.body_text.strip() and parsed.body_html_text.strip():
        parsed.body_text = parsed.body_html_text

    # 附件
    if attachments:
        parsed.has_attachments = True
        parsed.attachment_names = [a[0] for a in attachments]
        parsed.attachment_types = [a[1] for a in attachments]

    # 是否由当前用户发送
    if my_email:
        parsed.is_sent_by_me = (
            parsed.from_addr.email.lower() == my_email.lower()
        )

    # 自动回复检测
    parsed.is_auto_reply = _is_auto_reply(msg, parsed)

    # 退信检测
    parsed.is_bounce = _is_bounce(parsed)

    # 系统通知检测
    parsed.is_system_notification = _is_system_notification(parsed)

    # 内容哈希
    hash_input = f"{parsed.message_id}|{parsed.subject}|{parsed.body_text[:500]}"
    parsed.content_hash = hashlib.sha256(
        hash_input.encode("utf-8", errors="replace")).hexdigest()[:16]

    return parsed


def _decode_header(header_value: str) -> str:
    """解码 MIME 编码的邮件头"""
    if not header_value:
        return ""
    try:
        decoded_parts = email.header.decode_header(header_value)
        parts = []
        for content, charset in decoded_parts:
            if isinstance(content, bytes):
                encoding = charset or "utf-8"
                for enc in [encoding, "utf-8", "gbk", "gb2312", "gb18030", "latin-1"]:
                    try:
                        parts.append(content.decode(enc))
                        break
                    except (UnicodeDecodeError, LookupError):
                        continue
                else:
                    parts.append(content.decode("utf-8", errors="replace"))
            else:
                parts.append(str(content))
        return " ".join(parts).strip()
    except Exception:
        return str(header_value).strip()


def _parse_address(addr_str: str) -> EmailAddress:
    """解析单个邮箱地址"""
    if not addr_str:
        return EmailAddress()
    try:
        decoded_addr = _decode_header(addr_str)
        name, addr = email.utils.parseaddr(decoded_addr)
        name = _decode_header(name)
        return EmailAddress(email=addr.lower().strip(), name=name.strip())
    except Exception:
        return EmailAddress(email=addr_str.strip())


def _parse_address_list(addr_str: str) -> list[EmailAddress]:
    """解析多个邮箱地址"""
    if not addr_str:
        return []
    try:
        decoded_addr = _decode_header(addr_str)
        addrs = email.utils.getaddresses([decoded_addr])
        result = []
        for name, addr in addrs:
            name = _decode_header(name)
            if addr:
                result.append(EmailAddress(email=addr.lower().strip(), name=name.strip()))
        return result
    except Exception:
        return []


def _parse_date(date_str: str) -> Optional[datetime]:
    """解析邮件日期"""
    if not date_str:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(date_str)
        return parsed
    except Exception:
        # 尝试常见格式
        for fmt in [
            "%Y-%m-%d %H:%M:%S", "%a, %d %b %Y %H:%M:%S",
            "%d %b %Y %H:%M:%S",
        ]:
            try:
                return datetime.strptime(date_str.strip()[:25], fmt)
            except (ValueError, IndexError):
                continue
        return None


def _extract_parts(msg: Message) -> tuple[list[str], list[str], list[tuple[str, str]]]:
    """提取邮件的文本、HTML和附件部分"""
    text_parts = []
    html_parts = []
    attachments = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))

            if "attachment" in disposition.lower():
                filename = _decode_header(part.get_filename() or "未知附件")
                attachments.append((filename, content_type))
                continue

            if content_type == "text/plain":
                text = _decode_payload(part)
                if text:
                    text_parts.append(text)
            elif content_type == "text/html":
                html = _decode_payload(part)
                if html:
                    html_parts.append(html)
    else:
        content_type = msg.get_content_type()
        if content_type == "text/plain":
            text = _decode_payload(msg)
            if text:
                text_parts.append(text)
        elif content_type == "text/html":
            html = _decode_payload(msg)
            if html:
                html_parts.append(html)

    return text_parts, html_parts, attachments


def _decode_payload(part: Message) -> str:
    """解码邮件内容"""
    try:
        payload = part.get_payload(decode=True)
        if payload is None:
            return ""
        charset = part.get_content_charset() or "utf-8"
        for enc in [charset, "utf-8", "gbk", "gb2312", "gb18030", "latin-1"]:
            try:
                return payload.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue
        return payload.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _html_to_text(html: str) -> str:
    """将 HTML 转换为纯文本"""
    try:
        soup = BeautifulSoup(html, "lxml")
        # 移除 script 和 style
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        # 清理空行
        lines = [line.strip() for line in text.splitlines()]
        return "\n".join(line for line in lines if line)
    except Exception:
        try:
            soup = BeautifulSoup(html, "html.parser")
            return soup.get_text(separator="\n")
        except Exception:
            return re.sub(r'<[^>]+>', '', html)


def _is_auto_reply(msg: Message, parsed: ParsedMessage) -> bool:
    """检测是否为自动回复"""
    # 检查头部
    for header, values in AUTO_REPLY_HEADERS.items():
        header_val = msg.get(header, "")
        if header_val:
            if not values:  # 只要存在就判定
                return True
            for v in values:
                if v.lower() in header_val.lower():
                    return True

    # 检查 Return-Path
    return_path = msg.get("Return-Path", "").lower()
    if return_path and ("<>" == return_path.strip() or "mailer-daemon" in return_path):
        return True

    # 检查主题关键词
    subj = parsed.subject.lower()
    for kw in AUTO_REPLY_SUBJECTS:
        if kw in subj:
            # 简短正文 + 自动回复主题 = 自动回复
            body_len = len(parsed.body_text.strip())
            if body_len < 500:
                return True

    return False


def _is_bounce(parsed: ParsedMessage) -> bool:
    """检测是否为退信"""
    from_email = parsed.from_addr.email.lower()
    from_name = parsed.from_addr.name.lower()
    subj_lower = parsed.subject.lower()

    # 发件人检查
    for sender in BOUNCE_SENDERS:
        if sender in from_email or sender in from_name:
            return True

    # 主题检查
    for kw in BOUNCE_SUBJECTS:
        if kw in subj_lower:
            return True

    return False


def _is_system_notification(parsed: ParsedMessage) -> bool:
    """检测是否为系统通知"""
    from_email = parsed.from_addr.email.lower()
    system_senders = ["noreply", "no-reply", "system", "notification", "admin@"]
    for s in system_senders:
        if s in from_email:
            return True
    return False


def extract_new_content(body: str) -> tuple[str, str]:
    """分离当前回复内容和历史引用"""
    lines = body.split("\n")
    new_lines = []
    quote_lines = []
    in_quote = False

    quote_markers = [
        r'^>+\s*',                    # > 引用
        r'^-{3,}\s*原始邮件',          # --- 原始邮件
        r'^-{3,}\s*Original Message',
        r'^发件人[:：]',
        r'^From[:：]',
        r'^在\s+\d{4}',               # 在 2024-01-01
        r'^On\s+\w+,?\s+\w+',         # On Mon, Jan
        r'^\*{3}\s*',                  # *** 开头
        r'^_{3,}',                     # ___ 分割线
    ]

    for line in lines:
        if not in_quote:
            for pattern in quote_markers:
                if re.match(pattern, line.strip()):
                    in_quote = True
                    break
        if in_quote:
            quote_lines.append(line)
        else:
            new_lines.append(line)

    return "\n".join(new_lines).strip(), "\n".join(quote_lines).strip()
