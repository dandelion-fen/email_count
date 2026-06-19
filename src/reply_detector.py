"""
真实回复判定模块

核心规则：只有实际找到导师/课题组发来的收件邮件，才能判断为"收到真实回复"。
Re: 标题不能单独证明导师已回复。
"""
from __future__ import annotations

import re
from src import database as db
from src.models import ReplyStatus, MessageRole
from src.subject_normalizer import normalize_subject, subjects_similar
from src.utils import setup_logger, normalize_email

logger = setup_logger("reply_detector")


def detect_replies_for_teacher(teacher_id: int, account_id: int,
                               db_path: str | None = None) -> dict:
    """检测某位导师是否有真实回复"""
    teacher_emails = db.get_teacher_emails(teacher_id, db_path)
    teacher_msgs = db.get_teacher_messages(teacher_id, db_path)

    if not teacher_emails:
        return _result(ReplyStatus.UNCERTAIN, reason="导师邮箱信息缺失")

    # 获取导师发来的收件邮件
    all_received = db.get_received_messages(account_id, db_path)

    # 我发送的套磁邮件
    sent_msgs = [m for m in teacher_msgs if m.get("is_sent_by_me")]
    if not sent_msgs:
        all_sent = db.get_sent_messages(account_id, db_path)
        for m in all_sent:
            to_addrs = m.get("to_addrs", "")
            for email in teacher_emails:
                if email.lower() in to_addrs.lower():
                    sent_msgs.append(m)
                    break

    sent_subjects = set()
    sent_message_ids = set()
    for m in sent_msgs:
        sn = m.get("subject_normalized", "") or normalize_subject(m.get("subject", ""))
        if sn:
            sent_subjects.add(sn)
        mid = m.get("message_id", "")
        if mid:
            sent_message_ids.add(mid)

    teacher_email_set = {normalize_email(e) for e in teacher_emails}

    # 找到这些发送邮件对应的会话线程 ID
    conn = db.get_connection(db_path)
    sent_db_ids = [m["id"] for m in sent_msgs]
    thread_received_msg_ids = set()
    
    if sent_db_ids:
        placeholders = ",".join(["?"] * len(sent_db_ids))
        try:
            # 找到发送邮件对应的所有 thread_id
            t_rows = conn.execute(f"SELECT DISTINCT thread_id FROM thread_messages WHERE message_id IN ({placeholders})", sent_db_ids).fetchall()
            thread_ids = [r["thread_id"] for r in t_rows]
            if thread_ids:
                # 找到这些 thread 中的所有收到邮件的 id
                th_placeholders = ",".join(["?"] * len(thread_ids))
                r_rows = conn.execute(f"""
                    SELECT tm.message_id FROM thread_messages tm
                    JOIN messages m ON tm.message_id = m.id
                    WHERE tm.thread_id IN ({th_placeholders}) AND m.is_sent_by_me = 0
                """, thread_ids).fetchall()
                thread_received_msg_ids = {r["message_id"] for r in r_rows}
        except Exception as e:
            logger.warning(f"Error querying thread messages: {e}")

    # 在收件邮件中搜索导师的真实回复
    real_replies = []
    for msg in all_received:
        from_email = normalize_email(msg.get("from_email", ""))
        
        # 匹配方式：或者是发件人邮箱匹配，或者是该收件在会话线程中
        is_email_match = from_email in teacher_email_set
        is_thread_match = msg["id"] in thread_received_msg_ids
        
        if not is_email_match and not is_thread_match:
            continue

        # 排除退信
        if msg.get("is_bounce"):
            continue

        # 排除自动回复
        if msg.get("is_auto_reply"):
            # 记录但不算真实回复
            db.link_teacher_message(teacher_id, msg["id"],
                                    MessageRole.RECEIVED_AUTO.value, db_path)
            continue

        # 检查是否与套磁相关（在同一线程，或 In-Reply-To 引用，或主题匹配）
        is_related = False
        match_reason = ""

        if is_thread_match:
            is_related = True
            match_reason = "会话线程关联匹配"
        else:
            # 方法1: In-Reply-To 或 References 引用了我发送的邮件
            irt = msg.get("in_reply_to", "")
            refs = msg.get("references_str", "")
            if irt and irt in sent_message_ids:
                is_related = True
                match_reason = "In-Reply-To 匹配"
            elif refs:
                for ref in refs.split():
                    if ref.strip() in sent_message_ids:
                        is_related = True
                        match_reason = "References 匹配"
                        break
            
            # 方法2: 规范化主题匹配
            if not is_related:
                msg_subj = msg.get("subject_normalized", "") or normalize_subject(msg.get("subject", ""))
                for sent_subj in sent_subjects:
                    if subjects_similar(msg_subj, sent_subj, threshold=0.6):
                        is_related = True
                        match_reason = "主题相似匹配"
                        break

        if is_related:
            real_replies.append({
                "message": msg,
                "match_reason": match_reason,
            })
            db.link_teacher_message(teacher_id, msg["id"],
                                    MessageRole.RECEIVED_REPLY.value, db_path)
            
            # 自动把新发现的回复邮箱关联至导师的邮箱库中，便于后续去重和展示
            if from_email and from_email not in teacher_email_set:
                db.add_teacher_email(teacher_id, from_email, is_primary=False,
                                     source="auto_discovered_reply", db_path=db_path)
                teacher_email_set.add(from_email)

    if real_replies:
        # 读取回复正文确认是真实回复
        first_reply = real_replies[0]["message"]
        body = first_reply.get("body_text", "") or first_reply.get("body_html_text", "")
        if body.strip():
            return _result(
                ReplyStatus.YES,
                replies=real_replies,
                reason="找到导师发来的原始邮件并已读取正文",
            )
        else:
            return _result(
                ReplyStatus.UNCERTAIN,
                replies=real_replies,
                reason="找到导师发来的邮件但正文为空或无法解析",
            )

    # 检查是否有我发出的 Re: 但没有导师原始来信
    has_my_re = False
    for m in sent_msgs:
        subj = m.get("subject", "")
        if re.match(r'^(Re|RE|回复|答复)\s*[:：]', subj.strip()):
            has_my_re = True
            break

    if has_my_re:
        return _result(
            ReplyStatus.UNCERTAIN,
            reason="仅发现我发出的回复邮件(Re:)，未找到导师原始来信正文，无法确认",
        )

    return _result(ReplyStatus.NO, reason="未检索到导师本人或课题组针对套磁邮件的有效回复")


def detect_all_replies(account_id: int, db_path: str | None = None) -> dict[int, dict]:
    """检测所有导师的回复状态"""
    teachers = db.get_all_teachers(account_id, db_path)
    results = {}
    for t in teachers:
        tid = t["id"]
        # 检查是否有人工覆盖
        if db.has_override("teacher", tid, "reply_status", db_path):
            overrides = db.get_overrides("teacher", tid, db_path)
            for o in overrides:
                if o["field_name"] == "reply_status":
                    results[tid] = _result(
                        ReplyStatus(o["new_value"]),
                        reason="人工覆盖",
                        is_override=True,
                    )
                    break
        else:
            results[tid] = detect_replies_for_teacher(tid, account_id, db_path)

    return results


def _result(status: ReplyStatus, replies: list | None = None,
            reason: str = "", is_override: bool = False) -> dict:
    return {
        "status": status,
        "replies": replies or [],
        "reason": reason,
        "is_override": is_override,
    }
