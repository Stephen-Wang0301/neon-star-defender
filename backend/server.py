# -*- coding: utf-8 -*-
"""
多线程安全 Web 与 API 游戏服务器 (Multi-threaded Secure HTTP & REST API Server)
"""
import json
import mimetypes
import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .config import MAX_PAYLOAD_BYTES, SERVER_HOST, SERVER_PORT
from .database import (
    get_recent_security_logs,
    get_stats,
    get_top_scores,
    increment_stat,
    init_db,
    insert_score,
    log_security_event,
)
from .security import (
    SECURITY_HEADERS,
    check_rate_limit,
    create_game_session,
    extract_client_ip,
    is_safe_static_path,
    sanitize_player_name,
    verify_and_consume_session,
)

def get_lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

class SecureGameRequestHandler(BaseHTTPRequestHandler):
    server_version = "NeonStarDefenderServer/2.0"
    sys_version = ""

    def log_message(self, fmt, *args):
        # 由外部监听器或控制台统一管理日志输出
        pass

    def _send_security_headers(self):
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)

    def _send_json(self, status_code: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self._send_security_headers()
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        client_ip = extract_client_ip(self.headers, self.client_address)
        allowed, msg = check_rate_limit(client_ip, is_score_post=False)
        if not allowed:
            self._send_json(429, {"ok": False, "error": msg})
            return

        if self.path.startswith("/api/session"):
            session_info = create_game_session(client_ip)
            self._send_json(200, {"ok": True, **session_info})
            return

        if self.path.startswith("/api/scores"):
            visits = increment_stat("visits", 1)
            stats = get_stats()
            scores = get_top_scores(25)
            self._send_json(200, {
                "ok": True,
                "visits": visits,
                "blocked_attacks": stats.get("blocked_attacks", 0),
                "scores": scores,
            })
            return

        if self.path.startswith("/api/security-status"):
            stats = get_stats()
            logs = get_recent_security_logs(12)
            self._send_json(200, {
                "ok": True,
                "stats": stats,
                "recent_logs": logs,
            })
            return

        # 静态文件沙箱检查 (防止目录穿越攻击)
        safe, full_path = is_safe_static_path(self.path)
        if not safe or not os.path.isfile(full_path):
            if not safe:
                log_security_event("PATH_TRAVERSAL", client_ip, f"尝试非法路径访问: {self.path[:80]}")
            self._send_json(404, {"ok": False, "error": "404 Not Found"})
            return

        mime_type, _ = mimetypes.guess_type(full_path)
        mime_type = mime_type or "application/octet-stream"
        try:
            with open(full_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", f"{mime_type}; charset=utf-8" if mime_type.startswith("text/") else mime_type)
            self.send_header("Content-Length", str(len(content)))
            self._send_security_headers()
            self.end_headers()
            self.wfile.write(content)
        except Exception:
            self._send_json(500, {"ok": False, "error": "Internal Server Error"})

    def do_POST(self):
        client_ip = extract_client_ip(self.headers, self.client_address)
        allowed, msg = check_rate_limit(client_ip, is_score_post=True)
        if not allowed:
            self._send_json(429, {"ok": False, "error": msg})
            return

        if not self.path.startswith("/api/scores"):
            self._send_json(404, {"ok": False, "error": "Unknown API endpoint"})
            return

        try:
            content_len = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            content_len = 0

        if content_len <= 0 or content_len > MAX_PAYLOAD_BYTES:
            log_security_event("PAYLOAD_OVERSIZE", client_ip, f"异常请求体大小: {content_len} bytes")
            self._send_json(413, {"ok": False, "error": "请求数据包大小超出安全限制 (Max 4KB)"})
            return

        raw_body = self.rfile.read(content_len).decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw_body)
        except Exception:
            log_security_event("MALFORMED_JSON", client_ip, "非法的 JSON 格式请求")
            self._send_json(400, {"ok": False, "error": "非法的 JSON 数据格式"})
            return

        raw_name = payload.get("name", "匿名飞行员")
        name_ok, clean_name, name_err = sanitize_player_name(raw_name, client_ip)
        if not name_ok:
            self._send_json(400, {"ok": False, "error": name_err})
            return

        try:
            score = int(payload.get("score", 0))
            wave = max(1, min(999, int(payload.get("wave", 1))))
        except (ValueError, TypeError):
            self._send_json(400, {"ok": False, "error": "分数字段类型非法"})
            return

        session_token = str(payload.get("session_token", ""))
        token_ok, duration_sec, token_err = verify_and_consume_session(
            session_token, client_ip, score, wave
        )
        if not token_ok:
            self._send_json(403, {"ok": False, "error": token_err})
            return

        insert_score(clean_name, score, wave, duration_sec, client_ip)
        stats = get_stats()
        self._send_json(200, {
            "ok": True,
            "scores": get_top_scores(25),
            "visits": stats.get("visits", 1),
            "blocked_attacks": stats.get("blocked_attacks", 0),
        })

class GameServerController:
    def __init__(self, host: str = SERVER_HOST, port: int = SERVER_PORT):
        self.host = host
        self.port = port
        self.httpd = None
        self.thread = None

    def start(self):
        init_db()
        if self.httpd is not None:
            return
        self.httpd = ThreadingHTTPServer((self.host, self.port), SecureGameRequestHandler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
