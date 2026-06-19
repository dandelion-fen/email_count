"""
套磁邮件识别模块
"""
from __future__ import annotations

import re
from src.config import DEFAULT_SUBJECT_KEYWORDS, DEFAULT_BODY_KEYWORDS, ACADEMIC_DOMAINS
from src.models import ContactCandidate
from src.utils import is_academic_email


def identify_contact_email(msg: dict,
                           subject_keywords: list[str] | None = None,
                           body_keywords: list[str] | None = None) -> ContactCandidate:
    """识别是否为套磁候选邮件"""
    subj_kws = subject_keywords or DEFAULT_SUBJECT_KEYWORDS
    body_kws = body_keywords or DEFAULT_BODY_KEYWORDS

    candidate = ContactCandidate(message_db_id=msg.get("id", 0))
    score = 0.0
    reasons = []

    subject = msg.get("subject", "")
    subject_norm = msg.get("subject_normalized", "")
    body = msg.get("body_text", "") or ""
    is_sent = msg.get("is_sent_by_me", False)
    to_addrs = msg.get("to_addrs", "")
    has_attach = msg.get("has_attachments", False)
    attach_names = msg.get("attachment_names", "")

    # 1. 主题关键词匹配
    subj_matches = []
    for kw in subj_kws:
        if kw.lower() in subject.lower() or kw.lower() in subject_norm.lower():
            subj_matches.append(kw)
    if subj_matches:
        score += min(len(subj_matches) * 0.15, 0.45)
        reasons.append(f"主题包含关键词: {', '.join(subj_matches[:3])}")

    # 2. 典型套磁主题模式
    pattern = r'【?硕士?保研自荐】?.{0,10}(大学|学院|研究).{0,10}(专业|方向|工程|科学)'
    if re.search(pattern, subject):
        score += 0.3
        reasons.append("主题匹配典型套磁格式")

    # 排名模式
    rank_pattern = r'(专业前|排名|前)\s*[\d.]+[%％]?|排名\s*\d+\s*/\s*\d+'
    if re.search(rank_pattern, subject) or re.search(rank_pattern, body[:500]):
        score += 0.1
        reasons.append("包含专业排名信息")

    # 3. 正文关键词
    body_preview = body[:1000].lower()
    body_matches = []
    for kw in body_kws:
        if kw in body_preview:
            body_matches.append(kw)
    if body_matches:
        score += min(len(body_matches) * 0.08, 0.3)
        reasons.append(f"正文包含关键词: {', '.join(body_matches[:3])}")

    # 4. 正文身份介绍特征
    intro_patterns = [
        r'我是.{0,20}(大学|学院|专业)',
        r'(本科|在读).{0,10}(学生|同学)',
        r'(成绩|绩点|GPA).{0,10}[\d.]',
        r'自荐|自我介绍|个人简介',
    ]
    for pat in intro_patterns:
        if re.search(pat, body[:800]):
            score += 0.08
            reasons.append("正文包含身份介绍")
            break

    # 5. 附件是否为简历
    if has_attach:
        attach_lower = attach_names.lower()
        if any(kw in attach_lower for kw in ["简历", "cv", "resume", "个人简介"]):
            score += 0.15
            reasons.append("附件包含简历")
        elif attach_lower:
            score += 0.05
            reasons.append("包含附件")

    # 6. 收件人是否为学术邮箱
    if is_sent and to_addrs:
        academic = False
        for domain in ACADEMIC_DOMAINS:
            if domain in to_addrs.lower():
                academic = True
                break
        if academic:
            score += 0.1
            reasons.append("发送至学术机构邮箱")

    # 7. 是否由当前用户发送（套磁通常是我发出的）
    if is_sent:
        score += 0.05
        reasons.append("由当前用户发送")

    # 排除退信和自动回复
    if msg.get("is_bounce"):
        score = 0
        reasons = ["退信"]
    elif msg.get("is_auto_reply"):
        score *= 0.3
        reasons.append("自动回复（降低置信度）")
    elif msg.get("is_system_notification"):
        score *= 0.5
        reasons.append("系统通知（降低置信度）")

    # 判定
    candidate.confidence = min(score, 1.0)
    candidate.reasons = reasons

    if score >= 0.4:
        candidate.is_contact_email = True
        candidate.needs_review = score < 0.6
    elif score >= 0.2:
        candidate.is_contact_email = True
        candidate.needs_review = True
        candidate.reasons.append("低置信度，需人工确认")
    else:
        candidate.is_contact_email = False

    return candidate


def batch_identify(messages: list[dict],
                   subject_keywords: list[str] | None = None,
                   body_keywords: list[str] | None = None) -> list[ContactCandidate]:
    """批量识别套磁候选邮件"""
    results = []
    for msg in messages:
        candidate = identify_contact_email(msg, subject_keywords, body_keywords)
        results.append(candidate)
    return results
