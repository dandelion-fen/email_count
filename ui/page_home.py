"""
首页 — 欢迎页面与快速入门
"""
from __future__ import annotations

import streamlit as st


def render() -> None:
    """渲染首页"""
    st.title("📬 保研套磁统计工具")
    st.markdown("##### 一站式追踪你的保研套磁进度，智能分析导师回复")

    st.markdown("---")

    # ── 工具简介 ──
    st.markdown(
        """
        本工具帮助保研同学自动统计套磁邮件的发送与回复情况。它能：

        - 🔍 **自动扫描** 网易邮箱中的套磁相关邮件
        - 🧵 **智能关联** 发件与回复，构建完整会话线程
        - 👨‍🏫 **识别导师** 自动提取导师姓名、单位、邮箱
        - 📊 **分析回复** 判断导师的招生意向与后续建议
        - 📈 **生成报表** 一键导出 Excel / CSV / JSON
        """
    )

    # ── 数据隐私声明 ──
    st.markdown("---")
    st.subheader("🔒 数据隐私承诺")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            """
            <div class="stat-card" style="background:linear-gradient(135deg,#43cea2,#185a9d);">
              <h3>🔐</h3>
              <p>只读访问邮箱<br>不会修改、删除或发送任何邮件</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            """
            <div class="stat-card" style="background:linear-gradient(135deg,#667eea,#764ba2);">
              <h3>💻</h3>
              <p>数据保存在本机<br>不上传到任何远程服务器</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            """
            <div class="stat-card" style="background:linear-gradient(135deg,#f093fb,#f5576c);">
              <h3>🔑</h3>
              <p>授权码默认不保存<br>可选择使用系统密钥环存储</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("")

    # ── 快速开始 ──
    st.markdown("---")
    st.subheader("🚀 快速开始")

    steps = [
        ("1️⃣", "邮箱连接", "在「邮箱连接」页面填写邮箱地址和客户端授权码，测试连接是否成功。"),
        ("2️⃣", "选择文件夹", "在「文件夹选择」页面确认要扫描的文件夹（收件箱、已发送等）。"),
        ("3️⃣", "扫描邮件", "在「扫描与同步」页面启动邮件扫描，等待同步完成。"),
        ("4️⃣", "查看结果", "在「导师总表」页面运行分析，查看套磁统计与导师回复详情。"),
        ("5️⃣", "导出报表", "在「导出与数据管理」页面一键导出分析结果。"),
    ]

    for icon, title, desc in steps:
        st.markdown(f"**{icon} {title}** — {desc}")

    # ── 重要警告 ──
    st.markdown("---")
    st.warning(
        "⚠️ **请使用网易邮箱的「客户端授权码」，而非登录密码！**\n\n"
        "登录网易邮箱 → 设置 → POP3/SMTP/IMAP → 开启 IMAP 服务 → 生成客户端授权码。\n\n"
        "授权码与登录密码是两回事，使用登录密码将无法连接。"
    )

    st.info(
        "💡 **首次使用建议**：先用少量日期范围测试，确认功能正常后再扫描全部邮件。"
    )
