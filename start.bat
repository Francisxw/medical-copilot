@echo off
REM Medical Copilot 快速启动脚本 - Windows (DeepSeek配置)

echo ====================================
echo Medical Copilot 快速启动
echo ====================================
echo.

REM 检查虚拟环境
if not exist "venv\" (
    echo [1/5] 创建虚拟环境...
    python -m venv venv
    echo ✅ 虚拟环境创建完成
) else (
    echo ✅ 虚拟环境已存在
)

REM 激活虚拟环境
echo.
echo [2/5] 激活虚拟环境...
call venv\Scripts\activate.bat

REM 安装依赖
echo.
echo [3/5] 安装依赖...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo ❌ 依赖安装失败
    pause
    exit /b 1
)
echo ✅ 依赖安装完成

REM 检查环境变量
if not exist ".env" (
    echo.
    echo ⚠️  警告: .env 文件不存在
    echo 正在创建 .env 文件...
    copy .env.example .env >nul
    echo.
    echo ❗ 请编辑 .env 文件并填入你的 DeepSeek API 密钥
    echo.
    echo 获取API密钥: https://platform.deepseek.com/
    echo.
    notepad .env
    echo.
    echo 编辑完成后按任意键继续...
    pause >nul
)

REM 准备数据
echo.
echo [4/5] 准备示例数据...
python scripts/prepare_data.py
if errorlevel 1 (
    echo ❌ 数据准备失败
    pause
    exit /b 1
)

REM 验证配置
echo.
echo [5/5] 验证配置...
echo 注意: 本项目使用关键词匹配检索，无需向量索引
echo 数据已准备就绪！

echo.
echo ====================================
echo ✅ 所有设置已完成！
echo ====================================
echo.
echo 选择启动模式:
echo 1. 启动后端服务 (FastAPI)
echo 2. 启动前端界面 (Streamlit)
echo 3. 同时启动后端和前端
echo 4. 退出
echo.
set /p choice="请选择 (1-4): "

if "%choice%"=="1" (
    echo.
    echo 启动 FastAPI 后端服务...
    echo 访问 http://localhost:8000/docs 查看 API 文档
    uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
) else if "%choice%"=="2" (
    echo.
    echo 启动 Streamlit 前端界面...
    echo 访问 http://localhost:8501
    streamlit run frontend/app.py
) else if "%choice%"=="3" (
    echo.
    echo 同时启动后端和前端...
    echo.
    echo 在新窗口启动后端服务...
    start "Medical Copilot Backend" cmd /k "venv\Scripts\activate && uvicorn src.main:app --reload --host 0.0.0.0 --port 8000"
    timeout /t 3 >nul
    echo 启动前端界面...
    streamlit run frontend/app.py
) else (
    echo 退出
    exit /b 0
)
