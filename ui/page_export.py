"""
导出与数据管理页面 — 导出报表、清理数据
"""
from __future__ import annotations

import streamlit as st

from src.exporter import export_excel, export_csv, export_json, rows_to_dataframe, COLUMNS
from src.merge_table import build_stats
from src.models import MergedTeacherRow, StatsOverview
from src import database as db


def render() -> None:
    """渲染导出与数据管理页面"""
    st.header("💾 导出与数据管理")
    st.caption("导出分析结果为 Excel / CSV / JSON，或管理本地数据。")

    # ── 检查前置条件 ──
    account_id = st.session_state.get("account_id")
    rows: list[MergedTeacherRow] = st.session_state.get("merged_rows", [])

    tab_export, tab_manage = st.tabs(["📤 导出报表", "🗃️ 数据管理"])

    # ══════════════════════════════════════════════
    # Tab 1: 导出报表
    # ══════════════════════════════════════════════
    with tab_export:
        if not rows:
            st.warning("⚠️ 暂无分析结果可导出，请先在「导师总表」页面运行分析。")
        else:
            stats: StatsOverview = st.session_state.get("stats_overview")
            if not stats:
                stats = build_stats(rows)

            # ── 导出预览 ──
            st.subheader("📋 导出内容预览")

            st.info(
                f"将导出 **{len(rows)}** 位导师的分析结果，"
                f"包含 {len(COLUMNS)} 个字段。"
            )

            with st.expander("👁️ 预览导出数据", expanded=False):
                preview_df = rows_to_dataframe(rows)
                st.dataframe(
                    preview_df.head(10),
                    use_container_width=True,
                )
                if len(rows) > 10:
                    st.caption(f"（仅显示前 10 行，共 {len(rows)} 行）")

            # ── 隐私提醒 ──
            st.markdown("---")
            st.warning(
                "⚠️ **导出前请注意**\n\n"
                "- 导出文件包含邮件主题和回复摘要等信息\n"
                "- 不包含邮箱授权码或 API Key\n"
                "- 请妥善保管导出文件，避免泄露导师联系方式\n"
                "- 建议不要将导出文件上传到公开平台"
            )

            # ── 导出按钮 ──
            st.subheader("📥 选择导出格式")

            col_excel, col_csv, col_json = st.columns(3)

            with col_excel:
                if st.button("📊 导出 Excel", use_container_width=True, type="primary"):
                    try:
                        filepath = export_excel(rows, stats)
                        st.success(f"✅ Excel 导出成功！")
                        st.code(filepath, language=None)

                        # 提供下载按钮
                        with open(filepath, "rb") as f:
                            st.download_button(
                                "⬇️ 下载 Excel 文件",
                                data=f.read(),
                                file_name=filepath.split("\\")[-1].split("/")[-1],
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True,
                            )
                    except Exception as e:
                        st.error(f"❌ 导出失败: {type(e).__name__}: {e}")

            with col_csv:
                if st.button("📄 导出 CSV", use_container_width=True):
                    try:
                        filepath = export_csv(rows)
                        st.success(f"✅ CSV 导出成功！")
                        st.code(filepath, language=None)

                        with open(filepath, "rb") as f:
                            st.download_button(
                                "⬇️ 下载 CSV 文件",
                                data=f.read(),
                                file_name=filepath.split("\\")[-1].split("/")[-1],
                                mime="text/csv",
                                use_container_width=True,
                            )
                    except Exception as e:
                        st.error(f"❌ 导出失败: {type(e).__name__}: {e}")

            with col_json:
                if st.button("📝 导出 JSON", use_container_width=True):
                    try:
                        filepath = export_json(rows, stats)
                        st.success(f"✅ JSON 导出成功！")
                        st.code(filepath, language=None)

                        with open(filepath, "rb") as f:
                            st.download_button(
                                "⬇️ 下载 JSON 文件",
                                data=f.read(),
                                file_name=filepath.split("\\")[-1].split("/")[-1],
                                mime="application/json",
                                use_container_width=True,
                            )
                    except Exception as e:
                        st.error(f"❌ 导出失败: {type(e).__name__}: {e}")

    # ══════════════════════════════════════════════
    # Tab 2: 数据管理
    # ══════════════════════════════════════════════
    with tab_manage:
        if not account_id:
            st.warning("⚠️ 请先完成「邮箱连接」步骤。")
        else:
            st.subheader("🗃️ 数据管理")

            email = st.session_state.get("email_addr", "未知")
            st.info(f"当前账户: **{email}** (ID: {account_id})")

            st.markdown("---")

            # ── 清除分析数据 ──
            st.markdown("##### 🧹 清除分析结果")
            st.caption("保留已下载的邮件数据，仅清除导师识别、线程关联、回复检测等分析结果。再次运行分析即可重建。")

            if st.button("🧹 清除分析结果", use_container_width=True):
                st.session_state["confirm_clear_analysis"] = True

            if st.session_state.get("confirm_clear_analysis"):
                st.warning("⚠️ 确认要清除所有分析结果吗？邮件数据会保留。")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("✅ 确认清除", key="confirm_analysis_yes"):
                        try:
                            db.clear_analysis_data(account_id)
                            st.session_state.pop("merged_rows", None)
                            st.session_state.pop("stats_overview", None)
                            st.session_state.pop("contact_ids", None)
                            st.session_state.pop("confirm_clear_analysis", None)
                            st.success("✅ 分析结果已清除！")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ 清除失败: {e}")
                with col_no:
                    if st.button("❌ 取消", key="confirm_analysis_no"):
                        st.session_state.pop("confirm_clear_analysis", None)
                        st.rerun()

            st.markdown("---")

            # ── 清除所有数据 ──
            st.markdown("##### 🗑️ 清除全部数据")
            st.caption("删除当前账户的所有数据，包括邮件、导师、分析结果等。此操作不可恢复。")

            if st.button("🗑️ 清除全部数据", type="secondary", use_container_width=True):
                st.session_state["confirm_clear_all"] = True

            if st.session_state.get("confirm_clear_all"):
                st.error("⚠️ 危险操作！这将删除所有已下载的邮件和分析数据，无法恢复！")
                col_yes2, col_no2 = st.columns(2)
                with col_yes2:
                    if st.button("⚠️ 确认删除全部", key="confirm_all_yes"):
                        try:
                            db.clear_all_data(account_id)
                            # 清空 session
                            keys_to_clear = [
                                "merged_rows", "stats_overview", "contact_ids",
                                "scan_result", "scan_folders", "folders",
                                "folder_selections", "folder_type_overrides",
                                "connected", "account_id", "confirm_clear_all",
                            ]
                            for key in keys_to_clear:
                                st.session_state.pop(key, None)
                            st.success("✅ 所有数据已清除！请重新连接邮箱。")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ 清除失败: {e}")
                with col_no2:
                    if st.button("❌ 取消", key="confirm_all_no"):
                        st.session_state.pop("confirm_clear_all", None)
                        st.rerun()
