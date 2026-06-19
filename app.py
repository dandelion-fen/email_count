"""
保研套磁统计工具 — Streamlit 主入口
"""
import streamlit as st
from src.database import init_db

# 页面配置
st.set_page_config(
    page_title="保研套磁统计工具",
    page_icon="📬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 初始化数据库
init_db()

# 自定义 CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;700&display=swap');

    .stApp {
        font-family: 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
    }

    /* 侧边栏美化 */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    }
    [data-testid="stSidebar"] .stMarkdown {
        color: #e0e0e0;
    }

    /* 统计卡片 */
    .stat-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.2rem;
        border-radius: 12px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        transition: transform 0.2s;
    }
    .stat-card:hover {
        transform: translateY(-2px);
    }
    .stat-card h3 {
        font-size: 2rem;
        margin: 0;
        font-weight: 700;
    }
    .stat-card p {
        font-size: 0.85rem;
        margin: 0.3rem 0 0;
        opacity: 0.9;
    }

    /* 状态标签 */
    .tag-positive {
        background-color: #d4edda;
        color: #155724;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.85rem;
    }
    .tag-negative {
        background-color: #f8d7da;
        color: #721c24;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.85rem;
    }
    .tag-uncertain {
        background-color: #fff3cd;
        color: #856404;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.85rem;
    }
    .tag-info {
        background-color: #d1ecf1;
        color: #0c5460;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.85rem;
    }

    /* 表格美化 */
    .dataframe {
        font-size: 0.85rem;
    }

    /* 隐藏 Streamlit 默认页脚 */
    footer {visibility: hidden;}

    /* 进度条 */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #667eea, #764ba2);
    }
</style>
""", unsafe_allow_html=True)

# 侧边栏导航
st.sidebar.markdown("## 📬 保研套磁统计工具")
st.sidebar.markdown("---")

pages = {
    "🏠 首页": "home",
    "🔗 邮箱连接": "connection",
    "📁 文件夹选择": "folders",
    "🔄 扫描与同步": "scan",
    "📊 导师总表": "teachers",
    "🔍 证据详情": "evidence",
    "✅ 人工复核": "review",
    "📈 汇总统计": "stats",
    "🤖 AI 分析设置": "ai",
    "💾 导出与数据管理": "export",
}

selected = st.sidebar.radio("导航", list(pages.keys()), label_visibility="collapsed")
current_page = pages[selected]

st.sidebar.markdown("---")
st.sidebar.markdown(
    "<small>⚠️ 只读访问邮箱 · 数据保存在本机</small>",
    unsafe_allow_html=True,
)

# 页面路由
if current_page == "home":
    from ui.page_home import render
    render()
elif current_page == "connection":
    from ui.page_connection import render
    render()
elif current_page == "folders":
    from ui.page_folders import render
    render()
elif current_page == "scan":
    from ui.page_scan import render
    render()
elif current_page == "teachers":
    from ui.page_teachers import render
    render()
elif current_page == "evidence":
    from ui.page_evidence import render
    render()
elif current_page == "review":
    from ui.page_review import render
    render()
elif current_page == "stats":
    from ui.page_stats import render
    render()
elif current_page == "ai":
    from ui.page_ai import render
    render()
elif current_page == "export":
    from ui.page_export import render
    render()
