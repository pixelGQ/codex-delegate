# Delegate (agent) — full guide (EN)

## What it is
A second Codex instance (“agent”) with its own config (`~/.codex-agent`). Tasks are queued via files; the runner calls `codex exec`, streams logs, and writes finals to JSONL.

## Fast setup (done on this box)
1) Project: `~/codex-delegate/`
2) Token copy: `cp ~/.codex/auth.json ~/.codex-agent/`
3) Agent config `~/.codex-agent/config.toml`:
   ```toml
   model = "gpt-5.1-codex-max"
   model_reasoning_effort = "high"
   [projects."/home/pixel"]
   trust_level = "trusted"
   [features]
   web_search_request = true
   [sandbox_workspace_write]
   network_access = true
   ```
4) PATH/alias in `~/.zshrc`: `PATH="$HOME/codex-delegate/bin:$PATH"`, alias `dlg=delegate-ui`.

## Install on another machine
1) Dep: `sudo apt-get install -y python3-pexpect` (or `pip install -r requirements.txt`).
2) Clone to `~/codex-delegate`.
3) Token: `mkdir -p ~/.codex-agent && cp ~/.codex/auth.json ~/.codex-agent/` **or** `CODEX_HOME=~/.codex-agent codex login`.
4) Config: same TOML as above, adjust `/home/pixel` → your `$HOME`.
5) Shell: add PATH/alias, `source ~/.zshrc`.
6) Start runner: `delegate --restart`, check `delegate --status`.
7) Smoke: `delegate "who won euro 2021" --research --live`.

## CLI
- `delegate "instruction" [--cwd path] [--timeout N] [--allow-net] [--live] [--json] [--label txt] [--model m] [--profile p] [--sandbox mode] [--artifact path] [--context f1,f2] [--research]`
- `delegate --status` / `--restart` / `--stream TASK_ID`

Flags of note
- `--allow-net` / `--no-net` — toggle web_search (default on).
- `--research` — web-research preset: enables `--search`, asks for concise answer + 3–5 sources.
- `--context f1,f2` — inject files into the prompt (≈24 KB cap).
- `--artifact path` — save stdout to file relative to `cwd`.
- `--live` — live event stream.
- `--json` — final JSON line.

## Files/structure
- `runtime/delegate.in` — incoming tasks (JSONL)
- `runtime/delegate.out` — finals (JSONL)
- `runtime/delegate.stream` — events (request/stream/final/error)
- `streams/<task>.log` — raw stdout/stderr
- `delegate_runner.py` — queue worker
- `delegate_tui.py` — curses monitor (left: tasks, right: log)

## Limits
- timeout: 90s default
- stdout+stderr in final: 16 KB (truncates with a note)

## Troubleshooting
- Runner log: `/tmp/delegate_runner.log`
- Empty/old data? Check `delegate --restart`
- No web? Verify `~/.codex-agent/config.toml` has `web_search_request=true`, `network_access=true`; and you didn’t pass `--no-net`.
