# 🚀 霓虹星际守卫 (Neon Star Defender) v2.0 — 个人电脑自建服工程版

作者主页：[Stephen-Wang0301 (Stephen Wang)](https://github.com/Stephen-Wang0301)

## 一、v2.0 架构解决的核心痛点
1. **真正的一键集成启动（告别同时开 `.bat` + `server.py` + 手动敲隧道命令）**
   - **直接使用**：双击 `OneClick_Start_Windows.vbs`（无黑框直接弹出桌面可视化控制台），程序会自动启动本地 **SQLite 数据库**、**多线程安全服务端**，并自动下载/后台拉起 **Cloudflare 公网穿透隧道**，面板上直接显示 `https://xxxx.trycloudflare.com` 公网链接，点击按钮即可复制发给朋友！
   - **生成独立 `.exe`**：双击 `build_exe.bat` 即可在本机生成单文件 `dist/NeonStarServer.exe`；或者将代码推送到你的 GitHub 仓库，由内置的 **GitHub Actions** 在云端自动编译好 `NeonStarServer.exe` 供下载。
2. **前后端与数据库清晰解耦**
   - `frontend/`：纯前端游戏画面、音效与交互代码，后续修改游戏玩法或界面只需改动此文件夹。
   - `backend/`：独立配置 (`config.py`)、SQLite 数据库 (`database.py`)、6 层安全防火墙 (`security.py`) 与自动隧道管理 (`tunnel_manager.py`)。
   - `data/game_data.db`：自动生成的本地 SQLite 关系型数据库文件，所有玩家战绩与安全审计日志均安全存储在你自己的电脑硬盘上。

## 二、推送到 GitHub (`Stephen-Wang0301`) 与权限配置步骤
本项目文件夹已预置好 `.git` 版本库、`.gitignore`（自动屏蔽本地 `.db` 数据库与密钥）及 `.github/CODEOWNERS`。

1. 在 GitHub 上新建一个名为 `neon-star-defender` 的仓库（可设为 Public 或 Private）。
2. 在本文件夹打开终端运行：
   ```bash
   git remote add origin https://github.com/Stephen-Wang0301/neon-star-defender.git
   git push -u origin main
   ```
3. **推荐权限设置（防止他人乱改代码）**：
   - 进入 GitHub 仓库 **Settings → Branches → Add branch ruleset / protection rule**
   - 保护分支名填入 `main`
   - 勾选 **Require a pull request before merging** -> 勾选 **Require review from Code Owners**（已绑定 `@Stephen-Wang0301`）
   - 勾选 **Require status checks to pass**（绑定 `Security & Syntax Audit` 自动安全检查）
