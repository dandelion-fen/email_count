"""
邮箱连接页面 — 配置邮箱、测试连接、保存到 session
"""
from __future__ import annotations

import streamlit as st
from datetime import date, timedelta

from src.imap_client import IMAPReadOnlyClient
from src.database import init_db, upsert_account


def render() -> None:
    """渲染邮箱连接页面"""
    st.header("🔗 邮箱连接")
    st.caption("配置你的网易邮箱连接，测试成功后方可进行邮件扫描。")

    # ── 连接表单 ──
    with st.container():
        st.subheader("📧 邮箱信息")

        email_addr = st.text_input(
            "邮箱地址",
            value=st.session_state.get("email_addr", ""),
            placeholder="your_email@163.com",
            help="请输入完整的网易邮箱地址",
        )

        col_server, col_port, col_ssl = st.columns([3, 1, 1])
        with col_server:
            imap_server = st.text_input(
                "IMAP 服务器",
                value=st.session_state.get("imap_server", "imap.163.com"),
                help="网易邮箱默认为 imap.163.com",
            )
        with col_port:
            imap_port = st.number_input(
                "端口",
                value=st.session_state.get("imap_port", 993),
                min_value=1,
                max_value=65535,
                help="SSL 默认端口 993",
            )
        with col_ssl:
            use_ssl = st.toggle(
                "启用 SSL",
                value=st.session_state.get("use_ssl", True),
                help="强烈建议保持开启",
            )

    # ── 授权码 ──
    with st.container():
        st.subheader("🔑 客户端授权码")
        st.caption("⚠️ 请使用客户端授权码（非登录密码）")

        auth_code = st.text_input(
            "授权码",
            type="password",
            value="",
            placeholder="请输入客户端授权码",
            help="在网易邮箱「设置 → POP3/IMAP/SMTP」中生成",
        )

        save_to_keyring = st.checkbox(
            "将授权码保存到系统密钥环（可选）",
            value=False,
            help="使用操作系统的安全存储保存授权码，下次打开时无需重复输入。"
                 "授权码不会保存到代码或配置文件中。",
        )

    # ── 扫描范围 ──
    with st.container():
        st.subheader("📅 扫描范围")

        col_start, col_end = st.columns(2)
        with col_start:
            default_start = date.today() - timedelta(days=365)
            scan_start = st.date_input("开始日期", value=default_start)
        with col_end:
            default_end = date.today()
            scan_end = st.date_input("结束日期", value=default_end)

        if scan_start > scan_end:
            st.error("❌ 开始日期不能晚于结束日期")
            return

        col_spam, col_archive = st.columns(2)
        with col_spam:
            include_spam = st.toggle(
                "扫描垃圾邮件文件夹",
                value=st.session_state.get("include_spam", False),
                help="部分导师回复可能被误判为垃圾邮件",
            )
        with col_archive:
            include_archive = st.toggle(
                "扫描归档文件夹",
                value=st.session_state.get("include_archive", False),
                help="如果你有归档邮件的习惯，建议开启",
            )

    st.markdown("---")

    # ── 测试连接 ──
    if st.button("🔌 测试连接", type="primary", use_container_width=True):
        if not email_addr:
            st.error("❌ 请输入邮箱地址")
            return
        if not auth_code:
            st.error("❌ 请输入客户端授权码")
            return

        with st.spinner("正在连接邮箱服务器……"):
            client = IMAPReadOnlyClient(
                server=imap_server,
                port=int(imap_port),
                use_ssl=use_ssl,
            )
            result = client.connect(email_addr, auth_code)

        if result["success"]:
            st.success("✅ 连接成功！")

            # 获取文件夹信息
            folders = client.list_folders()

            # 获取每个文件夹的邮件数
            folder_details = []
            for f in folders:
                status = client.get_folder_status(f["name"])
                folder_details.append({
                    "name": f["name"],
                    "raw_name": f.get("raw_name", f["name"]),
                    "flags": f.get("flags", []),
                    "message_count": status.get("message_count", 0),
                    "readonly": status.get("readonly", True),
                })

            client.disconnect()

            # 显示连接详情
            col_a, col_b = st.columns(2)
            with col_a:
                st.metric("📁 发现文件夹", f"{len(folders)} 个")
                total_msgs = sum(fd["message_count"] for fd in folder_details)
                st.metric("📨 邮件总数", f"{total_msgs:,} 封")
            with col_b:
                st.metric("🖥️ 服务器", f"{imap_server}:{imap_port}")
                st.metric("🔒 访问模式", "只读 (readonly)")

            # 显示文件夹列表
            with st.expander("📂 文件夹详情", expanded=False):
                for fd in folder_details:
                    st.markdown(
                        f"- **{fd['name']}** — {fd['message_count']:,} 封邮件"
                    )

            # 服务器能力
            caps = result.get("capabilities", [])
            if caps:
                with st.expander("🔧 服务器能力", expanded=False):
                    st.code(", ".join(caps))

            # ── 保存到 session state ──
            st.session_state["email_addr"] = email_addr
            st.session_state["imap_server"] = imap_server
            st.session_state["imap_port"] = int(imap_port)
            st.session_state["use_ssl"] = use_ssl
            st.session_state["auth_code"] = auth_code
            st.session_state["scan_start"] = scan_start
            st.session_state["scan_end"] = scan_end
            st.session_state["include_spam"] = include_spam
            st.session_state["include_archive"] = include_archive
            st.session_state["folders"] = folder_details
            st.session_state["connected"] = True

            # 保存账户到数据库
            init_db()
            account_id = upsert_account(
                email_addr, imap_server, int(imap_port), use_ssl)
            st.session_state["account_id"] = account_id

            # 可选：保存到 keyring
            if save_to_keyring and auth_code:
                try:
                    import keyring
                    keyring.set_password(
                        "mail_tracker", email_addr, auth_code)
                    st.success("🔐 授权码已保存到系统密钥环")
                except ImportError:
                    st.warning(
                        "⚠️ keyring 库未安装，无法保存授权码。"
                        "可运行 `pip install keyring` 安装。"
                    )
                except Exception as e:
                    st.warning(f"⚠️ 保存到密钥环失败: {type(e).__name__}")

            st.info("✅ 连接信息已保存，请前往「文件夹选择」页面继续。")

        else:
            st.error(f"❌ {result['message']}")

    # ── 显示当前连接状态 ──
    if st.session_state.get("connected"):
        st.markdown("---")
        st.success(
            f"✅ 当前已连接: **{st.session_state.get('email_addr', '')}** "
            f"({st.session_state.get('imap_server', '')})"
        )

    # ── 尝试从 keyring 加载 ──
    if not auth_code and email_addr:
        try:
            import keyring
            saved = keyring.get_password("mail_tracker", email_addr)
            if saved:
                st.info("💡 检测到系统密钥环中保存有该邮箱的授权码，可直接测试连接。")
        except (ImportError, Exception):
            pass
