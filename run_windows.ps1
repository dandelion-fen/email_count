# run_windows.ps1 — 网易邮箱保研套磁统计工具 Windows 启动脚本
# 使用方法: 右键 -> 使用 PowerShell 运行

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  保研套磁统计工具 - 启动中..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查虚拟环境
if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Host "错误: 未找到虚拟环境，请先运行 setup_windows.ps1" -ForegroundColor Red
    Read-Host "按回车键退出"
    exit 1
}

# 激活虚拟环境
Write-Host "激活虚拟环境..." -ForegroundColor Yellow
& ".venv\Scripts\Activate.ps1"

# 加载 .env（如果存在）
if (Test-Path ".env") {
    Write-Host "加载环境变量配置..." -ForegroundColor Yellow
}

# 启动 Streamlit
Write-Host "启动应用..." -ForegroundColor Yellow
Write-Host "浏览器将自动打开，如未打开请访问 http://localhost:8501" -ForegroundColor Green
Write-Host ""

try {
    streamlit run app.py --server.headless false
} catch {
    Write-Host ""
    Write-Host "应用启动失败: $_" -ForegroundColor Red
    Write-Host "请确认已运行 setup_windows.ps1 安装依赖" -ForegroundColor Yellow
}

Read-Host "按回车键退出"
