# setup_windows.ps1 — 网易邮箱保研套磁统计工具 Windows 安装脚本
# 使用方法: 右键 -> 使用 PowerShell 运行

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  保研套磁统计工具 - Windows 安装脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查 Python 版本
Write-Host "[1/4] 检查 Python 环境..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "  发现 $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "  错误: 未找到 Python，请先安装 Python 3.11 或以上版本" -ForegroundColor Red
    Write-Host "  下载地址: https://www.python.org/downloads/" -ForegroundColor Yellow
    Read-Host "按回车键退出"
    exit 1
}

# 创建虚拟环境
Write-Host "[2/4] 创建虚拟环境..." -ForegroundColor Yellow
if (Test-Path ".venv") {
    Write-Host "  虚拟环境已存在，跳过创建" -ForegroundColor Green
} else {
    python -m venv .venv
    Write-Host "  虚拟环境创建成功" -ForegroundColor Green
}

# 激活虚拟环境
Write-Host "[3/4] 激活虚拟环境..." -ForegroundColor Yellow
& ".venv\Scripts\Activate.ps1"
Write-Host "  虚拟环境已激活" -ForegroundColor Green

# 安装依赖
Write-Host "[4/4] 安装项目依赖..." -ForegroundColor Yellow
pip install -r requirements.txt --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "  依赖安装成功" -ForegroundColor Green
} else {
    Write-Host "  依赖安装失败，请检查网络连接" -ForegroundColor Red
    Read-Host "按回车键退出"
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  安装完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "启动方式:" -ForegroundColor Yellow
Write-Host "  方式1: 运行 run_windows.ps1" -ForegroundColor White
Write-Host "  方式2: 手动执行以下命令:" -ForegroundColor White
Write-Host "    .venv\Scripts\Activate.ps1" -ForegroundColor Gray
Write-Host "    streamlit run app.py" -ForegroundColor Gray
Write-Host ""
Read-Host "按回车键退出"
