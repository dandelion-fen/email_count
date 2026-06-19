"""
最终合并表生成模块
"""
from __future__ import annotations

from src import database as db
from src.models import (
    MergedTeacherRow, ReplyStatus, MyReplyStatus,
    AdmissionIntent, ActionRequired, StatsOverview,
)
from src.reply_detector import detect_replies_for_teacher
from src.my_reply_checker import check_my_reply
from src.rule_analyzer import analyze_reply_by_rules
from src.utils import format_datetime, setup_logger

logger = setup_logger("merge_table")


def build_merged_table(account_id: int,
                       db_path: str | None = None) -> list[MergedTeacherRow]:
    """构建最终合并表"""
    teachers = db.get_all_teachers(account_id, db_path)
    rows = []

    for idx, teacher in enumerate(teachers, 1):
        tid = teacher["id"]
        emails = db.get_teacher_emails(tid, db_path)
        teacher_msgs = db.get_teacher_messages(tid, db_path)

        # 回复检测
        reply_result = detect_replies_for_teacher(tid, account_id, db_path)
        reply_status = reply_result["status"]
        reply_messages = reply_result.get("replies", [])

        # 我的回复检查
        my_reply = check_my_reply(tid, account_id, reply_messages, db_path)
        my_reply_status = my_reply["status"]

        # 获取回复正文
        reply_body = ""
        reply_time = ""
        actual_responder = ""
        if reply_messages:
            first_reply = reply_messages[0].get("message", {})
            reply_body = first_reply.get("body_text", "") or first_reply.get("body_html_text", "")
            reply_time = first_reply.get("date", "")
            actual_responder = first_reply.get("from_name", "") or first_reply.get("from_email", "")

        # 检查人工覆盖
        overrides = db.get_overrides("teacher", tid, db_path)
        override_map = {o["field_name"]: o["new_value"] for o in overrides}

        # 规则分析
        analysis = analyze_reply_by_rules(reply_body, reply_status, my_reply_status)

        # 检查是否有 AI 分析结果
        ai_analysis = db.get_latest_analysis(tid, "ai", db_path)
        if ai_analysis and ai_analysis.get("confidence", 0) > analysis.confidence:
            # AI 结果置信度更高时使用 AI 结果
            analysis.reply_summary = ai_analysis.get("reply_summary", analysis.reply_summary)
            analysis.admission_intent = _safe_enum(
                ai_analysis.get("admission_intent", ""), AdmissionIntent, analysis.admission_intent)
            analysis.action_required = _safe_enum(
                ai_analysis.get("action_required", ""), ActionRequired, analysis.action_required)
            analysis.recommended_next_step = ai_analysis.get(
                "recommended_next_step", analysis.recommended_next_step)
            analysis.evidence_sentences = (
                ai_analysis.get("evidence_sentences", "").split("|")
                if isinstance(ai_analysis.get("evidence_sentences"), str)
                else analysis.evidence_sentences
            )
            analysis.confidence = ai_analysis.get("confidence", analysis.confidence)

        # 邮件往来情况
        sent_count = teacher.get("send_count", 0)
        received_count = len(reply_messages)
        correspondence = f"发送 {sent_count} 封"
        if received_count > 0:
            correspondence += f"，收到 {received_count} 封回复"

        # 构建行（应用人工覆盖）
        row = MergedTeacherRow(
            index=idx,
            teacher_name=override_map.get("name", teacher.get("name", "")),
            institution=override_map.get("institution", teacher.get("institution", "")),
            teacher_email="; ".join(emails) if emails else "",
            first_sent_at=format_datetime(teacher.get("first_sent_at")),
            last_sent_at=format_datetime(teacher.get("last_sent_at")),
            send_count=sent_count,
            correspondence_summary=correspondence,
            has_real_reply=ReplyStatus(override_map.get("reply_status", reply_status.value)),
            teacher_reply_time=format_datetime(reply_time),
            actual_responder=actual_responder,
            reply_content_summary=override_map.get("reply_summary", analysis.reply_summary),
            evidence_sentences="; ".join(analysis.evidence_sentences),
            admission_intent=override_map.get("admission_intent", analysis.admission_intent.value),
            my_reply_status=MyReplyStatus(override_map.get("my_reply_status", my_reply_status.value)),
            action_required=override_map.get("action_required", analysis.action_required.value),
            recommended_next_step=analysis.recommended_next_step,
            confidence=analysis.confidence,
            needs_review=teacher.get("needs_review", False) or analysis.confidence < 0.5,
        )
        rows.append(row)

    return rows


def build_stats(rows: list[MergedTeacherRow]) -> StatsOverview:
    """生成汇总统计"""
    stats = StatsOverview()
    stats.teacher_count = len(rows)

    for row in rows:
        if row.has_real_reply == ReplyStatus.YES:
            stats.replied_teacher_count += 1
        elif row.has_real_reply == ReplyStatus.NO:
            stats.no_reply_count += 1
        else:
            stats.uncertain_reply_count += 1

        # 招生意向统计
        intent = row.admission_intent
        if intent in (AdmissionIntent.ACCEPT_WITH_QUOTA.value, AdmissionIntent.WELCOME_JOIN.value):
            stats.positive_intent_count += 1
        elif intent == AdmissionIntent.WELCOME_APPLY_NEED_EXAM.value:
            stats.welcome_apply_count += 1
        elif intent in (AdmissionIntent.SUGGEST_SUMMER_CAMP.value, AdmissionIntent.SUGGEST_PRE_ADMISSION.value):
            stats.suggest_camp_count += 1
        elif intent in (AdmissionIntent.WILLING_TO_TALK.value, AdmissionIntent.ADDED_WECHAT.value):
            stats.willing_to_talk_count += 1
        elif intent in (AdmissionIntent.QUOTA_UNCERTAIN.value, AdmissionIntent.WAIT_POLICY.value,
                        AdmissionIntent.WAIT_EXAM_RESULT.value):
            stats.quota_uncertain_count += 1
        elif intent == AdmissionIntent.POLITE_NO_INTENT.value:
            stats.polite_no_intent_count += 1
        elif intent in (AdmissionIntent.QUOTA_FULL.value, AdmissionIntent.DIRECTION_MISMATCH.value,
                        AdmissionIntent.REJECTED.value):
            stats.negative_count += 1

        # 行动统计
        if row.action_required == ActionRequired.REPLY_NOW.value:
            stats.need_reply_now_count += 1
        elif row.action_required == ActionRequired.CONSIDER_FOLLOWUP.value:
            stats.suggest_followup_count += 1

        if row.needs_review:
            stats.needs_review_count += 1

    # 有效回复率
    if stats.teacher_count > 0:
        stats.reply_rate = round(
            stats.replied_teacher_count / stats.teacher_count * 100, 1)

    # 一致性校验
    total_check = stats.replied_teacher_count + stats.no_reply_count + stats.uncertain_reply_count
    if total_check != stats.teacher_count:
        stats.consistency_valid = False
        stats.consistency_message = (
            f"数据一致性错误: 已回复({stats.replied_teacher_count}) + "
            f"未回复({stats.no_reply_count}) + "
            f"无法确认({stats.uncertain_reply_count}) = {total_check}, "
            f"但导师总数为 {stats.teacher_count}"
        )
    else:
        stats.consistency_valid = True
        stats.consistency_message = "数据一致性校验通过"

    return stats


def _safe_enum(value, enum_class, default):
    try:
        return enum_class(value)
    except (ValueError, KeyError):
        return default
