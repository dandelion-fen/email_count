"""
导师总表页面 — 运行分析、展示合并表、支持人工覆盖
"""
from __future__ import annotations

import streamlit as st
import pandas as pd

from src import database as db
from src.contact_filter import batch_identify
from src.thread_builder import build_threads
from src.teacher_dedup import identify_teachers, check_duplicate_teachers
import os
from src.reply_detector import detect_all_replies
from src.merge_table import build_merged_table, build_stats
from src.models import ReplyStatus, MergedTeacherRow
from src.ai_analyzer import analyze_reply_with_ai


def render() -> None:
    """渲染导师总表页面"""
    st.header("📊 导师总表")
    st.caption("运行完整分析流程，查看每位导师的套磁进度与回复详情。")

    # ── 检查前置条件 ──
    account_id = st.session_state.get("account_id")
    if not account_id:
        st.warning("⚠️ 请先完成「邮箱连接」和「扫描与同步」步骤。")
        return

    # ── 运行分析 ──
    col_btn, col_toggle = st.columns([3, 1])
    with col_toggle:
        use_ai = st.toggle(
            "结合 AI 语义分析",
            value=st.session_state.get("use_ai_in_batch", False),
            help="开启后在运行分析时自动调用 API 深度提取导师的回复意向（需在「AI 分析设置」配置好 API）",
        )
        st.session_state["use_ai_in_batch"] = use_ai
        
    with col_btn:
        run_clicked = st.button("🔬 运行分析", type="primary", use_container_width=True)

    if run_clicked:
        _run_analysis(account_id, use_ai=use_ai)

    # ── 显示结果 ──
    rows: list[MergedTeacherRow] = st.session_state.get("merged_rows", [])
    if not rows:
        st.info("💡 点击上方「运行分析」按钮开始分析已扫描的邮件。")
        return

    stats = st.session_state.get("stats_overview")

    # ── 顶部统计 ──
    if stats:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("👨‍🏫 导师总数", stats.teacher_count)
        with col2:
            st.metric("✅ 已回复", stats.replied_teacher_count)
        with col3:
            st.metric("📈 回复率", f"{stats.reply_rate}%")
        with col4:
            st.metric("⚠️ 待复核", stats.needs_review_count)

    st.markdown("---")

    # ── 搜索与过滤 ──
    col_search, col_filter = st.columns([3, 2])
    with col_search:
        search_text = st.text_input(
            "🔍 搜索",
            placeholder="输入导师姓名、学校或邮箱关键词",
            label_visibility="collapsed",
        )
    with col_filter:
        filter_reply = st.selectbox(
            "筛选回复状态",
            ["全部", "已回复", "未回复", "无法确认"],
            label_visibility="collapsed",
        )

    # ── 构建 DataFrame ──
    display_data = _rows_to_display(rows)
    df = pd.DataFrame(display_data)

    # 应用搜索
    if search_text:
        mask = df.apply(
            lambda row: search_text.lower() in " ".join(str(v).lower() for v in row.values),
            axis=1,
        )
        df = df[mask]

    # 应用过滤
    if filter_reply != "全部":
        reply_map = {"已回复": "是", "未回复": "否", "无法确认": "无法确认"}
        df = df[df["回复状态"] == reply_map.get(filter_reply, "")]

    # ── 显示数据表 ──
    st.markdown(f"📋 显示 **{len(df)}** / {len(rows)} 位导师")

    # 使用 st.data_editor 支持人工覆盖
    tab_view, tab_edit = st.tabs(["📋 查看模式", "✏️ 编辑模式"])

    with tab_view:
        # 带颜色标记的查看
        st.dataframe(
            df,
            use_container_width=True,
            height=min(len(df) * 40 + 50, 600),
            column_config={
                "序号": st.column_config.NumberColumn(width="small"),
                "导师姓名": st.column_config.TextColumn(width="medium"),
                "学校/单位": st.column_config.TextColumn(width="medium"),
                "回复状态": st.column_config.TextColumn(width="small"),
                "招生意向": st.column_config.TextColumn(width="large"),
                "置信度": st.column_config.ProgressColumn(
                    min_value=0, max_value=1, format="%.0%%",
                ),
                "需要复核": st.column_config.CheckboxColumn(width="small"),
            },
        )

    with tab_edit:
        st.caption("⚠️ 编辑后请点击下方「保存修改」按钮。人工修改优先于自动判断。")

        editable_df = df[["序号", "导师姓名", "学校/单位", "回复状态", "招生意向", "建议行动"]].copy()
        edited = st.data_editor(
            editable_df,
            use_container_width=True,
            num_rows="fixed",
            key="teacher_editor",
        )

        if st.button("💾 保存修改", use_container_width=True):
            _save_overrides(rows, edited, account_id)
            st.success("✅ 修改已保存！")

    # ── 可展开的证据详情 ──
    st.markdown("---")
    st.subheader("🔍 证据详情")

    for row in rows:
        if search_text and search_text.lower() not in f"{row.teacher_name} {row.institution}".lower():
            continue
        if filter_reply != "全部":
            reply_map = {"已回复": ReplyStatus.YES, "未回复": ReplyStatus.NO, "无法确认": ReplyStatus.UNCERTAIN}
            if row.has_real_reply != reply_map.get(filter_reply):
                continue

        # 回复状态标签
        if row.has_real_reply == ReplyStatus.YES:
            tag = '<span class="tag-positive">✅ 已回复</span>'
        elif row.has_real_reply == ReplyStatus.NO:
            tag = '<span class="tag-negative">❌ 未回复</span>'
        else:
            tag = '<span class="tag-uncertain">❓ 无法确认</span>'

        with st.expander(f"{row.index}. {row.teacher_name} — {row.institution}"):
            st.markdown(tag, unsafe_allow_html=True)
            st.markdown(f"**邮箱:** {row.teacher_email}")
            st.markdown(f"**发送:** {row.send_count} 封 ({row.first_sent_at} ~ {row.last_sent_at})")
            st.markdown(f"**往来:** {row.correspondence_summary}")

            if row.reply_content_summary:
                st.markdown(f"**回复摘要:** {row.reply_content_summary}")
            if row.evidence_sentences:
                st.markdown("**证据句:**")
                for s in row.evidence_sentences.split("; "):
                    if s.strip():
                        st.markdown(f"  > {s.strip()}")
            if row.admission_intent:
                st.markdown(f"**招生意向:** {row.admission_intent}")
            if row.recommended_next_step:
                st.markdown(f"**建议:** {row.recommended_next_step}")


def _run_analysis(account_id: int, use_ai: bool = False) -> None:
    """执行完整分析流程"""
    progress = st.progress(0, text="正在分析……")

    try:
        # Step 1: 识别套磁邮件
        progress.progress(0.1, text="步骤 1/5: 识别套磁邮件……")
        all_msgs = db.get_all_messages(account_id)
        candidates = batch_identify(all_msgs)
        contact_ids = [c.message_db_id for c in candidates if c.is_contact_email]
        st.session_state["contact_ids"] = contact_ids

        # Step 2: 构建会话线程
        progress.progress(0.3, text="步骤 2/5: 构建会话线程……")
        thread_count = build_threads(account_id)

        # Step 3: 识别导师（含去重）
        progress.progress(0.5, text="步骤 3/5: 识别导师……")
        teacher_count = identify_teachers(account_id, contact_ids)

        # Step 4: 检测回复
        progress.progress(0.7, text="步骤 4/5: 检测回复……")
        detect_all_replies(account_id)

        # 如果开启了 AI 分析，自动为所有新识别的、已收到回复的导师运行 AI 语义深度分析
        ai_success_count = 0
        if use_ai:
            api_key = st.session_state.get("openai_api_key") or os.environ.get("OPENAI_API_KEY")
            base_url = st.session_state.get("openai_base_url") or os.environ.get("OPENAI_BASE_URL")
            model = st.session_state.get("openai_model") or os.environ.get("OPENAI_MODEL")
            
            if not api_key:
                st.warning("⚠️ 未检测到已配置的 AI API Key，已跳过 AI 步骤。请先在「AI 分析设置」中配置。")
            else:
                progress.progress(0.8, text="步骤 4.5/5: 正在进行 AI 深度语义分析……")
                teachers = db.get_all_teachers(account_id)
                user_email = st.session_state.get("email_addr", "")
                
                for t in teachers:
                    tid = t["id"]
                    # 避免重复对已分析过的导师重复调用 API
                    if db.get_latest_analysis(tid, "ai"):
                        continue
                    
                    teacher_msgs = db.get_teacher_messages(tid)
                    reply_bodies = []
                    for msg in teacher_msgs:
                        if not msg.get("is_sent_by_me") and not msg.get("is_auto_reply"):
                            body = msg.get("body_text", "") or msg.get("body_html_text", "")
                            if body.strip():
                                reply_bodies.append(body)
                    
                    if reply_bodies:
                        full_body = "\n---\n".join(reply_bodies)
                        try:
                            result = analyze_reply_with_ai(
                                full_body,
                                teacher_name=t["name"],
                                user_email=user_email,
                                api_key=api_key,
                                base_url=base_url,
                                model=model,
                            )
                            if result:
                                db.insert_analysis({
                                    "teacher_id": tid,
                                    "analysis_type": "ai",
                                    "reply_status": "",
                                    "reply_summary": result.reply_summary,
                                    "evidence_sentences": "|".join(result.evidence_sentences),
                                    "admission_intent": result.admission_intent.value,
                                    "action_required": result.action_required.value,
                                    "recommended_next_step": result.recommended_next_step,
                                    "actual_responder_role": result.actual_responder_role,
                                    "confidence": result.confidence,
                                    "ambiguity_reason": result.ambiguity_reason,
                                    "my_reply_status": "",
                                    "model_name": model or "gpt-4o-mini",
                                    "analysis_time": "",
                                    "input_hash": "",
                                })
                                ai_success_count += 1
                        except Exception:
                            pass

        # Step 5: 生成合并表
        progress.progress(0.9, text="步骤 5/5: 生成导师总表……")
        rows = build_merged_table(account_id)
        stats = build_stats(rows)

        # 保存到 session
        st.session_state["merged_rows"] = rows
        st.session_state["stats_overview"] = stats

        progress.progress(1.0, text="分析完成！")
        msg_suffix = f" 并自动完成了 {ai_success_count} 位导师的 AI 语义深度解析。" if ai_success_count > 0 else "。"
        st.success(
            f"✅ 分析完成！识别 {len(contact_ids)} 封套磁邮件，"
            f"{thread_count} 个会话线程，{teacher_count} 位导师"
            f"{msg_suffix}"
        )

    except Exception as e:
        st.error(f"❌ 分析过程中出错: {type(e).__name__}: {e}")


def _rows_to_display(rows: list[MergedTeacherRow]) -> list[dict]:
    """将合并表行转为展示字典列表"""
    data = []
    for row in rows:
        data.append({
            "序号": row.index,
            "导师姓名": row.teacher_name,
            "学校/单位": row.institution,
            "邮箱": row.teacher_email,
            "发送次数": row.send_count,
            "回复状态": row.has_real_reply.value,
            "回复时间": row.teacher_reply_time,
            "回复摘要": row.reply_content_summary,
            "招生意向": row.admission_intent,
            "我是否回复": row.my_reply_status.value,
            "建议行动": row.action_required,
            "置信度": row.confidence,
            "需要复核": row.needs_review,
        })
    return data


def _save_overrides(rows: list[MergedTeacherRow], edited_df: pd.DataFrame,
                    account_id: int) -> None:
    """保存人工覆盖"""
    teachers = db.get_all_teachers(account_id)
    teacher_by_idx: dict[int, dict] = {}
    for t in teachers:
        teacher_by_idx[t["id"]] = t

    for i, edited_row in edited_df.iterrows():
        if i >= len(rows):
            break
        original = rows[i]
        teacher_id = 0
        # 查找对应的导师 ID
        for t in teachers:
            if t.get("name") == original.teacher_name:
                teacher_id = t["id"]
                break
        if not teacher_id:
            continue

        # 检查并保存变更
        field_map = {
            "导师姓名": ("name", original.teacher_name),
            "学校/单位": ("institution", original.institution),
            "回复状态": ("reply_status", original.has_real_reply.value),
            "招生意向": ("admission_intent", original.admission_intent),
            "建议行动": ("action_required", original.action_required),
        }

        for col_name, (field_name, old_val) in field_map.items():
            new_val = str(edited_row.get(col_name, ""))
            if new_val and new_val != str(old_val):
                db.add_override("teacher", teacher_id, field_name,
                                str(old_val), new_val)
