"""
会话线程重建模块
"""
from __future__ import annotations

from collections import defaultdict
from src.subject_normalizer import normalize_subject, subjects_similar
from src.models import ThreadMatchMethod
from src import database as db
from src.utils import setup_logger, normalize_email

logger = setup_logger("thread_builder")


def build_threads(account_id: int, db_path: str | None = None) -> int:
    """重建所有邮件的会话线程"""
    messages = db.get_all_messages(account_id, db_path)
    if not messages:
        return 0

    # 清除旧线程
    conn = db.get_connection(db_path)
    conn.execute("DELETE FROM thread_messages WHERE thread_id IN (SELECT id FROM threads WHERE account_id=?)", (account_id,))
    conn.execute("DELETE FROM threads WHERE account_id=?", (account_id,))
    conn.commit()

    # 建立索引
    msg_by_id: dict[str, dict] = {}  # message_id -> msg
    msg_by_db_id: dict[int, dict] = {}
    for m in messages:
        if m.get("message_id"):
            msg_by_id[m["message_id"]] = m
        msg_by_db_id[m["id"]] = m

    # 用 Union-Find 来分组
    parent: dict[int, int] = {m["id"]: m["id"] for m in messages}
    match_methods: dict[tuple[int, int], str] = {}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int, method: str):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
            match_methods[(min(a, b), max(a, b))] = method

    # 1. Message-ID / In-Reply-To / References 匹配
    for m in messages:
        # In-Reply-To
        irt = m.get("in_reply_to", "").strip()
        if irt and irt in msg_by_id:
            other = msg_by_id[irt]
            union(m["id"], other["id"], ThreadMatchMethod.IN_REPLY_TO.value)

        # References
        refs = m.get("references_str", "").strip()
        if refs:
            ref_ids = [r.strip() for r in refs.split() if r.strip()]
            for ref_id in ref_ids:
                if ref_id in msg_by_id:
                    other = msg_by_id[ref_id]
                    union(m["id"], other["id"], ThreadMatchMethod.REFERENCES.value)

    # 2. 规范化主题 + 收发件人匹配
    subj_groups: dict[str, list[dict]] = defaultdict(list)
    for m in messages:
        sn = m.get("subject_normalized", "")
        if sn:
            subj_groups[sn].append(m)

    for subj, msgs in subj_groups.items():
        if len(msgs) < 2:
            continue
        # 在同一规范化主题下，检查收发件人关系
        for i in range(len(msgs)):
            for j in range(i + 1, len(msgs)):
                mi, mj = msgs[i], msgs[j]
                if _has_address_overlap(mi, mj):
                    union(mi["id"], mj["id"], ThreadMatchMethod.SUBJECT.value)

    # 3. 收集线程
    thread_groups: dict[int, list[int]] = defaultdict(list)
    for m in messages:
        root = find(m["id"])
        thread_groups[root].append(m["id"])

    # 4. 保存到数据库
    thread_count = 0
    for root, msg_ids in thread_groups.items():
        if not msg_ids:
            continue
        # 用第一条消息的规范化主题
        first_msg = msg_by_db_id.get(msg_ids[0], {})
        subj_norm = first_msg.get("subject_normalized", "")

        thread_id = db.insert_thread(account_id, subj_norm, db_path)
        for mid in msg_ids:
            method = ""
            key1 = (min(mid, root), max(mid, root))
            if key1 in match_methods:
                method = match_methods[key1]
            db.link_thread_message(thread_id, mid, method, db_path)

        thread_count += 1

    logger.info(f"构建了 {thread_count} 个会话线程")
    return thread_count


def _has_address_overlap(m1: dict, m2: dict) -> bool:
    """检查两封邮件是否有收发件人重叠"""
    addrs1 = _extract_emails(m1)
    addrs2 = _extract_emails(m2)
    return bool(addrs1 & addrs2)


def _extract_emails(msg: dict) -> set[str]:
    """从邮件中提取所有相关邮箱"""
    emails = set()
    from_email = msg.get("from_email", "")
    if from_email:
        emails.add(normalize_email(from_email))

    for field in ["to_addrs", "cc_addrs"]:
        val = msg.get(field, "")
        if val:
            import re
            found = re.findall(r'[\w.+-]+@[\w.-]+\.\w+', val)
            for e in found:
                emails.add(normalize_email(e))

    return emails


def get_thread_for_message(message_id: int, db_path: str | None = None) -> int | None:
    """获取邮件所属的线程ID"""
    conn = db.get_connection(db_path)
    row = conn.execute(
        "SELECT thread_id FROM thread_messages WHERE message_id=?",
        (message_id,)).fetchone()
    return row["thread_id"] if row else None
