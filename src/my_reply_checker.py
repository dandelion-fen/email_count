"""
判断我是否已经回复导师来信
"""
from __future__ import annotations

import re
from src import database as db
from src.models import MyReplyStatus
from src.subject_normalizer import normalize_subject, subjects_similar
from src.utils import normalize_email


def check_my_reply(teacher_id: int, account_id: int,
                   reply_messages: list[dict],
                   db_path: str | None = None) -> dict:
    """检查我是否已回复导师的来信"""
    if not reply_messages:
        return {"status": MyReplyStatus.NO_NEED, "reason": "导师未回复，无需判断"}

    teacher_emails = db.get_teacher_emails(teacher_id, db_path)
    teacher_email_set = {normalize_email(e) for e in teacher_emails}

    sent_msgs = db.get_sent_messages(account_id, db_path)

    # 对每封导师来信，检查是否有我的后续回复
    for reply_msg in reply_messages:
        msg = reply_msg.get("message", reply_msg)
        reply_date = msg.get("date", "")
        reply_msg_id = msg.get("message_id", "")
        reply_subj_norm = msg.get("subject_normalized", "") or normalize_subject(msg.get("subject", ""))

        found_my_reply = False

        for sent in sent_msgs:
            sent_date = sent.get("date", "")
            # 时间必须在导师来信之后
            if sent_date and reply_date and sent_date <= reply_date:
                continue

            # 方法1: In-Reply-To 直接关联
            irt = sent.get("in_reply_to", "")
            if irt and irt == reply_msg_id:
                found_my_reply = True
                break

            # 方法2: References 包含导师邮件
            refs = sent.get("references_str", "")
            if refs and reply_msg_id and reply_msg_id in refs:
                found_my_reply = True
                break

            # 方法3: 同一导师邮箱 + 相似主题 + 时间在后
            sent_to = sent.get("to_addrs", "").lower()
            has_teacher_addr = any(e in sent_to for e in teacher_email_set)
            if has_teacher_addr:
                sent_subj = sent.get("subject_normalized", "") or normalize_subject(sent.get("subject", ""))
                if subjects_similar(sent_subj, reply_subj_norm, threshold=0.6):
                    found_my_reply = True
                    break

        if not found_my_reply:
            return {
                "status": MyReplyStatus.NOT_REPLIED,
                "reason": f"导师于 {reply_date} 的来信尚未回复",
                "unreplied_message": msg,
            }

    return {
        "status": MyReplyStatus.REPLIED,
        "reason": "已回复导师来信",
    }
