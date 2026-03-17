@echo off
REM Medical Copilot 智能启动脚本
REM 自动检测端口占用并启用其他端口

echo ====================================
echo Medical Copilot 智能启动
echo ====================================
echo.

REM 检查虚拟环境
if not exist "venv\" (
    echo [1/3] 创建虚拟环境...
    python -m venv venv
    echo ✅ 虚拟环境创建完成
) else (
    echo ✅ 虚拟环境已存在
)

REM 激活虚拟环境
echo.
echo [2/3] 激活虚拟环境...
call venv\Scripts\activate.bat

REM 安装依赖
echo.
echo [3/3] 安装依赖...
pip install -q -r requirements.txt 2>nul
if errorlevel 1 (
    echo ⚠️  依赖安装可能有问题，尝试继续...
)
echo ✅ 依赖安装完成

echo.
echo ====================================
echo 检查端口并启动服务...
echo ====================================
echo.

REM 查找可用端口（后端）
set BACKEND_PORT=8000
call :find_free_port BACKEND_PORT
echo 后端服务端口: %BACKEND_PORT%

REM 查找可用端口（前端）
set FRONTEND_PORT=8501
call :find_free_port FRONTEND_PORT
echo 前端服务端口: %FRONTEND_PORT%

echo.
echo ====================================
echo 启动服务...
echo ====================================
echo.

REM 在新窗口启动后端服务
echo [1/2] 启动后端服务 (FastAPI)...
start "Medical Copilot Backend" cmd /k "cd /d "%~dp0" && venv\Scripts\activate && uvicorn src.main:app --reload --host 0.0.0.0 --port %BACKEND_PORT%"

REM 等待后端启动
echo 等待后端服务初始化...
timeout /t 5 /nobreak >nul

REM 更新前端配置中的API地址
echo [2/2] 启动前端服务 (Streamlit)...
set "BACKEND_PORT=%BACKEND_PORT%"
streamlit run frontend/app.py --server.port %FRONTEND_PORT%

echo.
echo ====================================
echo ✅ 所有服务已启动！
echo ====================================
echo 后端服务: http://localhost:%BACKEND_PORT%
echo 前端界面: http://localhost:%FRONTEND_PORT%
echo.
pause

exit /b 0

REM ====================================
REM 子程序：查找可用端口
REM ====================================
:find_free_port
setlocal EnableDelayedExpansion
set "port=!%~1!"
:check_port
powershell -Command "try { $conn = New-Object System.Net.Sockets.TcpClient; $conn.Connect('localhost', !port!); $conn.Close(); exit 0 } catch { exit 1 }" >nul 2>&1
if %errorlevel% equ 0 (
    echo   端口 !port! 被占用，尝试下一个端口...
    set /a port+=1
    goto check_port
)
endlocal & set "%~1=%port%"
exit /b 0