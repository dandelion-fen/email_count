"""
证据详情页面 — 查看每位导师的所有相关邮件
"""
from __future__ import annotations

import streamlit as st

from src import database as db
from src.utils import truncate


def render() -> None:
    """渲染证据详情页面"""
    st.header("🔍 证据详情")
    st.caption("查看每位导师的所有相关邮件，包括发送记录和回复原文。")

    # ── 检查前置条件 ──
    account_id = st.session_state.get("account_id")
    if not account_id:
        st.warning("⚠️ 请先完成「邮箱连接」和「扫描与同步」步骤。")
        return

    teachers = db.get_all_teachers(account_id)
    if not teachers:
        st.info("💡 暂无导师数据，请先在「导师总表」页面运行分析。")
        return

    # ── 导师选择 ──
    teacher_options = {
        f"{t['name']} — {t.get('institution', '未知单位')}": t["id"]
        for t in teachers
    }

    selected_label = st.selectbox(
        "👨‍🏫 选择导师",
        options=list(teacher_options.keys()),
        help="选择一位导师查看其所有相关邮件",
    )

    if not selected_label:
        return

    teacher_id = teacher_options[selected_label]

    # ── 获取导师信息 ──
    teacher_emails = db.get_teacher_emails(teacher_id)
    teacher_msgs = db.get_teacher_messages(teacher_id)

    # 导师基本信息
    teacher_data = None
    for t in teachers:
        if t["id"] == teacher_id:
            teacher_data = t
            break

    if teacher_data:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📧 邮箱", ", ".join(teacher_emails) if teacher_emails else "未知")
        with col2:
            st.metric("📤 发送邮件", f"{teacher_data.get('send_count', 0)} 封")
        with col3:
            st.metric("📨 相关邮件", f"{len(teacher_msgs)} 封")

    st.markdown("---")

    # ── 邮件列表 ──
    if not teacher_msgs:
        st.info("📭 未找到与该导师相关的邮件记录。")
        return

    st.subheader(f"📧 相关邮件（共 {len(teacher_msgs)} 封）")

    for i, msg in enumerate(teacher_msgs, 1):
        is_sent = bool(msg.get("is_sent_by_me"))
        is_auto = bool(msg.get("is_auto_reply"))
        is_bounce = bool(msg.get("is_bounce"))

        # 方向标识
        if is_sent:
            direction_icon = "📤"
            direction_text = "我发送"
        else:
            direction_icon = "📥"
            direction_text = "收到"

        # 特殊状态
        status_tags = []
        if is_auto:
            status_tags.append("🤖 自动回复")
        if is_bounce:
            status_tags.append("❌ 退信")

        role = msg.get("message_role", "")
        if role:
            status_tags.append(f"📌 {role}")

        # 构建标题
        subject = msg.get("subject", "(无主题)")
        date_str = msg.get("date", "")[:16] if msg.get("date") else "日期未知"
        status_str = " | ".join(status_tags) if status_tags else ""

        expander_title = f"{direction_icon} [{date_str}] {subject}"
        if status_str:
            expander_title += f"  ({status_str})"

        with st.expander(expander_title, expanded=False):
            # 邮件头信息
            col_from, col_to = st.columns(2)
            with col_from:
                from_name = msg.get("from_name", "")
                from_email = msg.get("from_email", "")
                sender = f"{from_name} <{from_email}>" if from_name else from_email
                st.markdown(f"**发件人:** {sender}")
            with col_to:
                st.markdown(f"**收件人:** {msg.get('to_addrs', '')}")

            col_date, col_folder = st.columns(2)
            with col_date:
                st.markdown(f"**日期:** {msg.get('date', '未知')}")
            with col_folder:
                st.markdown(f"**文件夹:** {msg.get('folder_id', '')}")

            col_dir, col_reply = st.columns(2)
            with col_dir:
                st.markdown(f"**方向:** {direction_text}")
            with col_reply:
                reply_tag = "是" if not is_sent else "—"
                st.markdown(f"**是否为回复:** {reply_tag}")

            if msg.get("cc_addrs"):
                st.markdown(f"**抄送:** {msg['cc_addrs']}")

            if msg.get("has_attachments"):
                att_names = msg.get("attachment_names", "")
                st.markdown(f"**附件:** {att_names if att_names else '有附件'}")

            st.markdown("---")

            # 正文预览
            body = msg.get("body_text", "") or msg.get("body_html_text", "") or ""

            if body:
                # 显示摘要
                summary = truncate(body, 500)
                st.markdown("**正文预览:**")
                st.text(summary)

                # 完整正文折叠
                if len(body) > 500:
                    if st.button(
                        f"📖 查看完整正文",
                        key=f"full_body_{msg.get('id', i)}",
                    ):
                        st.text_area(
                            "完整正文",
                            value=body,
                            height=300,
                            disabled=True,
                            key=f"body_area_{msg.get('id', i)}",
                            label_visibility="collapsed",
                        )
            else:
                st.caption("（正文为空或无法解析）")
