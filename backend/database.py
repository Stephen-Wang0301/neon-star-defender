# -*- coding: utf-8 -*-
"""
SQLite 本地关系型数据库模块 (Local SQLite Relational Database Engine)
- 采用 WAL (Write-Ahead Logging) 模式支持多人并发读写
- 100% 强制使用 `?` 参数化预编译查询，彻底杜绝 SQL 注入攻击 (SQL Injection)
"""
import sqlite3
import threading
from datetime import datetime
from .config import DB_PATH

_db_lock = threading.Lock()

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
    except sqlite3.OperationalError:
        conn.execute("PRAGMA journal_mode=DELETE;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def init_db():
    with _db_lock:
        conn = get_connection()
        try:
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS scores (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        player_name TEXT NOT NULL,
                        score INTEGER NOT NULL CHECK(score >= 0 AND score <= 5000000),
                        wave INTEGER NOT NULL CHECK(wave >= 1 AND wave <= 999),
                        play_duration_sec REAL DEFAULT 0,
                        client_ip TEXT,
                        created_at TEXT NOT NULL
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_scores_val ON scores(score DESC);")

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS server_stats (
                        stat_key TEXT PRIMARY KEY,
                        stat_val INTEGER NOT NULL DEFAULT 0
                    );
                """)
                conn.execute("INSERT OR IGNORE INTO server_stats (stat_key, stat_val) VALUES ('visits', 1);")
                conn.execute("INSERT OR IGNORE INTO server_stats (stat_key, stat_val) VALUES ('blocked_attacks', 0);")

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS security_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_type TEXT NOT NULL,
                        client_ip TEXT NOT NULL,
                        detail TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );
                """)

                # 若榜单为空则写入初始守门员记录
                cur = conn.execute("SELECT COUNT(*) AS cnt FROM scores;")
                if cur.fetchone()["cnt"] == 0:
                    seed_rows = [
                        ("房主主机 (Stephen)", 2860, 6, 45.0, "127.0.0.1", "初始守门员"),
                        ("星际漫游者", 1950, 5, 38.0, "127.0.0.1", "初始记录"),
                        ("NeonPilot", 1420, 4, 29.0, "127.0.0.1", "初始记录"),
                    ]
                    conn.executemany(
                        "INSERT INTO scores (player_name, score, wave, play_duration_sec, client_ip, created_at) VALUES (?, ?, ?, ?, ?, ?);",
                        seed_rows
                    )
        finally:
            conn.close()

def increment_stat(key: str, delta: int = 1) -> int:
    with _db_lock:
        conn = get_connection()
        try:
            with conn:
                conn.execute(
                    "UPDATE server_stats SET stat_val = stat_val + ? WHERE stat_key = ?;",
                    (int(delta), str(key))
                )
                cur = conn.execute("SELECT stat_val FROM server_stats WHERE stat_key = ?;", (str(key),))
                row = cur.fetchone()
                return row["stat_val"] if row else 0
        finally:
            conn.close()

def get_stats() -> dict:
    conn = get_connection()
    try:
        cur = conn.execute("SELECT stat_key, stat_val FROM server_stats;")
        stats = {r["stat_key"]: r["stat_val"] for r in cur.fetchall()}
        cur_cnt = conn.execute("SELECT COUNT(*) AS total_records FROM scores;")
        stats["total_records"] = cur_cnt.fetchone()["total_records"]
        return stats
    finally:
        conn.close()

def get_top_scores(limit: int = 25) -> list:
    conn = get_connection()
    try:
        cur = conn.execute(
            "SELECT player_name AS name, score, wave, created_at AS time FROM scores ORDER BY score DESC, id ASC LIMIT ?;",
            (int(limit),)
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

def insert_score(player_name: str, score: int, wave: int, duration_sec: float, client_ip: str):
    now_str = datetime.now().strftime("%m-%d %H:%M")
    with _db_lock:
        conn = get_connection()
        try:
            with conn:
                conn.execute(
                    "INSERT INTO scores (player_name, score, wave, play_duration_sec, client_ip, created_at) VALUES (?, ?, ?, ?, ?, ?);",
                    (player_name, int(score), int(wave), float(duration_sec), str(client_ip), now_str)
                )
        finally:
            conn.close()

def log_security_event(event_type: str, client_ip: str, detail: str):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    increment_stat("blocked_attacks", 1)
    with _db_lock:
        conn = get_connection()
        try:
            with conn:
                conn.execute(
                    "INSERT INTO security_logs (event_type, client_ip, detail, created_at) VALUES (?, ?, ?, ?);",
                    (str(event_type)[:32], str(client_ip)[:64], str(detail)[:256], now_str)
                )
        finally:
            conn.close()

def get_recent_security_logs(limit: int = 15) -> list:
    conn = get_connection()
    try:
        cur = conn.execute(
            "SELECT event_type, client_ip, detail, created_at FROM security_logs ORDER BY id DESC LIMIT ?;",
            (int(limit),)
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
