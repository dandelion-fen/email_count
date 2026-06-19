"""
主题规范化模块
"""
from __future__ import annotations
import re
import unicodedata

# 需要去除的前缀模式（支持多层嵌套）
_PREFIX_PATTERN = re.compile(
    r'^[\s]*'
    r'(?:'
    r'Re|RE|re|Fw|FW|fw|Fwd|FWD|fwd'
    r'|回复|答复|转发'
    r')'
    r'[\s]*[:：][\s]*',
    re.UNICODE,
)


def normalize_subject(subject: str) -> str:
    """
    规范化邮件主题：
    1. 去除 Re:/RE:/回复:/答复:/Fw:/转发: 等前缀（支持多层）
    2. 统一全角/半角标点
    3. 去除多余空格
    4. 转小写
    """
    if not subject:
        return ""

    s = subject.strip()

    # 反复去除前缀直到稳定
    prev = None
    while prev != s:
        prev = s
        s = _PREFIX_PATTERN.sub("", s, count=1).strip()

    # 全角转半角
    s = _fullwidth_to_halfwidth(s)

    # 统一空白
    s = re.sub(r'\s+', ' ', s).strip()

    # 去除首尾标点空白
    s = s.strip("【】[]()（）ー- ")

    return s.lower()


def _fullwidth_to_halfwidth(text: str) -> str:
    """全角字符转半角"""
    result = []
    for char in text:
        code = ord(char)
        if 0xFF01 <= code <= 0xFF5E:
            result.append(chr(code - 0xFEE0))
        elif code == 0x3000:  # 全角空格
            result.append(' ')
        else:
            result.append(char)
    return ''.join(result)


def subjects_similar(s1: str, s2: str, threshold: float = 0.7) -> bool:
    """判断两个规范化后的主题是否相似"""
    n1 = normalize_subject(s1)
    n2 = normalize_subject(s2)
    if not n1 or not n2:
        return False
    if n1 == n2:
        return True

    # 简单 Jaccard 相似度（字符级别）
    set1 = set(n1.replace(" ", ""))
    set2 = set(n2.replace(" ", ""))
    if not set1 or not set2:
        return False
    intersection = set1 & set2
    union = set1 | set2
    similarity = len(intersection) / len(union)
    return similarity >= threshold


def extract_subject_prefix(subject: str) -> str:
    """提取被去除的前缀部分"""
    normalized = normalize_subject(subject)
    original_lower = subject.strip().lower()
    # 找到规范化内容在原始主题中的位置
    idx = original_lower.find(normalized)
    if idx > 0:
        return subject[:idx].strip()
    return ""


def has_reply_prefix(subject: str) -> bool:
    """检查主题是否以回复前缀开头"""
    s = subject.strip()
    patterns = [
        r'^Re\s*[:：]', r'^RE\s*[:：]', r'^re\s*[:：]',
        r'^回复\s*[:：]', r'^答复\s*[:：]',
    ]
    return any(re.match(p, s) for p in patterns)


def has_forward_prefix(subject: str) -> bool:
    """检查主题是否以转发前缀开头"""
    s = subject.strip()
    patterns = [
        r'^Fw\s*[:：]', r'^FW\s*[:：]', r'^Fwd\s*[:：]',
        r'^FWD\s*[:：]', r'^转发\s*[:：]',
    ]
    return any(re.match(p, s) for p in patterns)
