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
        
        # 优先从邮箱域名获取单位，保证 100% 准确性，其次从正文中提取并清洗
        institution = _guess_institution_from_email(email_addr)
        if not institution:
            institution = _extract_institution(msgs)

        needs_review = False
        review_reasons = []

        if not name:
            name = email_addr.split("@")[0]
            needs_review = True
            review_reasons.append("无法确认导师姓名")

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

        # 清理常见的关于学生自己学校的描述，防止干扰
        clean_text = text
        clean_text = re.sub(r'我是[\u4e00-\u9fa5]{2,10}(大学|学院)', '', clean_text)
        clean_text = re.sub(r'就读于[\u4e00-\u9fa5]{2,10}(大学|学院)', '', clean_text)
        clean_text = re.sub(r'毕业于[\u4e00-\u9fa5]{2,10}(大学|学院)', '', clean_text)
        clean_text = re.sub(r'在[\u4e00-\u9fa5]{2,10}(大学|学院)学习', '', clean_text)

        patterns = [
            r'([\u4e00-\u9fa5]{2,10}大学)',
            r'([\u4e00-\u9fa5]{2,10}研究所)',
            r'([\u4e00-\u9fa5]{2,10}研究院)',
            r'([\u4e00-\u9fa5]{2,15}学院)',
        ]
        for pat in patterns:
            matches = re.findall(pat, clean_text)
            if matches:
                for m in matches:
                    m = m.strip()
                    # 清理前缀词汇以防匹配结果里包含 “我是”、“在读于” 等
                    m = _clean_school_prefixes(m)
                    # 排除带有动作词或属于学生自述的词
                    if any(w in m for w in ["湖北工业", "我是", "就读", "毕业", "在读", "近期", "了解"]):
                        continue
                    if len(m) >= 4 and ("大学" in m or "学院" in m or "研究所" in m or "研究院" in m):
                        return m

    return ""


def _clean_school_prefixes(name: str) -> str:
    """清理提取出的学校名字中包含的动词/代词前缀"""
    prefixes = ["我是", "就读于", "毕业于", "想申请", "在读", "在", "近期", "了解", "报考", "联系", "向", "给", "我", "是", "的", "去"]
    changed = True
    while changed:
        changed = False
        for p in prefixes:
            if name.startswith(p):
                name = name[len(p):].strip()
                changed = True
                break
    return name


_DOMAIN_TO_SCHOOL = {
    "pku.edu.cn": "北京大学",
    "tsinghua.edu.cn": "清华大学",
    "zju.edu.cn": "浙江大学",
    "sjtu.edu.cn": "上海交通大学",
    "fudan.edu.cn": "复旦大学",
    "ustc.edu.cn": "中国科学技术大学",
    "nju.edu.cn": "南京大学",
    "whu.edu.cn": "武汉大学",
    "hust.edu.cn": "华中科技大学",
    "sysu.edu.cn": "中山大学",
    "hit.edu.cn": "哈尔滨工业大学",
    "xidian.edu.cn": "西安电子科技大学",
    "seu.edu.cn": "东南大学",
    "scut.edu.cn": "华南理工大学",
    "xmu.edu.cn": "厦门大学",
    "uestc.edu.cn": "电子科技大学",
    "bupt.edu.cn": "北京邮电大学",
    "hnu.edu.cn": "湖南大学",
    "ecnu.edu.cn": "华东师范大学",
    "neu.edu.cn": "东北大学",
    "tongji.edu.cn": "同济大学",
    "nankai.edu.cn": "南开大学",
    "tju.edu.cn": "天津大学",
    "sdu.edu.cn": "山东大学",
    "cqu.edu.cn": "重庆大学",
    "scu.edu.cn": "四川大学",
    "xjtu.edu.cn": "西安交通大学",
    "nwpu.edu.cn": "西北工业大学",
    "dlut.edu.cn": "大连理工大学",
    "jlu.edu.cn": "吉林大学",
    "lzu.edu.cn": "兰州大学",
    "buaa.edu.cn": "北京航空航天大学",
    "bit.edu.cn": "北京理工大学",
    "ustb.edu.cn": "北京科技大学",
    "bjtu.edu.cn": "北京交通大学",
    "ncepu.edu.cn": "华北电力大学",
    "cumt.edu.cn": "中国矿业大学",
    "upc.edu.cn": "中国石油大学（华东）",
    "upb.edu.cn": "中国石油大学（北京）",
    "ugb.edu.cn": "中国地质大学（北京）",
    "cug.edu.cn": "中国地质大学（武汉）",
    "swjtu.edu.cn": "西南交通大学",
    "nuaa.edu.cn": "南京航空航天大学",
    "njust.edu.cn": "南京理工大学",
    "hhu.edu.cn": "河海大学",
    "jiangnan.edu.cn": "江南大学",
    "hebut.edu.cn": "河北工业大学",
    "taur.edu.cn": "太原理工大学",
    "imu.edu.cn": "内蒙古大学",
    "dhu.edu.cn": "东华大学",
    "shmtu.edu.cn": "上海海事大学",
    "shutcm.edu.cn": "上海中医药大学",
    "yzu.edu.cn": "扬州大学",
    "ujs.edu.cn": "江苏大学",
    "njtech.edu.cn": "南京工业大学",
    "huel.edu.cn": "湖北工业大学",
    "hbut.edu.cn": "湖北工业大学",
    "wust.edu.cn": "武汉科技大学",
    "whut.edu.cn": "武汉理工大学",
    "ccnu.edu.cn": "华中师范大学",
    "hzau.edu.cn": "华中农业大学",
    "zuel.edu.cn": "中南财经政法大学",
    "csu.edu.cn": "中南大学",
    "hunnu.edu.cn": "湖南师范大学",
    "szu.edu.cn": "深圳大学",
    "jnu.edu.cn": "暨南大学",
    "scau.edu.cn": "华南农业大学",
    "gxu.edu.cn": "广西大学",
    "hnu.edu.cn": "海南大学",
    "swufe.edu.cn": "西南财经大学",
    "sicau.edu.cn": "四川农业大学",
    "cdut.edu.cn": "成都理工大学",
    "yuntc.edu.cn": "云南大学",
    "ynu.edu.cn": "云南大学",
    "guet.edu.cn": "桂林电子科技大学",
    "gzu.edu.cn": "贵州大学",
    "xju.edu.cn": "新疆大学",
    "shzu.edu.cn": "石河子大学",
    "ime.ac.cn": "中国科学院微电子研究所",
    "ucas.ac.cn": "中国科学院大学",
    "ucas.edu.cn": "中国科学院大学",
}


def _guess_institution_from_email(email: str) -> str:
    """从邮箱域名猜测单位"""
    email = email.lower().strip()
    domain = email.split("@")[-1]
    
    # 1. 尝试完全匹配
    if domain in _DOMAIN_TO_SCHOOL:
        return _DOMAIN_TO_SCHOOL[domain]
        
    # 2. 尝试子域名匹配（如 xxx.zju.edu.cn）
    for d, school in _DOMAIN_TO_SCHOOL.items():
        if domain.endswith("." + d) or domain == d:
            return school
            
    # 3. 常见教育域名回退
    if ".edu.cn" in domain:
        parts = domain.replace(".edu.cn", "").split(".")
        prefix = parts[-1] if parts else ""
        for d, school in _DOMAIN_TO_SCHOOL.items():
            if d.startswith(prefix + "."):
                return school
        return prefix.upper()
    if ".ac.cn" in domain or ".cas.cn" in domain:
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
