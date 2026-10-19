#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
《霓虹星际守卫 v2.0》一键集成桌面服务端控制台 (GUI App Launcher)
- 双击即可打开可视化窗口，无需手动开启多个命令行或配置隧道
- 自动启动本地 SQLite 数据库 + 多线程安全 Web 服务 + Cloudflare 公网穿透隧道
- 支持通过 `build_exe.bat` 或 GitHub Actions 一键编译为独立 `NeonStarServer.exe`
"""
import sys
import threading
import time
import webbrowser
from backend.config import DB_PATH, SERVER_PORT
from backend.database import get_recent_security_logs, get_stats
from backend.server import GameServerController, get_lan_ip
from backend.tunnel_manager import TunnelManager

def run_cli_mode(server: GameServerController, tunnel: TunnelManager):
    lan_ip = get_lan_ip()
    print("=" * 66)
    print("🚀 霓虹星际守卫 v2.0 — 集成安全服务器与公网隧道已启动")
    print("=" * 66)
    print(f"👉 本机访问地址:     http://127.0.0.1:{SERVER_PORT}")
    print(f"👉 局域网访问地址:   http://{lan_ip}:{SERVER_PORT}")
    print(f"👉 SQLite 数据库:    {DB_PATH}")
    print("正在自动拉起 Cloudflare 公网隧道，请稍候...")
    tunnel.start_async()
    try:
        while True:
            time.sleep(2)
    except KeyboardInterrupt:
        print("\n正在关闭服务与公网隧道...")
        tunnel.stop()
        server.stop()

def run_gui_mode():
    try:
        import tkinter as tk
        from tkinter import messagebox
    except Exception:
        # 若当前环境无图形界面则自动回退到集成命令行模式
        server = GameServerController(port=SERVER_PORT)
        server.start()
        tunnel = TunnelManager(port=SERVER_PORT, on_status_change=lambda s, u: print(f"[隧道状态] {s} {u or ''}"))
        run_cli_mode(server, tunnel)
        return

    server = GameServerController(port=SERVER_PORT)
    server.start()
    lan_ip = get_lan_ip()

    root = tk.Tk()
    root.title("霓虹星际守卫 v2.0 — 个人电脑服务器一键控制台")
    root.geometry("680x500")
    root.configure(bg="#090d16")
    root.resizable(False, False)

    # Header
    header = tk.Frame(root, bg="#0f172a", padx=20, pady=14)
    header.pack(fill="x")
    tk.Label(
        header,
        text="🚀 霓虹星际守卫 · 个人服务器一键控制中心 (v2.0)",
        font=("Microsoft YaHei UI", 13, "bold"),
        fg="#38bdf8",
        bg="#0f172a",
    ).pack(anchor="w")
    tk.Label(
        header,
        text="本地 SQLite 数据库 + 6 层网络安全防御 + 全自动公网 HTTPS 隧道集成",
        font=("Microsoft YaHei UI", 9),
        fg="#94a3b8",
        bg="#0f172a",
    ).pack(anchor="w", pady=(2, 0))

    # Main Status Frame
    body = tk.Frame(root, bg="#090d16", padx=20, pady=12)
    body.pack(fill="both", expand=True)

    local_url = f"http://127.0.0.1:{SERVER_PORT}"
    lan_url = f"http://{lan_ip}:{SERVER_PORT}"

    info_frame = tk.Frame(body, bg="#111827", padx=14, pady=12, highlightbackground="#1e293b", highlightthickness=1)
    info_frame.pack(fill="x", pady=(0, 10))

    tk.Label(info_frame, text=f"🟢 本地服务状态: 运行中 (端口 {SERVER_PORT})   |   局域网地址: {lan_url}", font=("Microsoft YaHei UI", 9, "bold"), fg="#34d399", bg="#111827").pack(anchor="w")

    pub_var = tk.StringVar(value="正在准备公网穿透隧道...")
    pub_label = tk.Label(info_frame, textvariable=pub_var, font=("Consolas", 10, "bold"), fg="#fbbf24", bg="#111827")
    pub_label.pack(anchor="w", pady=(8, 4))

    stats_var = tk.StringVar(value="总访问人次: 1  |  排行榜记录: 3 条  |  已拦截网络攻击: 0 次")
    tk.Label(info_frame, textvariable=stats_var, font=("Microsoft YaHei UI", 9), fg="#cbd5e1", bg="#111827").pack(anchor="w")

    def on_tunnel_update(status_text, url):
        if url:
            pub_var.set(f"🌐 全球公网链接: {url}")
        else:
            pub_var.set(f"⏳ 隧道状态: {status_text}")

    tunnel = TunnelManager(port=SERVER_PORT, on_status_change=on_tunnel_update)

    # Action Buttons
    btn_frame = tk.Frame(body, bg="#090d16")
    btn_frame.pack(fill="x", pady=6)

    def copy_public_url():
        target = tunnel.public_url or lan_url
        root.clipboard_clear()
        root.clipboard_append(target)
        messagebox.showinfo("复制成功", f"已复制访问链接到剪贴板：\n{target}\n\n现在可以直接发给微信/QQ好友打开畅玩！")

    tk.Button(
        btn_frame,
        text="🎮 在浏览器打开游戏",
        command=lambda: webbrowser.open(local_url),
        bg="#0284c7",
        fg="white",
        font=("Microsoft YaHei UI", 9, "bold"),
        relief="flat",
        padx=14,
        pady=7,
    ).pack(side="left", padx=(0, 8))

    tk.Button(
        btn_frame,
        text="📋 一键复制公网链接发给朋友",
        command=copy_public_url,
        bg="#d97706",
        fg="white",
        font=("Microsoft YaHei UI", 9, "bold"),
        relief="flat",
        padx=14,
        pady=7,
    ).pack(side="left", padx=(0, 8))

    tk.Button(
        btn_frame,
        text="🔄 重新连接公网隧道",
        command=lambda: (tunnel.stop(), tunnel.start_async()),
        bg="#334155",
        fg="white",
        font=("Microsoft YaHei UI", 9),
        relief="flat",
        padx=12,
        pady=7,
    ).pack(side="left")

    # Security Audit Log Box
    tk.Label(body, text="🛡️ 实时网络安全与反作弊审计日志 (SQLite WAF):", font=("Microsoft YaHei UI", 9, "bold"), fg="#94a3b8", bg="#090d16").pack(anchor="w", pady=(8, 4))
    log_text = tk.Text(body, height=9, bg="#050811", fg="#34d399", font=("Consolas", 9), relief="flat", padx=10, pady=8)
    log_text.pack(fill="both", expand=True)
    log_text.insert("end", f"[SYSTEM] SQLite 数据库已挂载: {DB_PATH}\n")
    log_text.insert("end", "[SECURITY] 6 层防护已开启: SQLi预编译 | IP令牌桶限流 | HMAC防作弊 | XSS清洗\n")

    def refresh_ui():
        try:
            st = get_stats()
            stats_var.set(
                f"总访问人次: {st.get('visits', 1)}  |  排行榜记录: {st.get('total_records', 0)} 条  |  已拦截网络攻击: {st.get('blocked_attacks', 0)} 次"
            )
            logs = get_recent_security_logs(6)
            if logs:
                log_text.delete("1.0", "end")
                for item in reversed(logs):
                    log_text.insert(
                        "end",
                        f"[{item['created_at']}] [{item['event_type']}] IP:{item['client_ip']} -> {item['detail']}\n"
                    )
        except Exception:
            pass
        root.after(2500, refresh_ui)

    def on_close():
        tunnel.stop()
        server.stop()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    # 启动即自动拉起公网隧道
    tunnel.start_async()
    root.after(2000, refresh_ui)
    root.mainloop()

if __name__ == "__main__":
    if "--cli" in sys.argv:
        srv = GameServerController(port=SERVER_PORT)
        srv.start()
        tnl = TunnelManager(port=SERVER_PORT, on_status_change=lambda s, u: print(f"[隧道] {s} {u or ''}"))
        run_cli_mode(srv, tnl)
    else:
        run_gui_mode()
