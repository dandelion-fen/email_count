"""
Pydantic 数据模型定义
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ────────────────────── 枚举 ──────────────────────

class FolderType(str, enum.Enum):
    INBOX = "inbox"
    SENT = "sent"
    DRAFTS = "drafts"
    SPAM = "spam"
    TRASH = "trash"
    ARCHIVE = "archive"
    OTHER = "other"


class ReplyStatus(str, enum.Enum):
    YES = "是"
    NO = "否"
    UNCERTAIN = "无法确认"


class MyReplyStatus(str, enum.Enum):
    REPLIED = "已回复"
    NOT_REPLIED = "未回复"
    NO_NEED = "无需回复"
    UNCERTAIN = "无法确认"


class AdmissionIntent(str, enum.Enum):
    ACCEPT_WITH_QUOTA = "明确愿意接收，且有招生名额"
    WELCOME_JOIN = "明确欢迎加入或重点考虑"
    WELCOME_APPLY_NEED_EXAM = "欢迎报名，但仍需参加考核"
    SUGGEST_SUMMER_CAMP = "建议参加夏令营"
    SUGGEST_PRE_ADMISSION = "建议参加预推免"
    WILLING_TO_TALK = "愿意进一步交流或安排面试"
    ADDED_WECHAT = "已添加微信，转入其他方式沟通"
    NEED_MORE_MATERIAL = "需要补充材料后再判断"
    QUOTA_UNCERTAIN = "暂时无法确定招生名额"
    WAIT_POLICY = "需要等待学院招生政策"
    WAIT_EXAM_RESULT = "需要等待夏令营或预推免考核结果"
    POLITE_NO_INTENT = "礼貌回复，但未表达明确接收意向"
    QUOTA_FULL = "名额已满"
    DIRECTION_MISMATCH = "研究方向不匹配"
    REJECTED = "明确拒绝"
    NO_REPLY = "尚未回复"
    UNCERTAIN = "无法确认"


class ActionRequired(str, enum.Enum):
    REPLY_NOW = "需要立即回复"
    POLITE_REPLY = "建议礼貌回复"
    SEND_MATERIAL = "需要补充材料"
    ADD_WECHAT = "需要添加微信"
    WAIT_TEACHER = "等待导师后续通知"
    WAIT_EXAM = "等待夏令营或预推免结果"
    CONTACT_LATER = "在指定时间再次联系"
    ALREADY_REPLIED = "已经回复，无需重复回复"
    NO_ACTION = "暂时无需回复"
    CONSIDER_FOLLOWUP = "尚未回复，可考虑跟进"
    UNCERTAIN = "无法确认"


class MessageRole(str, enum.Enum):
    SENT_FIRST = "首次套磁"
    SENT_FOLLOWUP = "补发邮件"
    SENT_SECOND = "第二封套磁"
    SENT_SUPPLEMENT = "补充材料"
    SENT_REPLY = "我的回复"
    SENT_THANKS = "感谢信"
    RECEIVED_REPLY = "导师回复"
    RECEIVED_AUTO = "自动回复"
    RECEIVED_BOUNCE = "退信"
    RECEIVED_OTHER = "其他收件"


class ThreadMatchMethod(str, enum.Enum):
    MESSAGE_ID = "Message-ID"
    REFERENCES = "References"
    IN_REPLY_TO = "In-Reply-To"
    SUBJECT = "主题匹配"
    SENDER_RECEIVER = "收发件人匹配"
    TIME_PROXIMITY = "时间接近"
    BODY_QUOTE = "正文引用"


class AnalysisType(str, enum.Enum):
    RULE = "rule"
    AI = "ai"


# ────────────────────── 数据模型 ──────────────────────

class EmailAddress(BaseModel):
    """邮箱地址"""
    email: str = ""
    name: str = ""


class ParsedMessage(BaseModel):
    """解析后的邮件"""
    folder: str = ""
    uid: int = 0
    message_id: str = ""
    in_reply_to: str = ""
    references_str: str = ""
    date: Optional[datetime] = None
    date_str: str = ""
    from_addr: EmailAddress = Field(default_factory=EmailAddress)
    to_addrs: list[EmailAddress] = Field(default_factory=list)
    cc_addrs: list[EmailAddress] = Field(default_factory=list)
    reply_to_addr: EmailAddress = Field(default_factory=EmailAddress)
    subject: str = ""
    subject_normalized: str = ""
    body_text: str = ""
    body_html_text: str = ""
    has_attachments: bool = False
    attachment_names: list[str] = Field(default_factory=list)
    attachment_types: list[str] = Field(default_factory=list)
    is_sent_by_me: bool = False
    is_auto_reply: bool = False
    is_bounce: bool = False
    is_system_notification: bool = False
    content_hash: str = ""


class TeacherInfo(BaseModel):
    """导师信息"""
    id: int = 0
    name: str = ""
    institution: str = ""
    emails: list[str] = Field(default_factory=list)
    primary_email: str = ""
    first_sent_at: Optional[datetime] = None
    last_sent_at: Optional[datetime] = None
    send_count: int = 0
    confidence: float = 0.0
    needs_review: bool = False
    review_reasons: list[str] = Field(default_factory=list)


class ThreadInfo(BaseModel):
    """会话线程"""
    id: int = 0
    subject_normalized: str = ""
    message_ids: list[int] = Field(default_factory=list)
    match_methods: list[str] = Field(default_factory=list)


class ContactCandidate(BaseModel):
    """套磁候选邮件"""
    message_db_id: int = 0
    is_contact_email: bool = False
    reasons: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    needs_review: bool = False


class AIAnalysisResult(BaseModel):
    """AI 分析结果"""
    reply_summary: str = ""
    evidence_sentences: list[str] = Field(default_factory=list)
    admission_intent: AdmissionIntent = AdmissionIntent.UNCERTAIN
    action_required: ActionRequired = ActionRequired.UNCERTAIN
    recommended_next_step: str = ""
    actual_responder_role: str = ""
    confidence: float = 0.0
    ambiguity_reason: str = ""


class RuleAnalysisResult(BaseModel):
    """本地规则分析结果"""
    reply_summary: str = ""
    evidence_sentences: list[str] = Field(default_factory=list)
    admission_intent: AdmissionIntent = AdmissionIntent.UNCERTAIN
    action_required: ActionRequired = ActionRequired.UNCERTAIN
    recommended_next_step: str = ""
    confidence: float = 0.0


class MergedTeacherRow(BaseModel):
    """最终合并表中的一行"""
    index: int = 0
    teacher_name: str = ""
    institution: str = ""
    teacher_email: str = ""
    first_sent_at: str = ""
    last_sent_at: str = ""
    send_count: int = 0
    correspondence_summary: str = ""
    has_real_reply: ReplyStatus = ReplyStatus.NO
    teacher_reply_time: str = ""
    actual_responder: str = ""
    reply_content_summary: str = ""
    evidence_sentences: str = ""
    admission_intent: str = ""
    my_reply_status: MyReplyStatus = MyReplyStatus.UNCERTAIN
    action_required: str = ""
    recommended_next_step: str = ""
    confidence: float = 0.0
    needs_review: bool = False


class ScanProgress(BaseModel):
    """扫描进度"""
    current_folder: str = ""
    total_folders: int = 0
    current_folder_index: int = 0
    current_message: int = 0
    total_messages: int = 0
    errors: int = 0
    status: str = "idle"
    cancelled: bool = False


class StatsOverview(BaseModel):
    """汇总统计"""
    total_related_emails: int = 0
    sent_emails: int = 0
    received_reply_emails: int = 0
    auto_reply_count: int = 0
    bounce_count: int = 0
    teacher_count: int = 0
    replied_teacher_count: int = 0
    uncertain_reply_count: int = 0
    no_reply_count: int = 0
    reply_rate: float = 0.0
    positive_intent_count: int = 0
    welcome_apply_count: int = 0
    suggest_camp_count: int = 0
    willing_to_talk_count: int = 0
    quota_uncertain_count: int = 0
    polite_no_intent_count: int = 0
    negative_count: int = 0
    need_reply_now_count: int = 0
    suggest_followup_count: int = 0
    needs_review_count: int = 0
    consistency_valid: bool = True
    consistency_message: str = ""
