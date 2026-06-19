"""
隐私保护工具模块
"""
from __future__ import annotations

import re
from src.config import PHONE_PATTERN, ID_CARD_PATTERN, ADDRESS_PATTERN


def mask_phone(text: str) -> str:
    """隐藏手机号"""
    return re.sub(PHONE_PATTERN, "***手机号***", text)


def mask_id_card(text: str) -> str:
    """隐藏身份证号"""
    return re.sub(ID_CARD_PATTERN, "***身份证号***", text)


def mask_address(text: str) -> str:
    """隐藏家庭住址"""
    return re.sub(ADDRESS_PATTERN, "***地址***", text)


def mask_email_in_text(text: str, keep_emails: set[str] | None = None) -> str:
    """隐藏文本中的邮箱地址（保留指定邮箱）"""
    keep = keep_emails or set()

    def _replace(m):
        email = m.group(0)
        if email.lower() in {e.lower() for e in keep}:
            return email
        user, domain = email.split("@", 1)
        if len(user) > 2:
            return user[0] + "***@" + domain
        return "***@" + domain

    return re.sub(r'[\w.+-]+@[\w.-]+\.\w+', _replace, text)


def mask_sensitive(text: str, keep_emails: set[str] | None = None) -> str:
    """综合隐藏所有敏感信息"""
    text = mask_phone(text)
    text = mask_id_card(text)
    text = mask_address(text)
    text = mask_email_in_text(text, keep_emails)
    return text


def prepare_text_for_ai(text: str, user_email: str = "", max_length: int = 3000) -> str:
    """准备发送给 AI 的文本，隐藏敏感信息并截断"""
    keep = {user_email} if user_email else set()
    text = mask_sensitive(text, keep_emails=keep)
    if len(text) > max_length:
        text = text[:max_length] + "\n...(已截断)"
    return text


def get_privacy_warnings(text: str) -> list[str]:
    """检查文本中包含哪些隐私信息"""
    warnings = []
    if re.search(PHONE_PATTERN, text):
        warnings.append("包含手机号码")
    if re.search(ID_CARD_PATTERN, text):
        warnings.append("包含身份证号码")
    emails = re.findall(r'[\w.+-]+@[\w.-]+\.\w+', text)
    if emails:
        warnings.append(f"包含 {len(emails)} 个邮箱地址")
    return warnings
