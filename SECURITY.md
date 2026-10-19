# 安全策略与防护说明 (Security Policy)

维护者：[@Stephen-Wang0301](https://github.com/Stephen-Wang0301)

## 内置 6 层网络安全架构
1. **防 SQL 注入 (SQL Injection)**：`backend/database.py` 使用 SQLite3 WAL 模式，所有数据库读写强制使用 `?` 参数化预编译查询，并配合 `SQLI_XSS_PATTERNS` 拦截恶意语句。
2. **防 CC / DDoS 频率限制 (Rate Limiting)**：`backend/security.py` 对每个公网访客 IP（支持识别 `CF-Connecting-IP`）实施滑动窗口限流。
3. **防抓包改分与重放攻击 (HMAC-SHA256 Anti-Cheat)**：每局游戏开始时由 `/api/session` 签发带时间戳与 IP 绑定的 HMAC 令牌，结算时校验签名及游戏时长合理性，令牌一次性销毁。
4. **防跨站脚本与超大请求包 (XSS & Payload Cap)**：严格限制 POST 请求体不超过 4KB，并对玩家昵称执行 HTML 实体转义。
5. **防目录穿越 (Path Traversal Sandbox)**：通过 `os.path.realpath` 锁定静态资源访问范围仅限 `frontend/` 目录。
6. **OWASP 安全响应头**：全站启用 `X-Content-Type-Options: nosniff`、`X-Frame-Options: SAMEORIGIN` 与 `Referrer-Policy`。
