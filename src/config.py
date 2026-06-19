"""
配置管理模块
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 数据库
DB_PATH = os.getenv("DB_PATH", str(PROJECT_ROOT / "mail_tracker.db"))

# 邮箱默认配置
DEFAULT_IMAP_SERVER = "imap.163.com"
DEFAULT_IMAP_PORT = 993
DEFAULT_USE_SSL = True

# OpenAI 配置
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
OPENAI_MODEL_ENV = "OPENAI_MODEL"
DEFAULT_OPENAI_MODEL = "gpt-4o"

# 日志
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 导出
EXPORT_DIR = PROJECT_ROOT / "exports"
EXPORT_DIR.mkdir(exist_ok=True)

# 套磁关键词（默认）
DEFAULT_SUBJECT_KEYWORDS = [
    "硕士保研自荐", "保研自荐", "夏令营", "预推免",
    "研究生自荐", "推免申请", "杜子坤", "湖北工业大学",
    "微电子科学与工程", "附简历",
]

DEFAULT_BODY_KEYWORDS = [
    "保研", "夏令营", "预推免", "研究生", "招生",
    "名额", "课题组", "推荐免试", "推免", "自荐",
]

# 积极回复关键词
POSITIVE_KEYWORDS = [
    "欢迎报名", "欢迎申请", "可以报名", "有名额", "可以接收",
    "欢迎加入", "保持联系", "加微信", "安排面试", "线上交流",
    "发一下材料", "报名后联系", "参加夏令营", "参加预推免",
]

# 不确定关键词
UNCERTAIN_KEYWORDS = [
    "名额未定", "还不确定", "等政策", "等通知",
    "后续联系", "到时候再说", "通过考核", "择优录取",
]

# 消极关键词
NEGATIVE_KEYWORDS = [
    "名额已满", "没有名额", "不招生", "方向不符",
    "不太匹配", "建议联系其他老师", "无法接收", "已招满",
]

# 退信和自动回复特征
BOUNCE_SENDERS = [
    "mailer-daemon", "postmaster", "mail delivery subsystem",
]

BOUNCE_SUBJECTS = [
    "delivery status notification", "undelivered mail",
    "投递失败", "退信", "邮箱不存在", "mail delivery failed",
    "returned to sender",
]

AUTO_REPLY_HEADERS = {
    "Auto-Submitted": ["auto-replied", "auto-generated", "auto-notified"],
    "Precedence": ["auto_reply", "bulk", "junk"],
    "X-Autoreply": [],
    "X-Autorespond": [],
}

AUTO_REPLY_SUBJECTS = [
    "自动回复", "自动答复", "out of office", "automatic reply",
    "放假通知", "假期自动回复",
]

# 学术邮箱域名特征
ACADEMIC_DOMAINS = [
    ".edu.cn", ".edu", ".ac.cn", ".ac.",
    ".cas.cn", ".pku.edu.cn", ".tsinghua.edu.cn",
]

# 连接超时
IMAP_TIMEOUT = 30  # 秒
IMAP_RETRY_COUNT = 3
IMAP_RETRY_DELAY = 5  # 秒

# 隐私过滤正则
PHONE_PATTERN = r'1[3-9]\d{9}'
ID_CARD_PATTERN = r'\d{17}[\dXx]'
ADDRESS_PATTERN = r'(?:省|市|区|县|路|街|号|栋|单元|室).{5,30}'
