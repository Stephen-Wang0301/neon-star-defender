@echo off
chcp 65001 >nul
echo ============================================================
echo 正在将《霓虹星际守卫 v2.0》打包为独立单文件 NeonStarServer.exe ...
echo ============================================================
python -m pip install --upgrade pyinstaller
python -m PyInstaller --noconsole --onefile --name NeonStarServer --add-data "frontend;frontend" app_launcher.py
echo.
echo ✅ 打包完成！请前往 dist\NeonStarServer.exe 双击运行！
pause
