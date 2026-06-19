"""
通用工具函数
"""
from __future__ import annotations

import hashlib
import logging
import re
import sys
from pathlib import Path

from src.config import PHONE_PATTERN, ID_CARD_PATTERN


def setup_logger(name: str, log_file: str | None = None) -> logging.Logger:
    """创建安全的日志记录器，自动过滤敏感信息"""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台输出
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    ch.addFilter(SensitiveFilter())
    logger.addHandler(ch)

    # 文件输出
    if log_file:
        from src.config import LOG_DIR
        fh = logging.FileHandler(LOG_DIR / log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        fh.addFilter(SensitiveFilter())
        logger.addHandler(fh)

    return logger


class SensitiveFilter(logging.Filter):
    """过滤日志中的敏感信息"""

    _patterns = [
        (re.compile(r'(授权码|auth_code|password|passwd|token)\s*[:=]\s*\S+', re.IGNORECASE),
         r'\1=***REDACTED***'),
        (re.compile(r'(sk-[a-zA-Z0-9]{10,})', re.IGNORECASE),
         '***API_KEY***'),
        (re.compile(PHONE_PATTERN), '***PHONE***'),
        (re.compile(ID_CARD_PATTERN), '***ID_CARD***'),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        msg = str(record.msg)
        for pattern, replacement in self._patterns:
            msg = pattern.sub(replacement, msg)
        record.msg = msg
        return True


def content_hash(text: str) -> str:
    """计算内容哈希"""
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def safe_str(value, default: str = "") -> str:
    """安全转换为字符串"""
    if value is None:
        return default
    return str(value)


def truncate(text: str, max_len: int = 200) -> str:
    """截断文本"""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def is_academic_email(email: str) -> bool:
    """判断是否为学术邮箱"""
    from src.config import ACADEMIC_DOMAINS
    email_lower = email.lower()
    return any(domain in email_lower for domain in ACADEMIC_DOMAINS)


def normalize_email(email: str) -> str:
    """规范化邮箱地址"""
    return email.strip().lower()


def format_datetime(dt) -> str:
    """格式化日期时间"""
    if dt is None:
        return ""
    if hasattr(dt, "strftime"):
        return dt.strftime("%Y-%m-%d %H:%M")
    return str(dt)


def sanitize_for_excel(value: str) -> str:
    """防止 Excel 公式注入"""
    if isinstance(value, str) and value and value[0] in ('=', '+', '-', '@'):
        return "'" + value
    return value
