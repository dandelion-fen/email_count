"""
文件夹选择页面 — 选择要扫描的文件夹与分类
"""
from __future__ import annotations

import streamlit as st

from src.folder_discovery import categorize_folders, classify_folder
from src.models import FolderType


# 文件夹类型的中文标签和图标
_TYPE_LABELS: dict[str, tuple[str, str]] = {
    "inbox": ("📥", "收件箱"),
    "sent": ("📤", "已发送"),
    "spam": ("🚫", "垃圾邮件"),
    "archive": ("📦", "归档"),
    "drafts": ("📝", "草稿"),
    "trash": ("🗑️", "已删除"),
    "other": ("📂", "其他"),
}

def select_all_callback(folders_list):
    selected_folders = {f["name"] for f in folders_list}
    st.session_state["folder_selections"] = selected_folders
    for f in folders_list:
        st.session_state[f"scan_{f['name']}"] = True
    
    # 自动构建并保存 scan_folders
    type_overrides = st.session_state.get("folder_type_overrides", {})
    scan_folders = []
    for f in folders_list:
        ft = type_overrides.get(f["name"], f.get("folder_type", "other"))
        scan_folders.append({
            "name": f["name"],
            "raw_name": f.get("raw_name", f["name"]),
            "flags": f.get("flags", []),
            "folder_type": ft,
            "message_count": f.get("message_count", 0),
        })
    st.session_state["scan_folders"] = scan_folders


def select_none_callback(folders_list):
    st.session_state["folder_selections"] = set()
    for f in folders_list:
        st.session_state[f"scan_{f['name']}"] = False
    st.session_state["scan_folders"] = []


def reset_default_callback(folders_list):
    if "folder_selections" in st.session_state:
        del st.session_state["folder_selections"]
    if "folder_type_overrides" in st.session_state:
        del st.session_state["folder_type_overrides"]
    if "scan_folders" in st.session_state:
        del st.session_state["scan_folders"]
    for k in list(st.session_state.keys()):
        if k.startswith("scan_") or k.startswith("type_"):
            del st.session_state[k]


def render() -> None:
    """渲染文件夹选择页面"""
    st.header("📁 文件夹选择")
    st.caption("选择需要扫描的文件夹，并确认文件夹类型分类是否正确。")

    # ── 检查前置条件 ──
    if not st.session_state.get("connected"):
        st.warning("⚠️ 请先在「邮箱连接」页面完成连接测试。")
        return

    folders = st.session_state.get("folders", [])
    if not folders:
        st.warning("⚠️ 未发现文件夹信息，请返回「邮箱连接」页面重新测试连接。")
        return

    # ── 分类文件夹 ──
    categories = categorize_folders(folders)

    # ── 初始化选择状态 ──
    if "folder_selections" not in st.session_state:
        default_scan = set()
        for f in folders:
            ft = classify_folder(f["name"], f.get("flags", []))
            # 默认扫描收件箱和已发送
            if ft in (FolderType.INBOX, FolderType.SENT):
                default_scan.add(f["name"])
            # 根据用户设置决定是否扫描垃圾邮件和归档
            elif ft == FolderType.SPAM and st.session_state.get("include_spam"):
                default_scan.add(f["name"])
            elif ft == FolderType.ARCHIVE and st.session_state.get("include_archive"):
                default_scan.add(f["name"])
        st.session_state["folder_selections"] = default_scan

    if "folder_type_overrides" not in st.session_state:
        st.session_state["folder_type_overrides"] = {}

    # ── 显示文件夹分组 ──
    st.subheader("📂 发现的文件夹")

    type_options = [t.value for t in FolderType]
    type_display = {t.value: f"{_TYPE_LABELS.get(t.value, ('📂', t.value))[0]} {_TYPE_LABELS.get(t.value, ('📂', t.value))[1]}" for t in FolderType}

    selected_folders: set[str] = set(st.session_state["folder_selections"])
    type_overrides: dict[str, str] = dict(st.session_state["folder_type_overrides"])

    for cat_key, cat_folders in categories.items():
        if not cat_folders:
            continue

        icon, label = _TYPE_LABELS.get(cat_key, ("📂", cat_key))

        with st.expander(f"{icon} {label}（{len(cat_folders)} 个文件夹）", expanded=True):
            for f in cat_folders:
                fname = f["name"]
                msg_count = f.get("message_count", 0)
                current_type = type_overrides.get(fname, f.get("folder_type", cat_key))

                col_check, col_name, col_count, col_type = st.columns([1, 4, 2, 3])

                with col_check:
                    is_selected = st.checkbox(
                        "扫描",
                        value=fname in selected_folders,
                        key=f"scan_{fname}",
                        label_visibility="collapsed",
                    )
                    if is_selected:
                        selected_folders.add(fname)
                    else:
                        selected_folders.discard(fname)

                with col_name:
                    st.markdown(f"**{fname}**")

                with col_count:
                    st.caption(f"{msg_count:,} 封")

                with col_type:
                    new_type = st.selectbox(
                        "类型",
                        options=type_options,
                        index=type_options.index(current_type) if current_type in type_options else len(type_options) - 1,
                        key=f"type_{fname}",
                        format_func=lambda x: type_display.get(x, x),
                        label_visibility="collapsed",
                    )
                    if new_type != f.get("folder_type", cat_key):
                        type_overrides[fname] = new_type

    # ── 快速操作 ──
    st.markdown("---")
    col_all, col_none, col_reset = st.columns(3)
    with col_all:
        st.button("✅ 全选", on_click=select_all_callback, args=(folders,), use_container_width=True)
    with col_none:
        st.button("⬜ 全不选", on_click=select_none_callback, args=(folders,), use_container_width=True)
    with col_reset:
        st.button("🔄 重置默认", on_click=reset_default_callback, args=(folders,), use_container_width=True)

    # ── 保存选择 ──
    st.markdown("---")
    if st.button("💾 保存文件夹配置", type="primary", use_container_width=True):
        st.session_state["folder_selections"] = selected_folders
        st.session_state["folder_type_overrides"] = type_overrides

        # 构建扫描文件夹列表
        scan_folders = []
        for f in folders:
            if f["name"] in selected_folders:
                ft = type_overrides.get(f["name"], f.get("folder_type", "other"))
                scan_folders.append({
                    "name": f["name"],
                    "raw_name": f.get("raw_name", f["name"]),
                    "flags": f.get("flags", []),
                    "folder_type": ft,
                    "message_count": f.get("message_count", 0),
                })
        st.session_state["scan_folders"] = scan_folders

        st.success(f"✅ 已保存！将扫描 {len(scan_folders)} 个文件夹。")

    # ── 当前选择摘要 ──
    if selected_folders:
        st.info(f"📋 当前选中 **{len(selected_folders)}** 个文件夹待扫描")
