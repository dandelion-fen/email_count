"""
导师识别与去重模块
"""
from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

from src import database as db
from src.utils import setup_logger, normalize_email
from src.models import MessageRole

logger = setup_logger("teacher_dedup")


def identify_teachers(account_id: int, contact_msg_ids: list[int],
                      db_path: str | None = None) -> int:
    """从已发送的套磁邮件中识别导师"""
    # 清除旧数据（保留人工覆盖）
    db.clear_analysis_data(account_id, db_path)

    conn = db.get_connection(db_path)
    sent_msgs = []
    for mid in contact_msg_ids:
        row = conn.execute("SELECT * FROM messages WHERE id=? AND is_sent_by_me=1", (mid,)).fetchone()
        if row:
            sent_msgs.append(dict(row))

    if not sent_msgs:
        logger.info("未发现已发送的套磁邮件")
        return 0

    # 按收件人分组
    email_to_msgs: dict[str, list[dict]] = defaultdict(list)
    for msg in sent_msgs:
        to_emails = _extract_recipient_emails(msg)
        for email in to_emails:
            email_to_msgs[email].append(msg)

    # 为每个收件人邮箱创建或合并导师
    teacher_count = 0
    processed_emails: set[str] = set()

    for email_addr, msgs in email_to_msgs.items():
        if email_addr in processed_emails:
            continue

        # 从邮件中提取导师信息
        name = _extract_teacher_name(msgs, email_addr)
        institution = _extract_institution(msgs)

        needs_review = False
        review_reasons = []

        if not name:
            name = email_addr.split("@")[0]
            needs_review = True
            review_reasons.append("无法确认导师姓名")

        if not institution:
            institution = _guess_institution_from_email(email_addr)
            if not institution:
                needs_review = True
                review_reasons.append("无法确认所属单位")

        # 计算发送信息
        dates = [m.get("date", "") for m in msgs if m.get("date")]
        dates.sort()
        first_sent = dates[0] if dates else ""
        last_sent = dates[-1] if dates else ""

        confidence = 0.8
        if needs_review:
            confidence = 0.5

        teacher_id = db.insert_teacher(
            account_id, name, institution,
            confidence=confidence,
            needs_review=needs_review,
            review_reasons="; ".join(review_reasons),
            db_path=db_path,
        )

        db.update_teacher(teacher_id, {
            "first_sent_at": first_sent,
            "last_sent_at": last_sent,
            "send_count": len(msgs),
        }, db_path)

        db.add_teacher_email(teacher_id, email_addr, is_primary=True,
                             source="sent_email", db_path=db_path)

        # 关联邮件
        for i, msg in enumerate(msgs):
            role = MessageRole.SENT_FIRST.value if i == 0 else MessageRole.SENT_FOLLOWUP.value
            # 判断是否为补发、补充材料等
            subj = msg.get("subject", "").lower()
            body = (msg.get("body_text", "") or "")[:200].lower()
            if "补充" in subj or "补充" in body:
                role = MessageRole.SENT_SUPPLEMENT.value
            elif i > 0 and "re:" in msg.get("subject", "").lower():
                role = MessageRole.SENT_REPLY.value

            db.link_teacher_message(teacher_id, msg["id"], role, db_path)

        processed_emails.add(email_addr)
        teacher_count += 1

    logger.info(f"识别了 {teacher_count} 位导师")
    return teacher_count


def merge_teachers_by_alias(account_id: int, alias_file: str | None = None,
                            db_path: str | None = None) -> int:
    """根据别名文件合并导师"""
    if not alias_file or not Path(alias_file).exists():
        return 0

    merged = 0
    try:
        with open(alias_file, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                primary = normalize_email(row.get("email", ""))
                alias = normalize_email(row.get("alias_email", ""))
                if primary and alias and primary != alias:
                    _merge_by_emails(account_id, primary, alias, db_path)
                    merged += 1
    except Exception as e:
        logger.error(f"读取别名文件失败: {e}")

    return merged


def check_duplicate_teachers(account_id: int, db_path: str | None = None) -> list[dict]:
    """检查可能重复的导师（同姓名不同邮箱）"""
    teachers = db.get_all_teachers(account_id, db_path)
    name_groups: dict[str, list[dict]] = defaultdict(list)

    for t in teachers:
        if t.get("name"):
            name_groups[t["name"]].append(t)

    duplicates = []
    for name, group in name_groups.items():
        if len(group) > 1:
            # 检查是否同一单位
            institutions = set(t.get("institution", "") for t in group)
            if len(institutions) == 1 and "" not in institutions:
                duplicates.append({
                    "name": name,
                    "teachers": group,
                    "reason": "同姓名同单位，可能是同一导师使用多个邮箱",
                    "auto_merge": False,  # 不自动合并，放入人工复核
                })
            else:
                duplicates.append({
                    "name": name,
                    "teachers": group,
                    "reason": "同姓名但不同单位，可能是不同导师",
                    "auto_merge": False,
                })

    return duplicates


def _extract_teacher_name(msgs: list[dict], email: str) -> str:
    """从邮件中提取导师姓名"""
    # 从收件人字段中查找
    for msg in msgs:
        to_addrs = msg.get("to_addrs", "")
        # 查找 "姓名 <email>" 格式
        pattern = rf'([^<,;]+?)\s*<{re.escape(email)}>'
        match = re.search(pattern, to_addrs, re.IGNORECASE)
        if match:
            name = match.group(1).strip().strip('"\'')
            if name and not re.match(r'^[\w.+-]+@', name):
                return name

    # 从正文中尝试提取（如 "尊敬的X教授/老师"）
    for msg in msgs:
        body = (msg.get("body_text", "") or "")[:500]
        patterns = [
            r'尊敬的\s*(\w{1,4})\s*(教授|老师|导师|研究员|博导)',
            r'(\w{1,4})\s*(教授|老师|导师|研究员|博导)\s*(您好|你好)',
        ]
        for pat in patterns:
            match = re.search(pat, body)
            if match:
                return match.group(1) + match.group(2)

    return ""


def _extract_institution(msgs: list[dict]) -> str:
    """从邮件中提取学校/研究单位"""
    for msg in msgs:
        subject = msg.get("subject", "")
        body = (msg.get("body_text", "") or "")[:800]
        text = subject + " " + body

        patterns = [
            r'([\u4e00-\u9fa5]{2,10}大学)',
            r'([\u4e00-\u9fa5]{2,10}研究所)',
            r'([\u4e00-\u9fa5]{2,10}研究院)',
            r'([\u4e00-\u9fa5]{2,15}学院)',
        ]
        for pat in patterns:
            matches = re.findall(pat, text)
            if matches:
                # 排除我自己的学校
                for m in matches:
                    if "湖北工业" not in m:
                        return m
                # 如果只有自己学校，可能是主题中的
                if matches:
                    return matches[0]

    return ""


def _guess_institution_from_email(email: str) -> str:
    """从邮箱域名猜测单位"""
    domain = email.split("@")[-1].lower()
    # 常见教育域名
    if ".edu.cn" in domain:
        parts = domain.replace(".edu.cn", "").split(".")
        return parts[-1] if parts else ""
    if ".ac.cn" in domain:
        return "中国科学院"
    return ""


def _merge_by_emails(account_id: int, primary: str, alias: str,
                     db_path: str | None = None) -> None:
    """将 alias 邮箱的导师合并到 primary 邮箱的导师"""
    conn = db.get_connection(db_path)
    primary_row = conn.execute(
        "SELECT te.teacher_id FROM teacher_emails te JOIN teachers t ON te.teacher_id=t.id WHERE te.email=? AND t.account_id=?",
        (primary, account_id)).fetchone()
    alias_row = conn.execute(
        "SELECT te.teacher_id FROM teacher_emails te JOIN teachers t ON te.teacher_id=t.id WHERE te.email=? AND t.account_id=?",
        (alias, account_id)).fetchone()

    if not primary_row or not alias_row:
        return
    if primary_row["teacher_id"] == alias_row["teacher_id"]:
        return

    primary_tid = primary_row["teacher_id"]
    alias_tid = alias_row["teacher_id"]

    # 将 alias 的邮件转移到 primary
    conn.execute("UPDATE teacher_messages SET teacher_id=? WHERE teacher_id=?",
                 (primary_tid, alias_tid))
    # 转移邮箱
    try:
        conn.execute("UPDATE teacher_emails SET teacher_id=? WHERE teacher_id=?",
                     (primary_tid, alias_tid))
    except Exception:
        pass
    # 更新发送次数
    conn.execute(
        "UPDATE teachers SET send_count = (SELECT COUNT(*) FROM teacher_messages WHERE teacher_id=?), updated_at=datetime('now') WHERE id=?",
        (primary_tid, primary_tid))
    # 删除 alias 导师
    conn.execute("DELETE FROM teachers WHERE id=?", (alias_tid,))
    conn.commit()


def _extract_recipient_emails(msg: dict) -> list[str]:
    """从已发送邮件的 to_addrs 中提取收件人邮箱列表"""
    to_addrs = msg.get("to_addrs", "")
    if not to_addrs:
        return []
    # 使用正则表达式提取所有括号内的邮箱，或者作为回退提取所有邮箱匹配项
    emails = re.findall(r'<([^>]+)>', to_addrs)
    if not emails:
        parts = re.split(r'[;,]', to_addrs)
        for p in parts:
            p = p.strip()
            if "@" in p:
                m = re.search(r'[\w.+-]+@[\w.+-]+', p)
                if m:
                    emails.append(m.group(0).lower())
    else:
        emails = [e.strip().lower() for e in emails if e.strip()]
    return emails
