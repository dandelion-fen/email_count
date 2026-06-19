"""
本地规则分析模块 — 不依赖任何外部 AI
"""
from __future__ import annotations

from src.config import POSITIVE_KEYWORDS, UNCERTAIN_KEYWORDS, NEGATIVE_KEYWORDS
from src.models import (
    RuleAnalysisResult, AdmissionIntent, ActionRequired,
    ReplyStatus, MyReplyStatus,
)
from src.mime_parser import extract_new_content


def analyze_reply_by_rules(reply_body: str, reply_status: ReplyStatus,
                           my_reply_status: MyReplyStatus = MyReplyStatus.UNCERTAIN) -> RuleAnalysisResult:
    """使用本地规则分析导师回复内容"""
    result = RuleAnalysisResult()

    if reply_status == ReplyStatus.NO:
        result.reply_summary = "未检索到导师本人或课题组针对套磁邮件的有效回复。"
        result.admission_intent = AdmissionIntent.NO_REPLY
        result.action_required = ActionRequired.CONSIDER_FOLLOWUP
        result.recommended_next_step = "可以考虑再次联系或等待"
        result.confidence = 0.9
        return result

    if reply_status == ReplyStatus.UNCERTAIN:
        result.reply_summary = "仅发现相关会话或我发出的回复邮件，未读取到导师原始回复正文，因此无法确认。"
        result.admission_intent = AdmissionIntent.UNCERTAIN
        result.action_required = ActionRequired.UNCERTAIN
        result.recommended_next_step = "建议人工检查邮箱确认"
        result.confidence = 0.3
        return result

    # 有真实回复，分析内容
    if not reply_body.strip():
        result.reply_summary = "导师回复正文为空或无法解析"
        result.admission_intent = AdmissionIntent.UNCERTAIN
        result.confidence = 0.2
        return result

    # 分离新回复和引用
    new_content, _ = extract_new_content(reply_body)
    text = new_content if new_content.strip() else reply_body
    text_lower = text.lower()

    # 关键词匹配
    pos_matches = []
    unc_matches = []
    neg_matches = []

    for kw in POSITIVE_KEYWORDS:
        if kw in text:
            pos_matches.append(kw)
    for kw in UNCERTAIN_KEYWORDS:
        if kw in text:
            unc_matches.append(kw)
    for kw in NEGATIVE_KEYWORDS:
        if kw in text:
            neg_matches.append(kw)

    # 提取证据句
    sentences = _split_sentences(text)
    evidence = []
    for sent in sentences:
        sent_stripped = sent.strip()
        if not sent_stripped or len(sent_stripped) < 4:
            continue
        for kw in POSITIVE_KEYWORDS + UNCERTAIN_KEYWORDS + NEGATIVE_KEYWORDS:
            if kw in sent_stripped:
                evidence.append(sent_stripped)
                break

    result.evidence_sentences = evidence[:5]

    # 判断招生意向
    if neg_matches:
        if "名额已满" in text or "已招满" in text:
            result.admission_intent = AdmissionIntent.QUOTA_FULL
        elif "方向不符" in text or "不太匹配" in text:
            result.admission_intent = AdmissionIntent.DIRECTION_MISMATCH
        elif "无法接收" in text or "不招生" in text:
            result.admission_intent = AdmissionIntent.REJECTED
        else:
            result.admission_intent = AdmissionIntent.REJECTED
        result.confidence = 0.7

    elif pos_matches:
        if "可以接收" in text or "有名额" in text:
            result.admission_intent = AdmissionIntent.ACCEPT_WITH_QUOTA
            result.confidence = 0.7
        elif "欢迎加入" in text:
            result.admission_intent = AdmissionIntent.WELCOME_JOIN
            result.confidence = 0.7
        elif "加微信" in text or "微信" in text:
            result.admission_intent = AdmissionIntent.ADDED_WECHAT
            result.confidence = 0.7
        elif "夏令营" in text:
            result.admission_intent = AdmissionIntent.SUGGEST_SUMMER_CAMP
            result.confidence = 0.7
        elif "预推免" in text:
            result.admission_intent = AdmissionIntent.SUGGEST_PRE_ADMISSION
            result.confidence = 0.7
        elif "面试" in text or "交流" in text or "线上" in text:
            result.admission_intent = AdmissionIntent.WILLING_TO_TALK
            result.confidence = 0.7
        elif "欢迎报名" in text or "欢迎申请" in text or "可以报名" in text:
            # 注意：欢迎报名 ≠ 明确接收
            result.admission_intent = AdmissionIntent.WELCOME_APPLY_NEED_EXAM
            result.confidence = 0.7
        elif "发一下材料" in text or "补充材料" in text:
            result.admission_intent = AdmissionIntent.NEED_MORE_MATERIAL
            result.confidence = 0.7
        else:
            result.admission_intent = AdmissionIntent.POLITE_NO_INTENT
            result.confidence = 0.5
    elif unc_matches:
        if "名额未定" in text or "还不确定" in text:
            result.admission_intent = AdmissionIntent.QUOTA_UNCERTAIN
        elif "等政策" in text:
            result.admission_intent = AdmissionIntent.WAIT_POLICY
        else:
            result.admission_intent = AdmissionIntent.POLITE_NO_INTENT
        result.confidence = 0.5
    else:
        result.admission_intent = AdmissionIntent.POLITE_NO_INTENT
        result.confidence = 0.4

    # 生成回复摘要
    summary_parts = []
    if new_content.strip():
        summary_text = new_content.strip()[:300]
        summary_parts.append(summary_text)
    result.reply_summary = "; ".join(summary_parts) if summary_parts else text[:300]

    # 判断行动建议
    result.action_required = _determine_action(
        result.admission_intent, my_reply_status)
    result.recommended_next_step = _recommend_step(
        result.admission_intent, result.action_required)

    return result


def _determine_action(intent: AdmissionIntent,
                      my_status: MyReplyStatus) -> ActionRequired:
    """根据招生意向确定需要采取的行动"""
    if intent in (AdmissionIntent.ACCEPT_WITH_QUOTA, AdmissionIntent.WELCOME_JOIN):
        if my_status == MyReplyStatus.REPLIED:
            return ActionRequired.ALREADY_REPLIED
        return ActionRequired.REPLY_NOW

    if intent == AdmissionIntent.ADDED_WECHAT:
        return ActionRequired.ADD_WECHAT

    if intent == AdmissionIntent.NEED_MORE_MATERIAL:
        return ActionRequired.SEND_MATERIAL

    if intent in (AdmissionIntent.WILLING_TO_TALK,
                  AdmissionIntent.WELCOME_APPLY_NEED_EXAM):
        if my_status == MyReplyStatus.REPLIED:
            return ActionRequired.ALREADY_REPLIED
        return ActionRequired.POLITE_REPLY

    if intent in (AdmissionIntent.SUGGEST_SUMMER_CAMP,
                  AdmissionIntent.SUGGEST_PRE_ADMISSION):
        return ActionRequired.WAIT_EXAM

    if intent in (AdmissionIntent.WAIT_POLICY, AdmissionIntent.WAIT_EXAM_RESULT,
                  AdmissionIntent.QUOTA_UNCERTAIN):
        return ActionRequired.WAIT_TEACHER

    if intent in (AdmissionIntent.QUOTA_FULL, AdmissionIntent.DIRECTION_MISMATCH,
                  AdmissionIntent.REJECTED):
        return ActionRequired.NO_ACTION

    if intent == AdmissionIntent.NO_REPLY:
        return ActionRequired.CONSIDER_FOLLOWUP

    return ActionRequired.UNCERTAIN


def _recommend_step(intent: AdmissionIntent, action: ActionRequired) -> str:
    """生成建议下一步"""
    recommendations = {
        ActionRequired.REPLY_NOW: "建议尽快回复导师，表达感谢并确认意向",
        ActionRequired.POLITE_REPLY: "建议礼貌回复，表达感谢和继续关注的意愿",
        ActionRequired.SEND_MATERIAL: "按导师要求准备并发送补充材料",
        ActionRequired.ADD_WECHAT: "按导师提供的微信号添加好友",
        ActionRequired.WAIT_TEACHER: "等待导师后续通知，期间可准备相关材料",
        ActionRequired.WAIT_EXAM: "关注夏令营/预推免报名通知，按时提交申请",
        ActionRequired.CONTACT_LATER: "在导师建议的时间再次联系",
        ActionRequired.ALREADY_REPLIED: "已回复，保持关注后续进展",
        ActionRequired.NO_ACTION: "该导师暂无可行性，可将精力转向其他导师",
        ActionRequired.CONSIDER_FOLLOWUP: "可以考虑再次发送邮件跟进",
        ActionRequired.UNCERTAIN: "建议人工查看邮件详情后决定",
    }
    return recommendations.get(action, "请人工查看")


def _split_sentences(text: str) -> list[str]:
    """中英文分句"""
    import re
    sentences = re.split(r'[。！？\n;；.!?]+', text)
    return [s.strip() for s in sentences if s.strip()]
