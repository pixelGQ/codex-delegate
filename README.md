# Codex Delegate Runner (agent)

A tiny queue + UI that lets your primary Codex instance delegate tasks to a second Codex session (“agent”) that can use the internet, run commands in a chosen working dir, and stream output. Good for:
- Offloading long or noisy tasks (web research, codegen, scripts) without clogging your main Codex context.
- Having a lightweight dashboard/TUI to watch multiple tasks.
- Keeping the agent in a separate config/token (`~/.codex-agent`) so it doesn’t touch your main Codex auth/history.

*Русская версия: `README.ru.md`*

## How it works
- CLI helper `delegate` appends tasks to `runtime/delegate.in` (JSONL).
- `delegate_runner.py` watches the queue, runs `codex exec --skip-git-repo-check --cd <cwd>` with `CODEX_HOME=~/.codex-agent`, streams stdout/stderr to `streams/<task>.log` and events to `runtime/delegate.stream`, writes finals to `runtime/delegate.out`.
- `delegate-ui` (curses) shows a table of tasks on the left and the selected log on the right.

## Requirements
- Linux/macOS shell with Python 3.8+.
- `codex` CLI installed and logged in (primary), plus a separate agent config/token at `~/.codex-agent`.
- `python3-pexpect` (or `pip install -r requirements.txt`).
## Install (clean machine, ~5 minutes)
1) Install dependency: `sudo apt-get install -y python3-pexpect` (or `pip install -r requirements.txt`).
2) Place the repo, e.g. `git clone https://github.com/pixelGQ/codex-delegate.git ~/codex-delegate`.
3) Agent token & config:
   ```bash
   mkdir -p ~/.codex-agent
   cp ~/.codex/auth.json ~/.codex-agent/    # reuse token, or run:
   CODEX_HOME=~/.codex-agent codex login    # separate login
   cat > ~/.codex-agent/config.toml <<'CFG'
   model = "gpt-5.1-codex-max"
   model_reasoning_effort = "high"
   [projects."$HOME"]
   trust_level = "trusted"
   [features]
   web_search_request = true
   [sandbox_workspace_write]
   network_access = true
   CFG
   ```
4) PATH + alias:
   ```bash
   echo 'PATH="$HOME/codex-delegate/bin:$PATH"' >> ~/.zshrc
   echo 'alias dlg="delegate-ui"' >> ~/.zshrc
   source ~/.zshrc
   ```
5) Start runner: `delegate --restart`; check: `delegate --status` (log: `/tmp/delegate_runner.log`).
6) Smoke test web: `delegate "who won euro 2021" --research --live`.

## Usage (CLI)
- Basic: `delegate "do X" [--cwd path] [--timeout 120] [--allow-net|--no-net] [--live] [--json]`
- Research preset: `--research` (forces `--search`, prompt asks for concise answer + 3–5 sources).
- Context files: `--context file1,file2` (injects up to ~24 KB of content into the prompt).
- Artifact: `--artifact path` (save stdout to file relative to `--cwd`).
- Model/profile/sandbox: `--model`, `--profile`, `--sandbox` (defaults: model from config, sandbox workspace-write).
- Stream later: `delegate --stream <task_id>`.
- Monitor UI: `delegate-ui` or `dlg` (q to quit, arrows to select).

## Files
- `runtime/delegate.in`   — incoming tasks (JSONL)
- `runtime/delegate.out`  — final answers (JSONL)
- `runtime/delegate.stream` — event stream (request/stream/final/error, JSONL)
- `streams/<task>.log`    — raw stdout/stderr
- `delegate_runner.py`    — queue worker
- `delegate_tui.py`       — curses monitor

## Defaults & limits
- Timeout 90s; max instruction ~4096 chars; final stdout+stderr capped at 16 KB (truncated with a flag).

## Why separate agent?
- Keeps your main Codex token/history clean; can use different sandbox or internet policy.
- Lets you run noisy/long web or build tasks without filling main context.
- Simple observable pipeline (JSONL + TUI) you can extend to web/desktop UI later.

## Troubleshooting
- Runner log: `/tmp/delegate_runner.log`
- No web? Check `~/.codex-agent/config.toml` has `web_search_request=true`, `network_access=true`; ensure you didn’t pass `--no-net`.
