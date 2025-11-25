# Codex delegate (agent) runner

English version: see `README.en.md`

Ведущий Codex делегирует задачи второму экземпляру Codex с отдельной сессией/конфигом и (по желанию) доступом в интернет.

## Ключевые идеи
- Отдельный конфиг/сессия агента: `~/.codex-agent` (чтобы не путаться с основным `~/.codex`).
- Runner создаёт для каждой задачи отдельный вызов `codex exec --skip-git-repo-check --cd <cwd>` (без постоянного PTY), принимает задачи в JSON, стримит вывод и отдаёт финальный ответ.
- Транспорт: JSON Lines файлы в `runtime/`.
- Стриминг: события пишутся в `runtime/delegate.stream`, отдельные логи по задачам — в `streams/<task_id>.log`.
- Финальные ответы — в `runtime/delegate.out`.

## Быстрый старт (после установки)
- Отправить задачу: `delegate "сделай X" [--cwd path] [--timeout 120] [--allow-net] [--live] [--json]`
- Live-вывод: `delegate "..." --live` (события `request/stream/final` прямо в терминал)
- Смотреть поток позже: `delegate --stream <task_id>`
- Перезапуск runner'а: `delegate --restart`
- Проверить статус: `delegate --status`
- TUI-монитор: `python3 delegate_tui.py` (лево — задачи, право — лог выбранной задачи, q — выход)

## Полная установка на новую машину (5 минут)
1) Зависимости: `sudo apt-get install -y python3-pexpect` (или `pip install -r requirements.txt`).
2) Код: поместите проект в `~/codex-delegate` (например, `git clone <repo> ~/codex-delegate`).
3) Токен агента: `mkdir -p ~/.codex-agent && cp ~/.codex/auth.json ~/.codex-agent/`  
   (или `CODEX_HOME=~/.codex-agent codex login` — отдельный логин).
4) Конфиг агента `~/.codex-agent/config.toml`:
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
5) PATH/алиасы:  
   `echo 'PATH="$HOME/codex-delegate/bin:$PATH"' >> ~/.zshrc`  
   `echo 'alias dlg="delegate-ui"' >> ~/.zshrc`  
   затем `source ~/.zshrc`.
6) Запустить раннер: `delegate --restart`, проверить `delegate --status`. Логи — `/tmp/delegate_runner.log`.
7) Smoke-тест сети: `delegate "кто выиграл евро 2021" --research --live`.

## Файлы и директории
- `runtime/delegate.in`   — входящие запросы (JSONL).
- `runtime/delegate.out`  — финальные ответы (JSONL).
- `runtime/delegate.stream` — поток событий (JSONL, типы: request|stream|final|error).
- `streams/<task_id>.log` — сырой stdout/stderr задачи.
- `runtime/delegate.log`  — лог runner'а.
- Конфиг агента: `~/.codex-agent/config.toml` (опционально отдельный токен или сетевой профиль).

## Протокол (v1)
Запрос (JSON, одна строка):
```
{
  "task_id": "uuid",
  "instruction": "что сделать",
  "cwd": "/path",
  "timeout_s": 90,
  "allow_net": true,
  "context_files": []
}
```

Ответ:
```
{
  "task_id": "uuid",
  "status": "ok|timeout|error",
  "summary": "кратко",
  "stdout": "...(усечено)",
  "stderr": "...(усечено)",
  "truncated": true/false,
  "duration_ms": 1234
}
```

## Лимиты (по умолчанию)
- timeout: 90s
- макс длина инструкции: 4096 символов
- вывод stdout+stderr в финале: 16 KB (усечка с пометкой)

## Основные флаги `delegate`
- `--allow-net` / `--no-net` — включить/выключить web_search (по умолчанию включено).
- `--research` — быстрый режим «перепроверить в интернете»: авто `--search`, в промпте просит краткое резюме + 3–5 источников.
- `--context f1,f2` — подмешать содержимое файлов (до ~24 KB).
- `--artifact path` — сохранить stdout в файл относительно `--cwd`.
- `--live` — стрим событий в реальном времени.
- `--json` — вернуть финал одной строкой JSON.

## Аутентификация агента
- Runner использует `CODEX_HOME=~/.codex-agent`. Чтобы агент работал без повторного логина, скопируйте токен:
  ```
  mkdir -p ~/.codex-agent
  cp ~/.codex/auth.json ~/.codex-agent/
  ```
  или залогиньтесь отдельно: `CODEX_HOME=~/.codex-agent codex login`.

## Отладка
- Runner лог: `/tmp/delegate_runner.log`
- Поток событий: `runtime/delegate.stream`
- Сырой лог задачи: `streams/<task_id>.log`
- Если нет сети в ответе — проверьте `~/.codex-agent/config.toml` (`web_search_request=true`, `network_access=true`) и что флаг `--no-net` не указан.
