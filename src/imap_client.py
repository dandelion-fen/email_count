"""
IMAP 只读连接模块

重要：所有操作必须使用只读模式
不执行 STORE/COPY/MOVE/DELETE/EXPUNGE/APPEND/SMTP
"""
from __future__ import annotations

import imaplib
import re
import socket
import time
from typing import Optional

from src.config import (
    DEFAULT_IMAP_SERVER, DEFAULT_IMAP_PORT, DEFAULT_USE_SSL,
    IMAP_TIMEOUT, IMAP_RETRY_COUNT, IMAP_RETRY_DELAY,
)
from src.utils import setup_logger

logger = setup_logger("imap_client")

# 禁止的 IMAP 命令 — 确保只读安全
_FORBIDDEN_COMMANDS = {"STORE", "COPY", "MOVE", "DELETE", "EXPUNGE", "APPEND"}


class IMAPReadOnlyClient:
    """只读 IMAP 客户端"""

    def __init__(self, server: str = DEFAULT_IMAP_SERVER,
                 port: int = DEFAULT_IMAP_PORT,
                 use_ssl: bool = DEFAULT_USE_SSL,
                 timeout: int = IMAP_TIMEOUT):
        self.server = server
        self.port = port
        self.use_ssl = use_ssl
        self.timeout = timeout
        self._conn: Optional[imaplib.IMAP4 | imaplib.IMAP4_SSL] = None

    def connect(self, email_addr: str, auth_code: str) -> dict:
        """连接并登录邮箱，返回连接信息"""
        try:
            socket.setdefaulttimeout(self.timeout)
            if self.use_ssl:
                self._conn = imaplib.IMAP4_SSL(self.server, self.port)
            else:
                self._conn = imaplib.IMAP4(self.server, self.port)

            # 登录
            self._conn.login(email_addr, auth_code)

            # 发送 ID 命令以绕过网易 IMAP 限制 (Unsafe Login)
            try:
                self._conn.xatom("ID", '("name" "ietf" "version" "2.0" "vendor" "generic")')
            except Exception as e:
                logger.warning(f"Failed to send IMAP ID command: {e}")

            # 获取能力信息
            caps = self._conn.capabilities
            cap_list = [c.decode() if isinstance(c, bytes) else str(c) for c in caps] if caps else []

            return {
                "success": True,
                "message": "连接成功",
                "capabilities": cap_list,
                "server": self.server,
                "port": self.port,
                "ssl": self.use_ssl,
            }

        except imaplib.IMAP4.error as e:
            error_msg = str(e)
            if "AUTHENTICATIONFAILED" in error_msg.upper() or "LOGIN" in error_msg.upper():
                return {"success": False, "message": "认证失败：请检查邮箱地址和客户端授权码是否正确。注意需要使用客户端授权码而非登录密码。"}
            return {"success": False, "message": f"IMAP 错误: {self._safe_error(error_msg)}"}
        except socket.timeout:
            return {"success": False, "message": f"连接超时：无法在 {self.timeout} 秒内连接到 {self.server}:{self.port}"}
        except socket.gaierror:
            return {"success": False, "message": f"无法解析服务器地址: {self.server}，请检查服务器配置"}
        except ConnectionRefusedError:
            return {"success": False, "message": f"连接被拒绝: {self.server}:{self.port}，请确认IMAP服务已开启"}
        except Exception as e:
            return {"success": False, "message": f"连接失败: {self._safe_error(str(e))}"}

    def disconnect(self) -> None:
        """断开连接"""
        if self._conn:
            try:
                self._conn.logout()
            except Exception:
                pass
            self._conn = None

    def list_folders(self) -> list[dict]:
        """列出所有文件夹"""
        self._ensure_connected()
        folders = []
        status, data = self._conn.list()
        if status != "OK":
            return folders

        for item in data:
            if item is None:
                continue
            folder_info = self._parse_folder_line(item)
            if folder_info:
                folders.append(folder_info)

        return folders

    def get_folder_status(self, folder_name: str) -> dict:
        """获取文件夹状态（邮件数量、UIDVALIDITY等）"""
        self._ensure_connected()
        try:
            encoded_name = self._encode_folder(folder_name)
            status, data = self._conn.select(encoded_name, readonly=True)
            if status != "OK":
                logger.error(f"Select folder failed: {folder_name} (encoded: {encoded_name}), status={status}, response={data}")
                return {"error": f"无法打开文件夹: {folder_name}, status={status}, response={data}"}

            message_count = int(data[0]) if data[0] else 0

            # 获取 UIDVALIDITY 和 UIDNEXT
            uidvalidity = 0
            uidnext = 0
            try:
                status2, data2 = self._conn.status(
                    self._encode_folder(folder_name),
                    "(UIDVALIDITY UIDNEXT MESSAGES)"
                )
                if status2 == "OK" and data2:
                    resp = data2[0]
                    if isinstance(resp, bytes):
                        resp = resp.decode("utf-8", errors="replace")
                    m = re.search(r'UIDVALIDITY\s+(\d+)', resp)
                    if m:
                        uidvalidity = int(m.group(1))
                    m = re.search(r'UIDNEXT\s+(\d+)', resp)
                    if m:
                        uidnext = int(m.group(1))
            except Exception:
                pass

            return {
                "name": folder_name,
                "message_count": message_count,
                "uidvalidity": uidvalidity,
                "uidnext": uidnext,
                "readonly": True,
            }
        except Exception as e:
            return {"error": self._safe_error(str(e))}

    def fetch_uids(self, folder_name: str, since_uid: int = 0,
                   date_since: str = "", date_before: str = "") -> list[int]:
        """获取文件夹中的邮件 UID 列表"""
        self._ensure_connected()
        status, _ = self._conn.select(self._encode_folder(folder_name), readonly=True)
        if status != "OK":
            return []

        # 构建搜索条件
        criteria = []
        if since_uid > 0:
            criteria.append(f"UID {since_uid}:*")
        if date_since:
            criteria.append(f'SINCE "{date_since}"')
        if date_before:
            criteria.append(f'BEFORE "{date_before}"')

        search_str = " ".join(criteria) if criteria else "ALL"

        try:
            if since_uid > 0:
                status, data = self._conn.uid("SEARCH", None, f"UID {since_uid}:*")
            else:
                status, data = self._conn.uid("SEARCH", None, search_str)

            if status != "OK" or not data or not data[0]:
                return []

            uid_str = data[0]
            if isinstance(uid_str, bytes):
                uid_str = uid_str.decode()
            return [int(u) for u in uid_str.split() if u.strip()]
        except Exception as e:
            logger.warning(f"搜索邮件失败: {self._safe_error(str(e))}")
            return []

    def fetch_message(self, folder_name: str, uid: int) -> Optional[bytes]:
        """获取单封邮件的原始内容（只读）"""
        self._ensure_connected()

        for attempt in range(IMAP_RETRY_COUNT):
            try:
                status, _ = self._conn.select(
                    self._encode_folder(folder_name), readonly=True)
                if status != "OK":
                    return None

                status, data = self._conn.uid("FETCH", str(uid), "(RFC822)")
                if status != "OK" or not data or data[0] is None:
                    return None

                if isinstance(data[0], tuple) and len(data[0]) >= 2:
                    return data[0][1]
                return None

            except (imaplib.IMAP4.abort, socket.timeout, ConnectionResetError) as e:
                logger.warning(f"获取邮件重试 {attempt+1}/{IMAP_RETRY_COUNT}: UID={uid}")
                if attempt < IMAP_RETRY_COUNT - 1:
                    time.sleep(IMAP_RETRY_DELAY)
                    try:
                        self._conn.noop()
                    except Exception:
                        pass
                else:
                    return None
            except Exception as e:
                logger.error(f"获取邮件失败: UID={uid}, 错误={self._safe_error(str(e))}")
                return None

        return None

    def _ensure_connected(self) -> None:
        if self._conn is None:
            raise RuntimeError("未连接到邮箱服务器，请先调用 connect()")

    def _encode_folder(self, folder_name: str) -> str:
        """编码文件夹名称（处理中文）"""
        if not folder_name:
            return ""
        if folder_name.upper() == "INBOX":
            return "INBOX"
        try:
            encoded = self._encode_modified_utf7(folder_name)
            if not (encoded.startswith('"') and encoded.endswith('"')):
                return f'"{encoded}"'
            return encoded
        except Exception:
            return folder_name

    @staticmethod
    def _encode_modified_utf7(text: str) -> str:
        """将 string 编码为 IMAP modified UTF-7"""
        import base64
        res = []
        in_utf16 = []
        
        def flush_utf16():
            if not in_utf16:
                return
            utf16_bytes = "".join(in_utf16).encode("utf-16-be")
            b64_str = base64.b64encode(utf16_bytes).decode("ascii").replace("/", ",").rstrip("=")
            res.append("&" + b64_str + "-")
            in_utf16.clear()

        for c in text:
            if 0x20 <= ord(c) <= 0x7E:
                if c == '&':
                    flush_utf16()
                    res.append('&-')
                else:
                    flush_utf16()
                    res.append(c)
            else:
                in_utf16.append(c)
                
        flush_utf16()
        return "".join(res)

    def _parse_folder_line(self, line: bytes | str) -> Optional[dict]:
        """解析 IMAP LIST 返回的文件夹行"""
        if isinstance(line, bytes):
            line = line.decode("utf-8", errors="replace")

        # 格式: (\Flags) "delimiter" "name"
        match = re.match(r'\(([^)]*)\)\s+"([^"]*)"\s+"?([^"]*)"?', line)
        if not match:
            match = re.match(r'\(([^)]*)\)\s+(\S+)\s+(.+)', line)

        if not match:
            return None

        flags_str = match.group(1)
        delimiter = match.group(2)
        name = match.group(3).strip().strip('"')

        # 尝试解码 modified UTF-7
        decoded_name = self._decode_modified_utf7(name)

        flags = [f.strip().lower() for f in flags_str.split() if f.strip()]

        return {
            "name": decoded_name,
            "raw_name": name,
            "flags": flags,
            "delimiter": delimiter,
        }

    @staticmethod
    def _decode_modified_utf7(text: str) -> str:
        """解码 IMAP modified UTF-7 编码的文件夹名"""
        if "&" not in text:
            return text
        try:
            # IMAP modified UTF-7: & -> +, , -> /
            result = []
            i = 0
            while i < len(text):
                if text[i] == '&':
                    j = text.index('-', i + 1)
                    if j == i + 1:
                        result.append('&')
                    else:
                        encoded = text[i+1:j]
                        encoded = encoded.replace(',', '/')
                        encoded = '+' + encoded + '-'
                        result.append(encoded.encode('ascii').decode('utf-7'))
                    i = j + 1
                else:
                    result.append(text[i])
                    i += 1
            return ''.join(result)
        except Exception:
            return text

    @staticmethod
    def _safe_error(msg: str) -> str:
        """过滤错误信息中的敏感内容"""
        msg = re.sub(r'(password|passwd|auth_code|token)\s*[:=]\s*\S+',
                     r'\1=***', msg, flags=re.IGNORECASE)
        return msg

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.disconnect()
