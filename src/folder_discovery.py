"""
文件夹发现与分类模块
"""
from __future__ import annotations
from src.models import FolderType


# 文件夹名称到类型的映射规则
_FOLDER_RULES: list[tuple[list[str], FolderType]] = [
    (["inbox", "收件箱", "INBOX"], FolderType.INBOX),
    (["sent", "已发送", "Sent Messages", "已发邮件", "Sent Items", "已发送邮件"], FolderType.SENT),
    (["drafts", "草稿", "草稿箱", "Draft"], FolderType.DRAFTS),
    (["junk", "spam", "垃圾邮件", "垃圾箱", "Junk", "Spam"], FolderType.SPAM),
    (["trash", "deleted", "已删除", "废纸篓", "Trash", "Deleted Messages", "Deleted Items"], FolderType.TRASH),
    (["archive", "归档", "存档", "All Mail"], FolderType.ARCHIVE),
]

# IMAP 标志到类型的映射
_FLAG_RULES: dict[str, FolderType] = {
    "\\sent": FolderType.SENT,
    "\\drafts": FolderType.DRAFTS,
    "\\junk": FolderType.SPAM,
    "\\trash": FolderType.TRASH,
    "\\archive": FolderType.ARCHIVE,
    "\\all": FolderType.ARCHIVE,
    "\\inbox": FolderType.INBOX,
}


def classify_folder(name: str, flags: list[str] | None = None) -> FolderType:
    """根据名称和标志分类文件夹"""
    # 先检查 IMAP 标志
    if flags:
        for flag in flags:
            flag_lower = flag.lower()
            for flag_key, folder_type in _FLAG_RULES.items():
                if flag_key in flag_lower:
                    return folder_type

    # 再检查名称
    name_lower = name.lower().strip()
    for names, folder_type in _FOLDER_RULES:
        for n in names:
            if n.lower() == name_lower or n.lower() in name_lower:
                return folder_type

    return FolderType.OTHER


def get_default_scan_folders(folders: list[dict],
                             include_spam: bool = False,
                             include_archive: bool = False) -> list[dict]:
    """获取默认需要扫描的文件夹列表"""
    result = []
    for f in folders:
        ft = f.get("folder_type") or classify_folder(
            f.get("name", ""), f.get("flags", []))

        # 默认排除草稿和已删除
        if ft in (FolderType.DRAFTS, FolderType.TRASH):
            continue
        if ft == FolderType.SPAM and not include_spam:
            continue
        if ft == FolderType.ARCHIVE and not include_archive:
            continue

        result.append(f)

    return result


def is_sent_folder(name: str, flags: list[str] | None = None) -> bool:
    """判断是否为已发送文件夹"""
    return classify_folder(name, flags) == FolderType.SENT


def is_inbox_folder(name: str, flags: list[str] | None = None) -> bool:
    """判断是否为收件箱"""
    return classify_folder(name, flags) == FolderType.INBOX


def categorize_folders(folders: list[dict]) -> dict[str, list[dict]]:
    """将文件夹按类型分组"""
    categories: dict[str, list[dict]] = {
        "sent": [],
        "inbox": [],
        "spam": [],
        "archive": [],
        "drafts": [],
        "trash": [],
        "other": [],
    }
    for f in folders:
        ft = classify_folder(f.get("name", ""), f.get("flags", []))
        key = ft.value if ft.value in categories else "other"
        f["folder_type"] = ft.value
        categories[key].append(f)

    return categories
