@echo off
chcp 65001 >nul
set ROOT=%~dp0..
set PYTHON=%ROOT%\.venv\Scripts\python.exe

if not exist "%PYTHON%" (
  echo [错误] 未找到虚拟环境: %ROOT%\.venv
  echo 请先执行: py -3.12 -m venv %ROOT%\.venv
  echo 然后: %ROOT%\.venv\Scripts\pip install -r %ROOT%\backend\requirements.txt
  pause
  exit /b 1
)

if not exist "%ROOT%\.env" (
  echo [警告] 未找到配置文件: %ROOT%\.env
  echo 请执行: copy %ROOT%\.env.example %ROOT%\.env 并填入 API Key
  pause
  exit /b 1
)

echo 启动后端 http://localhost:8000 ...
start "video-backend" cmd /k "cd /d %ROOT%\backend && %PYTHON% main.py"

timeout /t 2 /nobreak >nul

echo 启动前端 http://localhost:5173 ...
start "video-frontend" cmd /k "cd /d %ROOT%\frontend && npm run dev"

echo.
echo 用户端:   http://localhost:5173
echo 管理后台: http://localhost:5173/admin
echo API 文档: http://localhost:8000/docs
echo 配置文件: %ROOT%\.env
echo.
pause
