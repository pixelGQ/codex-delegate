#!/usr/bin/env python3
"""
Delegate runner: manages a secondary Codex ("agent") session.
- Reads tasks from runtime/delegate.in (JSONL)
- Streams agent output to runtime/delegate.stream and streams/<task_id>.log
- Writes final responses to runtime/delegate.out (JSONL)
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import signal
import subprocess
import sys
import time
import uuid
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


RUNTIME_DIR = Path(__file__).parent / "runtime"
STREAMS_DIR = Path(__file__).parent / "streams"

DEFAULT_TIMEOUT = 90
MAX_INSTRUCTION_LEN = 4096
MAX_OUTPUT_BYTES = 16 * 1024
MAX_CONTEXT_BYTES = 24 * 1024


@dataclass
class Task:
    task_id: str
    instruction: str
    cwd: str
    timeout_s: int
    allow_net: bool
    context_files: list[str]
    label: str
    model: Optional[str]
    profile: Optional[str]
    sandbox: Optional[str]
    approval: Optional[str]
    artifact: Optional[str]
    research: bool


@dataclass
class AgentCfg:
    codex_bin: str
    codex_home: Path


def now_ms() -> int:
    return int(time.time() * 1000)


def ensure_dirs() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    STREAMS_DIR.mkdir(parents=True, exist_ok=True)


def load_task(line: str) -> Optional[Task]:
    try:
        obj = json.loads(line)
        instruction = obj.get("instruction", "")[:MAX_INSTRUCTION_LEN]
        return Task(
            task_id=obj.get("task_id") or str(uuid.uuid4()),
            instruction=instruction,
            cwd=obj.get("cwd") or os.getcwd(),
            timeout_s=int(obj.get("timeout_s") or DEFAULT_TIMEOUT),
            allow_net=bool(obj.get("allow_net", True)),
            context_files=obj.get("context_files", []) or [],
            label=obj.get("label", "")[:64],
            model=obj.get("model"),
            profile=obj.get("profile"),
            sandbox=obj.get("sandbox"),
            approval=obj.get("approval"),
            artifact=obj.get("artifact"),
            research=bool(obj.get("research", False)),
        )
    except Exception:
        return None


def write_jsonl(path: Path, obj: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def truncate_text(text: str, limit: int) -> tuple[str, bool]:
    if len(text.encode("utf-8")) <= limit:
        return text, False
    encoded = text.encode("utf-8")[:limit]
    return encoded.decode("utf-8", errors="ignore") + "\n...[truncated]...", True


def stream_event(event_type: str, task: Task, payload: dict) -> None:
    event = {
        "ts": now_ms(),
        "type": event_type,
        "task_id": task.task_id,
        "label": task.label,
        **payload,
    }
    write_jsonl(RUNTIME_DIR / "delegate.stream", event)


def build_context(task: Task) -> str:
    """Load context files and prepend as a system-style note."""
    if not task.context_files:
        return ""
    parts = []
    total = 0
    for path in task.context_files:
        p = Path(task.cwd) / path
        if not p.exists() or not p.is_file():
            continue
        try:
            data = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        chunk = f"\n\n# File: {path}\n{data}"
        b = len(chunk.encode("utf-8"))
        if total + b > MAX_CONTEXT_BYTES:
            break
        parts.append(chunk)
        total += b
    if not parts:
        return ""
    return "Please reference the following files:\n" + "".join(parts) + "\n\n"


def process_task(cfg: AgentCfg, task: Task) -> None:
    start = now_ms()
    stream_event("request", task, {"instruction": task.instruction, "cwd": task.cwd})

    task_log = STREAMS_DIR / f"{task.task_id}.log"
    out_buf: list[str] = []
    err_buf: list[str] = []

    env = os.environ.copy()
    env["CODEX_HOME"] = str(cfg.codex_home)

    sandbox = task.sandbox or "workspace-write"

    cmd = [cfg.codex_bin]
    if task.allow_net or task.research:
        cmd.append("--search")
        cmd += ["--enable", "web_search_request"]
    cmd += ["exec", "--skip-git-repo-check", "--cd", task.cwd]
    if task.model:
        cmd += ["-m", task.model]
    if task.profile:
        cmd += ["-p", task.profile]
    cmd += ["-s", sandbox]

    instruction = task.instruction
    ctx = build_context(task)
    if ctx:
        instruction = ctx + instruction
    if task.research:
        instruction = (
            "Act as a fast web researcher. Use web_search when helpful. "
            "Return a concise answer with bullet summary and list 3-5 sources. "
            "Question:\n" + instruction
        )

    cmd.append(instruction)

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=env,
    )

    deadline = time.time() + task.timeout_s
    status = "ok"
    truncated = False

    NOISE_PREFIXES = (
        "OpenAI Codex v",
        "--------",
        "session id:",
        "tokens used",
        "workdir:",
        "model:",
        "provider:",
        "approval:",
        "sandbox:",
        "reasoning effort:",
        "reasoning summaries:",
        "mcp startup:",
    )

    ansi_re = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")

    def clean(text: str) -> str:
        return ansi_re.sub("", text).strip("\r\n")

    def is_noise(text: str) -> bool:
        return clean(text).startswith(NOISE_PREFIXES)

    def handle_line(kind: str, line: str) -> None:
        nonlocal truncated
        if not line:
            return
        if is_noise(line):
            return
        line_clean = clean(line)
        with task_log.open("a", encoding="utf-8") as f:
            f.write(line_clean)
            if not line_clean.endswith("\n"):
                f.write("\n")
        stream_event("stream", task, {"kind": kind, "line": line_clean})
        if kind == "stdout":
            out_buf.append(line_clean + "\n")
        else:
            err_buf.append(line_clean + "\n")
        if len("".join(out_buf + err_buf).encode("utf-8")) > MAX_OUTPUT_BYTES:
            truncated = True

    while time.time() < deadline:
        if proc.poll() is not None:
            break
        ready = False
        if proc.stdout:
            line = proc.stdout.readline()
            if line:
                handle_line("stdout", line.rstrip("\r\n"))
                ready = True
        if proc.stderr:
            line = proc.stderr.readline()
            if line:
                handle_line("stderr", line.rstrip("\r\n"))
                ready = True
        if not ready:
            time.sleep(0.1)

    if proc.poll() is None:
        status = "timeout"
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
    else:
        proc.wait()

    stdout_text, trunc2 = truncate_text("".join(out_buf), MAX_OUTPUT_BYTES)
    truncated = truncated or trunc2

    # write artifact if requested
    if task.artifact:
        art_path = Path(task.cwd) / task.artifact
        try:
            art_path.parent.mkdir(parents=True, exist_ok=True)
            art_path.write_text("".join(out_buf), encoding="utf-8")
        except Exception:
            pass

    resp = {
        "task_id": task.task_id,
        "status": status,
        "summary": stdout_text.splitlines()[0][:200] if stdout_text else "",
        "stdout": stdout_text,
        "stderr": "".join(err_buf),
        "truncated": truncated,
        "duration_ms": now_ms() - start,
        "artifact": str(Path(task.cwd) / task.artifact) if task.artifact else None,
    }
    write_jsonl(RUNTIME_DIR / "delegate.out", resp)
    stream_event("final", task, {"status": status, "truncated": truncated, "duration_ms": resp["duration_ms"]})


def tail_tasks(in_path: Path, q: queue.Queue[Task]) -> None:
    # simple blocking tail
    with in_path.open("a+", encoding="utf-8") as f:
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.5)
                continue
            task = load_task(line)
            if task:
                q.put(task)


def main() -> None:
    parser = argparse.ArgumentParser(description="Codex delegate runner")
    parser.add_argument("--codex-bin", default=os.environ.get("CODEX_AGENT_BIN", "codex"))
    parser.add_argument("--codex-home", default=os.environ.get("CODEX_AGENT_HOME", str(Path.home() / ".codex-agent")))
    args = parser.parse_args()

    ensure_dirs()
    Path(args.codex_home).mkdir(parents=True, exist_ok=True)

    task_queue: queue.Queue[Task] = queue.Queue()
    cfg = AgentCfg(args.codex_bin, Path(args.codex_home))

    # start tailer
    import threading

    t = threading.Thread(target=tail_tasks, args=(RUNTIME_DIR / "delegate.in", task_queue), daemon=True)
    t.start()

    # main loop
    while True:
        task = task_queue.get()
        try:
            process_task(cfg, task)
        except Exception as exc:  # pragma: no cover - safety net
            err = {"task_id": task.task_id, "status": "error", "error": str(exc), "duration_ms": 0}
            write_jsonl(RUNTIME_DIR / "delegate.out", err)
            stream_event("error", task, {"error": str(exc)})


if __name__ == "__main__":
    # Graceful exit on Ctrl+C
    signal.signal(signal.SIGINT, lambda sig, frame: sys.exit(0))
    main()
