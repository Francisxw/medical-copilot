@echo off
REM Medical Copilot 启动脚本 - 向量检索版本

echo ====================================
echo Medical Copilot 启动向量化版本
echo ====================================
echo.

REM 检查虚拟环境
if not exist "venv\" (
    echo [1/6] 创建虚拟环境...
    python -m venv venv
    echo ✅ 虚拟环境创建完成
) else (
    echo ✅ 虚拟环境已存在
)

REM 激活虚拟环境
echo.
echo [2/6] 激活虚拟环境...
call venv\Scripts\activate.bat

REM 安装依赖
echo.
echo [3/6] 安装依赖...
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
    echo ❗ 请编辑 .env 文件并填入 API 密钥
    echo.
    echo 需要配置的 API:
    echo   1. DeepSeek API (用于LLM): https://platform.deepseek.com/
    echo   2. OpenRouter API (用于Embedding): https://openrouter.ai/
    echo.
    notepad .env
    echo.
    echo 编辑完成后按任意键继续...
    pause >nul
)

REM 准备数据
echo.
echo [4/6] 准备示例数据...
python scripts/prepare_data.py
if errorlevel 1 (
    echo ❌ 数据准备失败
    pause
    exit /b 1
)

REM 构建向量索引
echo.
echo [5/6] 构建向量索引...
echo 注意: 首次构建需要调用 Embedding API
echo 预计耗时: 1-2 分钟
echo.
python scripts/build_vector_index.py
if errorlevel 1 (
    echo ❌ 索引构建失败
    echo.
    echo 可能的原因:
    echo   1. OpenRouter API 密钥未配置或错误
    echo   2. 网络无法访问 openrouter.ai
    echo   3. OpenRouter 账户余额不足
    echo.
    echo 解决方案:
    echo   1. 检查 .env 文件中的 EMBEDDING_BASE_URL 和 OPENAI_API_KEY
    echo   2. 访问 https://openrouter.ai/ 充值
    pause
    exit /b 1
)

REM 验证配置
echo.
echo [6/6] 配置验证完成！
echo ✅ 向量数据库已构建
echo.

echo ====================================
echo ✅ 所有设置已完成！
echo ====================================
echo.
echo 选择启动模式:
echo 1. 启动后端服务 (FastAPI)
echo 2. 启动前端界面 (Streamlit)
echo 3. 同时启动后端和前端
echo 4. 重新构建向量索引
echo 5. 退出
echo.
set /p choice="请选择 (1-5): "

if "%choice%"=="1" (
    echo.
    echo 启动 FastAPI 后端服务...
    echo 使用向量检索模式
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
) else if "%choice%"=="4" (
    echo.
    echo 重新构建向量索引...
    python scripts/build_vector_index.py
    pause
) else (
    echo 退出
    exit /b 0
)
