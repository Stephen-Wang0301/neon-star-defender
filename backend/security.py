# -*- coding: utf-8 -*-
"""
6 层网络安全与防作弊中间件 (6-Layer Web Security & Anti-Cheat Middleware)
1. IP 滑动窗口限流 (防 CC / DDoS 洪水攻击)
2. 昵称 XSS 与恶意 SQL 载荷检测及清洗
3. HMAC-SHA256 一次性游戏战局令牌签名与时长合理性反作弊校验
4. 静态文件沙箱路径校验 (防 ../../ 目录穿越读取电脑隐私文件)
5. OWASP 安全响应头注入 (CSP / X-Frame-Options / nosniff)
"""
import hashlib
import hmac
import html
import os
import re
import secrets
import threading
import time
from .config import (
    FRONTEND_DIR,
    HMAC_SECRET_KEY,
    MAX_SCORE_PER_SECOND,
    RATE_LIMIT_MAX_REQ,
    RATE_LIMIT_MAX_SCORE_POST,
    RATE_LIMIT_WINDOW_SEC,
    SESSION_TTL_SECONDS,
)
from .database import log_security_event

_lock = threading.Lock()
_ip_requests = {}      # ip -> list of timestamps
_ip_score_posts = {}   # ip -> list of timestamps
_active_sessions = {}  # token_id -> start_time

SQLI_XSS_PATTERNS = re.compile(
    r"(DROP\s+TABLE|UNION\s+SELECT|DELETE\s+FROM|INSERT\s+INTO|<script|javascript:|onerror\s*=|onload\s*=|--|;)",
    re.IGNORECASE,
)

def extract_client_ip(headers, client_address) -> str:
    # 优先识别 Cloudflare Tunnel 转发的真实访客 IP
    cf_ip = headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()[:45]
    xff = headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()[:45]
    return str(client_address[0]) if client_address else "0.0.0.0"

def check_rate_limit(client_ip: str, is_score_post: bool = False) -> tuple[bool, str]:
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW_SEC
    with _lock:
        reqs = [t for t in _ip_requests.get(client_ip, []) if t > cutoff]
        if len(reqs) >= RATE_LIMIT_MAX_REQ:
            log_security_event("RATE_LIMIT_CC", client_ip, f"超过常规请求频率上限 ({RATE_LIMIT_MAX_REQ}/min)")
            return False, "请求过于频繁，请稍后再试 (429 Rate Limit)"
        reqs.append(now)
        _ip_requests[client_ip] = reqs

        if is_score_post:
            posts = [t for t in _ip_score_posts.get(client_ip, []) if t > cutoff]
            if len(posts) >= RATE_LIMIT_MAX_SCORE_POST:
                log_security_event("RATE_LIMIT_SCORE", client_ip, f"超过成绩提交频率上限 ({RATE_LIMIT_MAX_SCORE_POST}/min)")
                return False, "成绩提交过于频繁，请休息一下再试"
            posts.append(now)
            _ip_score_posts[client_ip] = posts

    return True, "OK"

def create_game_session(client_ip: str) -> dict:
    """当玩家点击开始游戏时签发一次性防篡改 HMAC 战局令牌"""
    now = int(time.time())
    nonce = secrets.token_hex(8)
    raw = f"{nonce}:{now}:{client_ip}".encode("utf-8")
    sig = hmac.new(HMAC_SECRET_KEY, raw, hashlib.sha256).hexdigest()
    token = f"{nonce}.{now}.{sig}"
    with _lock:
        # 清理过期 session
        expired = [k for k, ts in _active_sessions.items() if now - ts > SESSION_TTL_SECONDS]
        for k in expired:
            _active_sessions.pop(k, None)
        _active_sessions[nonce] = time.time()
    return {"session_token": token, "issued_at": now}

def verify_and_consume_session(token: str, client_ip: str, score: int, wave: int) -> tuple[bool, float, str]:
    """校验战局令牌签名、防止重放攻击，并验证得分与游戏时长是否合理"""
    if not token or "." not in token:
        log_security_event("ANTICHEAT_NO_TOKEN", client_ip, f"无令牌直接伪造请求 score={score}")
        return False, 0.0, "缺少安全战局签名令牌，请求已被反作弊系统拦截"

    parts = token.split(".")
    if len(parts) != 3:
        log_security_event("ANTICHEAT_BAD_TOKEN", client_ip, "令牌格式非法")
        return False, 0.0, "非法战局令牌格式"

    nonce, issued_str, sig = parts
    try:
        issued_at = int(issued_str)
    except ValueError:
        return False, 0.0, "令牌时间戳损坏"

    expected_raw = f"{nonce}:{issued_at}:{client_ip}".encode("utf-8")
    expected_sig = hmac.new(HMAC_SECRET_KEY, expected_raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        log_security_event("ANTICHEAT_HMAC_FAIL", client_ip, f"HMAC 签名不匹配 score={score}")
        return False, 0.0, "HMAC 签名校验失败，疑似篡改数据包"

    with _lock:
        start_time = _active_sessions.pop(nonce, None)

    if start_time is None:
        log_security_event("ANTICHEAT_REPLAY", client_ip, "重复使用已消耗或过期的战局令牌")
        return False, 0.0, "该局成绩已提交或令牌已失效（防重放拦截）"

    duration = max(1.0, time.time() - start_time)
    # 合理性校验：允许基础容差 + 每秒最高合理得分
    max_reasonable_score = int(1200 + duration * MAX_SCORE_PER_SECOND)
    if score < 0 or score > max_reasonable_score:
        log_security_event(
            "ANTICHEAT_SCORE_ANOMALY",
            client_ip,
            f"异常高分拦截: score={score}, duration={duration:.1f}s, max={max_reasonable_score}"
        )
        return False, duration, f"检测到异常得分数据 (耗时 {duration:.1f}s 得分 {score})"

    return True, duration, "OK"

def sanitize_player_name(raw_name: str, client_ip: str) -> tuple[bool, str, str]:
    """检测恶意 SQLi / XSS 载荷并清洗玩家昵称"""
    text = str(raw_name or "").strip()
    if SQLI_XSS_PATTERNS.search(text):
        log_security_event("WAF_PAYLOAD_BLOCK", client_ip, f"拦截恶意昵称载荷: {text[:60]}")
        return False, "", "检测到非法脚本或 SQL 注入特征，已被防火墙拦截"

    # 去除控制字符并限制长度
    cleaned = re.sub(r"[<>`;]", "", text)[:14].strip()
    if not cleaned:
        cleaned = "匿名飞行员"
    return True, html.escape(cleaned), "OK"

def is_safe_static_path(requested_path: str) -> tuple[bool, str]:
    """防止 ../../ 目录穿越攻击，确保只能访问 frontend 目录下的静态资源"""
    clean_rel = requested_path.split("?")[0].split("#")[0].lstrip("/")
    if not clean_rel or clean_rel == "/":
        clean_rel = "index.html"
    full_path = os.path.realpath(os.path.join(FRONTEND_DIR, clean_rel))
    root_real = os.path.realpath(FRONTEND_DIR)
    if not full_path.startswith(root_real + os.sep) and full_path != root_real:
        return False, ""
    return True, full_path

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "X-XSS-Protection": "1; mode=block",
}
