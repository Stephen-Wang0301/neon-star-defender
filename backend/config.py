# -*- coding: utf-8 -*-
"""
统一配置中心 (Centralized Configuration)
修改端口、安全阈值或数据库路径只需在此文件调整。
"""
import os
import secrets
import sys

def get_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = get_base_dir()
FRONTEND_DIR = os.path.join(
    getattr(sys, "_MEIPASS", BASE_DIR), "frontend"
) if getattr(sys, "frozen", False) else os.path.join(BASE_DIR, "frontend")

DATA_DIR = os.path.join(BASE_DIR, "data")
BIN_DIR = os.path.join(BASE_DIR, "bin")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(BIN_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "game_data.db")
SECRET_KEY_FILE = os.path.join(DATA_DIR, "server_secret.key")

def load_or_create_secret_key() -> bytes:
    if os.path.exists(SECRET_KEY_FILE):
        try:
            with open(SECRET_KEY_FILE, "rb") as f:
                key = f.read().strip()
                if len(key) >= 32:
                    return key
        except Exception:
            pass
    new_key = secrets.token_hex(32).encode("utf-8")
    try:
        with open(SECRET_KEY_FILE, "wb") as f:
            f.write(new_key)
    except Exception:
        pass
    return new_key

SERVER_HOST = "0.0.0.0"
SERVER_PORT = int(os.environ.get("GAME_SERVER_PORT", "8080"))

# 网络安全与反作弊阈值 (Security & Anti-Cheat Limits)
MAX_PAYLOAD_BYTES = 4096          # 限制单次 POST 请求最大 4KB，防止大包内存溢出攻击
RATE_LIMIT_WINDOW_SEC = 60        # 限流滑动窗口：60 秒
RATE_LIMIT_MAX_REQ = 90           # 每个 IP 每分钟最大常规请求数
RATE_LIMIT_MAX_SCORE_POST = 6     # 每个 IP 每分钟最大成绩提交次数
MAX_SCORE_PER_SECOND = 450        # 反作弊校验：每秒理论最大合理得分上限
SESSION_TTL_SECONDS = 3600        # 单局游戏令牌有效期：1 小时
HMAC_SECRET_KEY = load_or_create_secret_key()
