"""
扫描与同步页面 — 启动邮件扫描、显示进度、查看结果
"""
from __future__ import annotations

import streamlit as st

from src.imap_client import IMAPReadOnlyClient
from src.mail_sync import full_sync
from src.models import ScanProgress


def render() -> None:
    """渲染扫描与同步页面"""
    st.header("🔄 扫描与同步")
    st.caption("从邮箱服务器下载邮件数据到本地数据库，支持增量同步。")

    # ── 检查前置条件 ──
    if not st.session_state.get("connected"):
        st.warning("⚠️ 请先在「邮箱连接」页面完成连接测试。")
        return

    scan_folders = st.session_state.get("scan_folders", [])
    if not scan_folders:
        st.warning("⚠️ 请先在「文件夹选择」页面选择需要扫描的文件夹。")
        return

    # ── 扫描预览 ──
    st.subheader("📋 扫描计划")

    total_est = 0
    for f in scan_folders:
        count = f.get("message_count", 0)
        total_est += count
        st.markdown(f"- **{f['name']}** — 约 {count:,} 封邮件（{f.get('folder_type', 'other')}）")

    st.info(f"📊 共 {len(scan_folders)} 个文件夹，预计 {total_est:,} 封邮件")

    st.markdown("---")

    # ── 扫描控制 ──
    if "scan_running" not in st.session_state:
        st.session_state["scan_running"] = False
    if "scan_cancelled" not in st.session_state:
        st.session_state["scan_cancelled"] = False

    col_start, col_cancel = st.columns(2)

    with col_start:
        start_clicked = st.button(
            "🚀 开始扫描",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.get("scan_running", False),
        )

    with col_cancel:
        cancel_clicked = st.button(
            "⏹️ 取消扫描",
            use_container_width=True,
            disabled=not st.session_state.get("scan_running", False),
        )

    if cancel_clicked:
        st.session_state["scan_cancelled"] = True
        st.warning("⏹️ 正在取消扫描……")

    # ── 执行扫描 ──
    if start_clicked:
        st.session_state["scan_running"] = True
        st.session_state["scan_cancelled"] = False

        # 进度显示
        progress_bar = st.progress(0, text="准备中……")
        status_text = st.empty()
        detail_container = st.container()

        def progress_callback(progress: ScanProgress) -> None:
            """更新进度条"""
            if progress.total_folders > 0:
                folder_pct = (progress.current_folder_index - 1) / progress.total_folders
            else:
                folder_pct = 0

            if progress.total_messages > 0:
                msg_pct = progress.current_message / progress.total_messages
            else:
                msg_pct = 0

            total_pct = min(folder_pct + msg_pct / max(progress.total_folders, 1), 1.0)
            progress_bar.progress(
                total_pct,
                text=f"文件夹 {progress.current_folder_index}/{progress.total_folders}: "
                     f"{progress.current_folder}"
            )
            status_text.markdown(
                f"📧 邮件 {progress.current_message}/{progress.total_messages} | "
                f"❌ 错误 {progress.errors}"
            )

        def cancel_check() -> bool:
            """检查是否取消"""
            return st.session_state.get("scan_cancelled", False)

        # 建立连接并扫描
        try:
            client = IMAPReadOnlyClient(
                server=st.session_state["imap_server"],
                port=st.session_state["imap_port"],
                use_ssl=st.session_state["use_ssl"],
            )
            conn_result = client.connect(
                st.session_state["email_addr"],
                st.session_state["auth_code"],
            )

            if not conn_result["success"]:
                st.error(f"❌ 连接失败: {conn_result['message']}")
                st.session_state["scan_running"] = False
                return

            # 执行全量同步
            result = full_sync(
                client=client,
                account_id=st.session_state["account_id"],
                folders=scan_folders,
                my_email=st.session_state["email_addr"],
                progress_callback=progress_callback,
                cancel_check=cancel_check,
            )

            client.disconnect()

        except Exception as e:
            st.error(f"❌ 扫描过程中出错: {type(e).__name__}: {e}")
            st.session_state["scan_running"] = False
            return

        st.session_state["scan_running"] = False
        st.session_state["scan_result"] = result

        # 完成
        progress_bar.progress(1.0, text="扫描完成！")

        if result["status"] == "cancelled":
            st.warning("⏹️ 扫描已被用户取消")
        else:
            st.success("✅ 扫描完成！")

    # ── 显示扫描结果 ──
    scan_result = st.session_state.get("scan_result")
    if scan_result:
        st.markdown("---")
        st.subheader("📊 扫描结果")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📁 扫描文件夹", f"{scan_result.get('folders', 0)} 个")
        with col2:
            st.metric("📨 同步邮件", f"{scan_result.get('synced', 0)} 封")
        with col3:
            st.metric("❌ 错误数", f"{scan_result.get('errors', 0)}")
        with col4:
            status_label = {
                "completed": "✅ 完成",
                "cancelled": "⏹️ 已取消",
            }.get(scan_result.get("status", ""), scan_result.get("status", ""))
            st.metric("状态", status_label)

        # 详细结果
        details = scan_result.get("details", [])
        if details:
            with st.expander("📂 各文件夹扫描详情", expanded=False):
                for d in details:
                    synced = d.get("synced", 0)
                    total = d.get("total", 0)
                    errors = d.get("errors", 0)
                    icon = "✅" if errors == 0 else "⚠️"
                    st.markdown(
                        f"{icon} **{d['folder']}** — "
                        f"扫描 {total} 封，同步 {synced} 封"
                        f"{f'，{errors} 个错误' if errors else ''}"
                    )

        st.info("✅ 扫描完成！请前往「导师总表」页面运行分析。")
