"""
邮件同步模块 — 使用 UID 增量同步
"""
from __future__ import annotations

import email.utils
from datetime import datetime
from typing import Callable, Optional

from src.imap_client import IMAPReadOnlyClient
from src.mime_parser import parse_mime_message
from src.folder_discovery import classify_folder
from src.models import ScanProgress, FolderType
from src import database as db
from src.utils import setup_logger

logger = setup_logger("mail_sync")


def sync_folder(client: IMAPReadOnlyClient,
                account_id: int,
                folder_info: dict,
                my_email: str,
                progress_callback: Optional[Callable[[ScanProgress], None]] = None,
                cancel_check: Optional[Callable[[], bool]] = None,
                scan_run_id: int = 0,
                db_path: str | None = None) -> dict:
    """同步单个文件夹的邮件"""
    folder_name = folder_info["name"]
    folder_type = folder_info.get("folder_type", "other")

    # 获取或创建文件夹记录
    folder_id = db.upsert_folder(
        account_id, folder_name,
        raw_name=folder_info.get("raw_name", ""),
        folder_type=folder_type,
        db_path=db_path,
    )

    # 获取文件夹状态
    status = client.get_folder_status(folder_name)
    if "error" in status:
        logger.warning(f"文件夹 {folder_name} 状态获取失败: {status['error']}")
        if scan_run_id:
            db.add_scan_error(scan_run_id, folder_name, 0,
                              "folder_status", status["error"], db_path)
        return {"folder": folder_name, "synced": 0, "errors": 1}

    current_uidvalidity = status.get("uidvalidity", 0)

    # 获取上次同步状态
    conn = db.get_connection(db_path)
    sync_row = conn.execute(
        "SELECT * FROM sync_state WHERE account_id=? AND folder_id=?",
        (account_id, folder_id)).fetchone()

    last_uid = 0
    if sync_row:
        saved_uidvalidity = sync_row["uidvalidity"]
        if saved_uidvalidity and current_uidvalidity and saved_uidvalidity != current_uidvalidity:
            logger.warning(f"文件夹 {folder_name} 的 UIDVALIDITY 已变化，需要重建索引")
            # 清除该文件夹的旧邮件
            conn.execute("DELETE FROM messages WHERE folder_id=?", (folder_id,))
            conn.commit()
        else:
            last_uid = sync_row["last_sync_uid"] or 0

    # 获取新邮件 UID 列表
    uids = client.fetch_uids(folder_name, since_uid=last_uid + 1 if last_uid else 0)
    # 过滤已同步的
    uids = [u for u in uids if u > last_uid]

    synced = 0
    errors = 0
    total = len(uids)

    for i, uid in enumerate(uids):
        # 检查取消
        if cancel_check and cancel_check():
            logger.info(f"用户取消了 {folder_name} 的同步")
            break

        # 检查是否已存在
        if db.message_exists(account_id, folder_id, uid, db_path):
            continue

        # 进度回调
        if progress_callback:
            progress = ScanProgress(
                current_folder=folder_name,
                current_message=i + 1,
                total_messages=total,
                errors=errors,
                status="syncing",
            )
            progress_callback(progress)

        # 获取邮件
        try:
            raw = client.fetch_message(folder_name, uid)
            if raw is None:
                errors += 1
                if scan_run_id:
                    db.add_scan_error(scan_run_id, folder_name, uid,
                                      "fetch_failed", "获取邮件内容失败", db_path)
                continue

            # 解析邮件
            parsed = parse_mime_message(raw, folder=folder_name,
                                        uid=uid, my_email=my_email)

            # 保存到数据库
            msg_data = {
                "account_id": account_id,
                "folder_id": folder_id,
                "uid": uid,
                "message_id": parsed.message_id,
                "in_reply_to": parsed.in_reply_to,
                "references_str": parsed.references_str,
                "date": parsed.date.isoformat() if parsed.date else parsed.date_str,
                "subject": parsed.subject,
                "subject_normalized": parsed.subject_normalized,
                "from_email": parsed.from_addr.email,
                "from_name": parsed.from_addr.name,
                "to_addrs": "; ".join(email.utils.formataddr((a.name, a.email)) for a in parsed.to_addrs),
                "cc_addrs": "; ".join(email.utils.formataddr((a.name, a.email)) for a in parsed.cc_addrs),
                "reply_to": parsed.reply_to_addr.email if parsed.reply_to_addr else "",
                "body_text": parsed.body_text,
                "body_html_text": parsed.body_html_text,
                "has_attachments": int(parsed.has_attachments),
                "attachment_names": "; ".join(parsed.attachment_names),
                "attachment_types": "; ".join(parsed.attachment_types),
                "is_sent_by_me": int(parsed.is_sent_by_me),
                "is_auto_reply": int(parsed.is_auto_reply),
                "is_bounce": int(parsed.is_bounce),
                "is_system_notification": int(parsed.is_system_notification),
                "content_hash": parsed.content_hash,
            }

            result_id = db.insert_message(msg_data, db_path)
            if result_id > 0:
                synced += 1
            last_uid = max(last_uid, uid)

        except Exception as e:
            errors += 1
            logger.error(f"解析邮件失败: 文件夹={folder_name}, UID={uid}, 错误={type(e).__name__}")
            if scan_run_id:
                db.add_scan_error(scan_run_id, folder_name, uid,
                                  type(e).__name__, str(e)[:200], db_path)

    # 更新同步状态
    if last_uid > 0:
        conn = db.get_connection(db_path)
        conn.execute(
            """INSERT INTO sync_state (account_id,folder_id,uidvalidity,uidnext,last_sync_uid,last_sync_time)
               VALUES (?,?,?,?,?,datetime('now'))
               ON CONFLICT(account_id,folder_id) DO UPDATE SET
               uidvalidity=?,uidnext=?,last_sync_uid=?,last_sync_time=datetime('now')""",
            (account_id, folder_id, current_uidvalidity,
             status.get("uidnext", 0), last_uid,
             current_uidvalidity, status.get("uidnext", 0), last_uid))
        conn.commit()

        db.update_folder_sync(folder_id, current_uidvalidity,
                              status.get("uidnext", 0), last_uid,
                              status.get("message_count", 0), db_path)

    return {"folder": folder_name, "synced": synced, "errors": errors, "total": total}


def full_sync(client: IMAPReadOnlyClient,
              account_id: int,
              folders: list[dict],
              my_email: str,
              progress_callback: Optional[Callable] = None,
              cancel_check: Optional[Callable] = None,
              db_path: str | None = None) -> dict:
    """完整同步多个文件夹"""
    scan_run_id = db.start_scan_run(account_id, db_path)

    total_synced = 0
    total_errors = 0
    results = []

    for idx, folder in enumerate(folders):
        if cancel_check and cancel_check():
            break

        if progress_callback:
            p = ScanProgress(
                current_folder=folder["name"],
                total_folders=len(folders),
                current_folder_index=idx + 1,
                status="syncing",
            )
            progress_callback(p)

        result = sync_folder(
            client, account_id, folder, my_email,
            progress_callback=progress_callback,
            cancel_check=cancel_check,
            scan_run_id=scan_run_id,
            db_path=db_path,
        )
        results.append(result)
        total_synced += result.get("synced", 0)
        total_errors += result.get("errors", 0)

    status = "cancelled" if (cancel_check and cancel_check()) else "completed"
    db.finish_scan_run(scan_run_id, len(folders), total_synced,
                       total_errors, status, db_path)

    return {
        "scan_run_id": scan_run_id,
        "folders": len(folders),
        "synced": total_synced,
        "errors": total_errors,
        "status": status,
        "details": results,
    }
