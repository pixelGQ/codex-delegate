# Codex delegate (agent) runner — EN

A second Codex instance ("agent") with its own config/session and optional internet access. The main Codex (you) enqueue tasks; the agent runs them and streams logs.

## Quick start (after install)
- Send a task: `delegate "do X" [--cwd path] [--timeout 120] [--allow-net] [--live] [--json]`
- Live stream: `delegate "..." --live` (shows request/stream/final)
- Tail later: `delegate --stream <task_id>`
- Restart runner: `delegate --restart`
- Check status: `delegate --status`
- TUI monitor: `delegate-ui` or alias `dlg` (left: tasks; right: log; q quits)

## Full install on a new machine (≈5 min)
1) Dependency: `sudo apt-get install -y python3-pexpect` (or `pip install -r requirements.txt`).
2) Code: place project at `~/codex-delegate` (e.g., `git clone <repo> ~/codex-delegate`).
3) Agent token: `mkdir -p ~/.codex-agent && cp ~/.codex/auth.json ~/.codex-agent/`  
   (or `CODEX_HOME=~/.codex-agent codex login` for a separate login).
4) Agent config `~/.codex-agent/config.toml`:
   ```toml
   model = "gpt-5.1-codex-max"
   model_reasoning_effort = "high"
   [projects."/home/<user>"]
   trust_level = "trusted"
   [features]
   web_search_request = true
   [sandbox_workspace_write]
   network_access = true
   ```
5) PATH/aliases:  
   `echo 'PATH="$HOME/codex-delegate/bin:$PATH"' >> ~/.zshrc`  
   `echo 'alias dlg="delegate-ui"' >> ~/.zshrc`  
   then `source ~/.zshrc`.
6) Start runner: `delegate --restart`; check `delegate --status` (runner log: `/tmp/delegate_runner.log`).
7) Smoke test web: `delegate "who won euro 2021" --research --live`.

## Files & directories
- `runtime/delegate.in`   — incoming JSONL tasks.
- `runtime/delegate.out`  — final answers (JSONL).
- `runtime/delegate.stream` — event stream (request/stream/final/error, JSONL).
- `streams/<task_id>.log` — raw stdout/stderr per task.
- `runtime/delegate.log`  — runner log.
- Agent config: `~/.codex-agent/config.toml` (separate from main `~/.codex`).

## Protocol (v1)
Request (one JSON line):
```
{
  "task_id": "uuid",
  "instruction": "what to do",
  "cwd": "/path",
  "timeout_s": 90,
  "allow_net": true,
  "context_files": []
}
```
Response:
```
{
  "task_id": "uuid",
  "status": "ok|timeout|error",
  "summary": "short",
  "stdout": "...truncated",
  "stderr": "...truncated",
  "truncated": true/false,
  "duration_ms": 1234
}
```

## Defaults / limits
- timeout: 90s
- max instruction length: 4096 chars
- stdout+stderr in final: 16 KB (then truncated)

## Key flags (`delegate`)
- `--allow-net` / `--no-net` — enable/disable web search (default on).
- `--research` — web-research mode: auto `--search`, prompt asks for concise summary + 3–5 sources.
- `--context f1,f2` — inject file contents (≈24 KB cap).
- `--artifact path` — save stdout to file relative to `--cwd`.
- `--live` — stream events live.
- `--json` — return final as single JSON line.

## Agent auth
- Runner uses `CODEX_HOME=~/.codex-agent`. Copy token: `cp ~/.codex/auth.json ~/.codex-agent/` or login with `CODEX_HOME=~/.codex-agent codex login`.

## Debug
- Runner log: `/tmp/delegate_runner.log`
- Event stream: `runtime/delegate.stream`
- Task log: `streams/<task_id>.log`
- If no web data: check `~/.codex-agent/config.toml` (`web_search_request=true`, `network_access=true`) and ensure `--no-net` not set.
