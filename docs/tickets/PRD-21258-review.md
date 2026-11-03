# PRD-21258 · Code review

## Round 1 · 2026-11-03 · reviewed dev/PRD-21258 @ 2d6e4ab (base main @ 10c3dce)

Verdict: changes requested

### Findings

1. [must-fix] `src/betterstack_mcp/api_client.py:69,72,83` (and `src/betterstack_mcp/server.py:26`) — the service has no structured per-request logging at all: no request-id/correlation-id, no tool name, no duration anywhere in the codebase. `server.py:26` declares `logger = logging.getLogger("betterstack_mcp.server")` but never calls it; `api_client.py` only logs `logger.warning(...)` on the retry/timeout paths with just `path=%s attempt=%s` — nothing is logged on the (far more common) success path, and none of the three warning call sites carry a request-id. This fails SOP §6 ("用结构化日志...每条带 request-id / 关联 id" / "记录：工具名、入参摘要（脱敏）、你的 API 路径与状态码、耗时、错误 code") and the §14 delivery checklist item "结构化日志带 request-id", which `references/mcp-track.md` 4.3 lists verbatim as one of the MCP review must-fix bullets ("SOP §14 Checklist"). It also contradicts the design doc's own Non-functional § "Observability" claim ("structured logs with request-id, tool name, redacted arg summary, BetterStack status code, duration, error code") — the implementation does not do what the design says it does. Fix: add a request-scoped id (e.g. generated in `CredentialMiddleware` alongside the credential `ContextVar`, or read from an inbound correlation header if the gateway sends one) and log it together with tool name and call duration on both success and failure paths.
2. [must-fix] `docs/tickets/PRD-21258.md:272` — contains the Chinese characters `完成标准` (quoting a cross-referenced section title from `mcp-track.md` §3). SOP §0.4 ("语言：仓库内容全部用英文（必须）") is explicit that this is a **must**, covers "`README.md` 及仓库里的其它文档" (which includes `docs/tickets/*.md`), and `mcp-track.md` 4.3 restates it as its own must-fix bullet ("仓库里没有中文"). This also makes the Self-test section's own claimed evidence inaccurate: the "Chinese-text scan" row (`PRD-21258.md:260`) states the result as "No output (clean)", but re-running the exact command in this review (`grep -rnP '[\x{4e00}-\x{9fff}]' --exclude-dir=.git --exclude-dir=.venv .`) produces one match — this line. Fix: paraphrase the citation in English (e.g. "the SOP's completion-criteria section") so the repo is actually clean and the Self-test claim is true when re-run.

### Verification performed this round

- `uv sync --frozen && uv run pytest -q` on `dev/PRD-21258 @ 2d6e4ab`: 34 passed, 0 failed (confirms the `[DEV]` stub's gate claim).
- `grep -rnP '[\x{4e00}-\x{9fff}]' --exclude-dir=.git --exclude-dir=.venv .`: 1 match (`docs/tickets/PRD-21258.md:272`), contradicting the Self-test section's "No output (clean)" claim — see finding 2.
- `grep -rn "request_id|request-id|correlation" src/ tests/`: 0 matches; `grep -rn "logger\." src/`: only the 3 call sites cited in finding 1 — confirms finding 1 by direct inspection, no logging framework elsewhere in the service.
- README "MSPbots Connector" section diffed by eye against `~/.claude/skills/vendor-mcp-development/reference/readme-connector-section.md`: byte-identical, confirms the `[DEV]` stub's claim on this point.
- `gitleaks` is not installed in this review environment; relying on the dev leg's own gate result for that item (no override).
