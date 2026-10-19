# -*- coding: utf-8 -*-
"""
全自动公网隧道管理器 (Automated Cloudflare Quick Tunnel Manager)
- 自动检测系统平台并在缺少 cloudflared 时从官方 GitHub Releases 下载到 bin/
- 后台静默启动隧道进程（Windows 下隐藏黑框），自动提取 https://xxxx.trycloudflare.com 公网网址
"""
import os
import platform
import re
import shutil
import subprocess
import threading
import urllib.request
from .config import BIN_DIR, SERVER_PORT

TUNNEL_URL_REGEX = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")

class TunnelManager:
    def __init__(self, port: int = SERVER_PORT, on_status_change=None):
        self.port = port
        self.on_status_change = on_status_change
        self.process = None
        self.public_url = None
        self.status = "未启动"
        self._lock = threading.Lock()

    def _notify(self, status_text: str, url: str = None):
        self.status = status_text
        if url:
            self.public_url = url
        if self.on_status_change:
            try:
                self.on_status_change(self.status, self.public_url)
            except Exception:
                pass

    def get_binary_path(self) -> str:
        sys_Path = shutil.which("cloudflared")
        if sys_Path:
            return sys_Path
        is_win = platform.system().lower().startswith("win")
        exe_name = "cloudflared.exe" if is_win else "cloudflared"
        return os.path.join(BIN_DIR, exe_name)

    def ensure_binary(self) -> tuple[bool, str]:
        bin_path = self.get_binary_path()
        if os.path.exists(bin_path) and os.path.getsize(bin_path) > 1024 * 1024:
            return True, bin_path

        sys_name = platform.system().lower()
        machine = platform.machine().lower()
        if sys_name.startswith("win"):
            url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
        elif sys_name == "darwin":
            url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-amd64.tgz"
        else:
            arch = "arm64" if "aarch64" in machine or "arm64" in machine else "amd64"
            url = f"https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-{arch}"

        self._notify("正在首次自动下载公网隧道组件 (cloudflared)...")
        try:
            urllib.request.urlretrieve(url, bin_path)
            if not sys_name.startswith("win"):
                os.chmod(bin_path, 0o755)
            return True, bin_path
        except Exception as e:
            self._notify(f"自动下载失败，请检查网络: {e}")
            return False, str(e)

    def start_async(self):
        threading.Thread(target=self._run_tunnel, daemon=True).start()

    def _run_tunnel(self):
        with self._lock:
            if self.process and self.process.poll() is None:
                return
            ok, bin_path = self.ensure_binary()
            if not ok:
                return

            self._notify("正在建立全球 HTTPS 公网加密隧道...")
            cmd = [bin_path, "tunnel", "--url", f"http://127.0.0.1:{self.port}", "--no-autoupdate"]
            creationflags = 0
            if platform.system().lower().startswith("win"):
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

            try:
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    creationflags=creationflags,
                )
            except Exception as e:
                self._notify(f"启动隧道进程失败: {e}")
                return

        for line in iter(self.process.stdout.readline, ""):
            match = TUNNEL_URL_REGEX.search(line)
            if match:
                url = match.group(0)
                self._notify("公网隧道已连通 (所有人可访问)", url)

    def stop(self):
        with self._lock:
            if self.process and self.process.poll() is None:
                try:
                    self.process.terminate()
                except Exception:
                    pass
            self.process = None
            self.public_url = None
            self._notify("已停止公网隧道")
