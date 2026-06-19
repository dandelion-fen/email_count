"""
汇总统计页面 — 统计概览与一致性校验
"""
from __future__ import annotations

import streamlit as st

from src.merge_table import build_stats
from src.models import StatsOverview, MergedTeacherRow


def render() -> None:
    """渲染汇总统计页面"""
    st.header("📈 汇总统计")
    st.caption("查看套磁进度的整体统计数据与数据一致性校验。")

    # ── 检查前置条件 ──
    rows: list[MergedTeacherRow] = st.session_state.get("merged_rows", [])
    if not rows:
        st.warning("⚠️ 暂无分析数据，请先在「导师总表」页面运行分析。")
        return

    stats: StatsOverview = st.session_state.get("stats_overview")
    if not stats:
        stats = build_stats(rows)
        st.session_state["stats_overview"] = stats

    # ── 核心指标 ──
    st.subheader("📊 核心指标")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        _stat_card("👨‍🏫", "导师总数", str(stats.teacher_count), "#667eea", "#764ba2")
    with col2:
        _stat_card("✅", "已回复", str(stats.replied_teacher_count), "#43cea2", "#185a9d")
    with col3:
        _stat_card("📈", "回复率", f"{stats.reply_rate}%", "#f093fb", "#f5576c")
    with col4:
        _stat_card("⚠️", "待复核", str(stats.needs_review_count), "#ffecd2", "#fcb69f")

    st.markdown("")

    # ── 回复状态分布 ──
    st.subheader("📬 回复状态")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric("✅ 已确认回复", f"{stats.replied_teacher_count} 人")
    with col_b:
        st.metric("❌ 未回复", f"{stats.no_reply_count} 人")
    with col_c:
        st.metric("❓ 无法确认", f"{stats.uncertain_reply_count} 人")

    st.markdown("---")

    # ── 招生意向分布 ──
    st.subheader("🎯 招生意向分布")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("##### 积极意向")
        _intent_row("🟢", "明确愿意接收/欢迎加入", stats.positive_intent_count)
        _intent_row("🔵", "欢迎报名（仍需考核）", stats.welcome_apply_count)
        _intent_row("🟡", "建议参加夏令营/预推免", stats.suggest_camp_count)
        _intent_row("💬", "愿意进一步交流", stats.willing_to_talk_count)

    with col2:
        st.markdown("##### 其他情况")
        _intent_row("⏳", "暂时无法确定名额", stats.quota_uncertain_count)
        _intent_row("😐", "礼貌回复·态度不明确", stats.polite_no_intent_count)
        _intent_row("🔴", "名额已满/方向不符/拒绝", stats.negative_count)

    st.markdown("---")

    # ── 行动建议统计 ──
    st.subheader("🚀 行动建议")

    col_act1, col_act2 = st.columns(2)
    with col_act1:
        st.metric("🔴 需要立即回复", f"{stats.need_reply_now_count} 人",
                   help="导师已回复且建议立即回复")
    with col_act2:
        st.metric("🟡 建议跟进", f"{stats.suggest_followup_count} 人",
                   help="导师尚未回复，可考虑发送跟进邮件")

    st.markdown("---")

    # ── 一致性校验 ──
    st.subheader("🔍 数据一致性校验")

    if stats.consistency_valid:
        st.success(f"✅ {stats.consistency_message}")
    else:
        st.error(f"❌ {stats.consistency_message}")

    # 显示校验明细
    with st.expander("📋 校验明细", expanded=False):
        check_total = stats.replied_teacher_count + stats.no_reply_count + stats.uncertain_reply_count
        st.markdown(
            f"- 已回复: {stats.replied_teacher_count}\n"
            f"- 未回复: {stats.no_reply_count}\n"
            f"- 无法确认: {stats.uncertain_reply_count}\n"
            f"- **合计: {check_total}**\n"
            f"- 导师总数: {stats.teacher_count}\n"
            f"- 一致: {'✅ 是' if check_total == stats.teacher_count else '❌ 否'}"
        )


def _stat_card(icon: str, label: str, value: str,
               color1: str, color2: str) -> None:
    """渲染统计卡片"""
    st.markdown(
        f"""
        <div class="stat-card" style="background:linear-gradient(135deg,{color1},{color2});">
          <h3>{value}</h3>
          <p>{icon} {label}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _intent_row(icon: str, label: str, count: int) -> None:
    """渲染意向分布行"""
    st.markdown(f"{icon} **{label}**: {count} 人")
