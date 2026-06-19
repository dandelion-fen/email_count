"""
人工复核页面 — 处理低置信度、未知姓名、疑似重复导师
"""
from __future__ import annotations

import streamlit as st

from src import database as db
from src.teacher_dedup import check_duplicate_teachers


def render() -> None:
    """渲染人工复核页面"""
    st.header("✅ 人工复核")
    st.caption("处理需要人工确认的项目：低置信度分析、未知导师姓名、疑似重复条目。")

    # ── 检查前置条件 ──
    account_id = st.session_state.get("account_id")
    if not account_id:
        st.warning("⚠️ 请先完成「邮箱连接」和「扫描与同步」步骤。")
        return

    teachers = db.get_all_teachers(account_id)
    if not teachers:
        st.info("💡 暂无导师数据，请先在「导师总表」页面运行分析。")
        return

    # ── 分类待复核项目 ──
    needs_review = [t for t in teachers if t.get("needs_review")]
    low_confidence = [t for t in teachers if t.get("confidence", 1.0) < 0.6]
    unknown_name = [t for t in teachers
                    if not t.get("name")
                    or t.get("name", "").count("@") > 0]
    duplicates = check_duplicate_teachers(account_id)

    # ── 标签页 ──
    tab_review, tab_dup, tab_unknown, tab_history = st.tabs([
        f"⚠️ 待复核 ({len(needs_review)})",
        f"👥 疑似重复 ({len(duplicates)})",
        f"❓ 未知姓名 ({len(unknown_name)})",
        "📜 修改历史",
    ])

    # ── Tab 1: 待复核 ──
    with tab_review:
        if not needs_review:
            st.success("🎉 没有需要复核的项目！")
        else:
            for t in needs_review:
                tid = t["id"]
                reasons = t.get("review_reasons", "").split("; ")
                emails = db.get_teacher_emails(tid)

                with st.expander(
                    f"⚠️ {t.get('name', '未知')} — {t.get('institution', '未知单位')} "
                    f"(置信度: {t.get('confidence', 0):.0%})",
                    expanded=False,
                ):
                    st.markdown(f"**邮箱:** {', '.join(emails)}")
                    st.markdown(f"**复核原因:** {'; '.join(reasons)}")

                    st.markdown("---")
                    st.markdown("**操作:**")

                    col_a, col_b = st.columns(2)

                    with col_a:
                        new_name = st.text_input(
                            "修改姓名",
                            value=t.get("name", ""),
                            key=f"name_{tid}",
                        )
                        new_inst = st.text_input(
                            "修改单位",
                            value=t.get("institution", ""),
                            key=f"inst_{tid}",
                        )

                    with col_b:
                        new_status = st.selectbox(
                            "回复状态",
                            ["不修改", "是", "否", "无法确认"],
                            key=f"reply_{tid}",
                        )

                    col_confirm, col_exclude = st.columns(2)

                    with col_confirm:
                        if st.button("✅ 确认并保存", key=f"confirm_{tid}"):
                            updates: dict = {}
                            if new_name != t.get("name", ""):
                                db.add_override("teacher", tid, "name",
                                                t.get("name", ""), new_name)
                                updates["name"] = new_name
                            if new_inst != t.get("institution", ""):
                                db.add_override("teacher", tid, "institution",
                                                t.get("institution", ""), new_inst)
                                updates["institution"] = new_inst
                            if new_status != "不修改":
                                db.add_override("teacher", tid, "reply_status",
                                                "", new_status)

                            updates["needs_review"] = 0
                            db.update_teacher(tid, updates)
                            st.success(f"✅ 已保存 {new_name or t.get('name', '')} 的修改")
                            st.rerun()

                    with col_exclude:
                        if st.button("🚫 排除此导师", key=f"exclude_{tid}"):
                            db.add_override("teacher", tid, "excluded", "", "true")
                            db.update_teacher(tid, {"needs_review": 0})
                            st.warning(f"已排除 {t.get('name', '')}")
                            st.rerun()

    # ── Tab 2: 疑似重复 ──
    with tab_dup:
        if not duplicates:
            st.success("🎉 未发现疑似重复的导师！")
        else:
            for dup in duplicates:
                dup_name = dup["name"]
                dup_teachers = dup["teachers"]
                reason = dup["reason"]

                with st.expander(
                    f"👥 {dup_name}（{len(dup_teachers)} 个条目）— {reason}",
                    expanded=False,
                ):
                    for dt in dup_teachers:
                        dt_emails = db.get_teacher_emails(dt["id"])
                        st.markdown(
                            f"- **ID {dt['id']}**: {dt.get('institution', '未知单位')} "
                            f"| 邮箱: {', '.join(dt_emails)} "
                            f"| 发送: {dt.get('send_count', 0)} 封"
                        )

                    st.markdown("---")

                    # 合并操作
                    if len(dup_teachers) == 2:
                        if st.button(f"🔗 合并为同一导师", key=f"merge_{dup_name}"):
                            _merge_two_teachers(
                                dup_teachers[0]["id"],
                                dup_teachers[1]["id"],
                                account_id,
                            )
                            st.success(f"✅ 已合并 {dup_name}")
                            st.rerun()
                    else:
                        st.info("多于 2 个条目时，请逐一在「待复核」中处理。")

    # ── Tab 3: 未知姓名 ──
    with tab_unknown:
        if not unknown_name:
            st.success("🎉 所有导师姓名均已识别！")
        else:
            for t in unknown_name:
                tid = t["id"]
                emails = db.get_teacher_emails(tid)

                col_info, col_action = st.columns([3, 2])
                with col_info:
                    st.markdown(
                        f"**{t.get('name', '未知')}** | "
                        f"邮箱: {', '.join(emails)} | "
                        f"单位: {t.get('institution', '未知')}"
                    )
                with col_action:
                    new_name = st.text_input(
                        "输入导师姓名",
                        key=f"unknown_name_{tid}",
                        placeholder="例如：张教授",
                    )
                    if new_name and st.button("保存", key=f"save_name_{tid}"):
                        db.add_override("teacher", tid, "name",
                                        t.get("name", ""), new_name)
                        db.update_teacher(tid, {"name": new_name, "needs_review": 0})
                        st.success(f"✅ 已保存为 {new_name}")
                        st.rerun()

                st.markdown("---")

    # ── Tab 4: 修改历史 ──
    with tab_history:
        all_overrides = []
        for t in teachers:
            overrides = db.get_overrides("teacher", t["id"])
            for o in overrides:
                all_overrides.append({
                    "导师": t.get("name", "未知"),
                    "字段": o.get("field_name", ""),
                    "旧值": o.get("old_value", ""),
                    "新值": o.get("new_value", ""),
                    "时间": o.get("created_at", ""),
                })

        if all_overrides:
            st.dataframe(
                all_overrides,
                use_container_width=True,
                column_config={
                    "导师": st.column_config.TextColumn(width="medium"),
                    "字段": st.column_config.TextColumn(width="small"),
                    "旧值": st.column_config.TextColumn(width="medium"),
                    "新值": st.column_config.TextColumn(width="medium"),
                    "时间": st.column_config.TextColumn(width="medium"),
                },
            )
        else:
            st.info("暂无人工修改记录。")


def _merge_two_teachers(tid_keep: int, tid_remove: int,
                        account_id: int) -> None:
    """合并两个导师记录"""
    conn = db.get_connection()

    # 转移邮件关联
    try:
        conn.execute(
            "UPDATE teacher_messages SET teacher_id=? WHERE teacher_id=?",
            (tid_keep, tid_remove),
        )
    except Exception:
        pass

    # 转移邮箱
    try:
        conn.execute(
            "UPDATE teacher_emails SET teacher_id=? WHERE teacher_id=?",
            (tid_keep, tid_remove),
        )
    except Exception:
        pass

    # 更新发送次数
    conn.execute(
        "UPDATE teachers SET send_count = "
        "(SELECT COUNT(*) FROM teacher_messages WHERE teacher_id=?), "
        "updated_at=datetime('now') WHERE id=?",
        (tid_keep, tid_keep),
    )

    # 删除被合并的导师
    conn.execute("DELETE FROM teachers WHERE id=?", (tid_remove,))
    conn.commit()
