# Codex Delegate Runner (agent) — RU

Очередь + TUI/CLI, позволяющие основному Codex делегировать задачи второму экземпляру Codex («агенту») с отдельным конфигом/токеном. Агент может ходить в интернет, работать в нужной директории и стримить вывод, не засоряя контекст основного Codex.

*English version: see `README.md`*

## Зачем
- Отделить шумные/долгие задачи (ресерч, генерация кода, скрипты) от основной сессии.
- Иметь наглядный монитор (TUI) по нескольким задачам сразу.
- Держать отдельный токен и политику песочницы для агента.

## Как устроено
- CLI `delegate` пишет задания в `runtime/delegate.in` (JSONL).
- `delegate_runner.py` читает очередь, запускает `codex exec --skip-git-repo-check --cd <cwd>` с `CODEX_HOME=~/.codex-agent`, пишет логи в `streams/<task>.log`, события в `runtime/delegate.stream`, финалы в `runtime/delegate.out`.
- `delegate-ui` — curses-UI: слева таблица задач, справа лог выбранной.

## Требования
- Python 3.8+, установленный `codex` CLI (вход в основную учётку выполнен).
- Отдельный конфиг/токен для агента в `~/.codex-agent`.
- `python3-pexpect` (или `pip install -r requirements.txt`).
## Установка (чистая машина, ~5 минут)
1) Зависимости: `sudo apt-get install -y python3-pexpect` (или `pip install -r requirements.txt`).
2) Репозиторий: `git clone https://github.com/pixelGQ/codex-delegate.git ~/codex-delegate`.
3) Токен и конфиг агента:
   ```bash
   mkdir -p ~/.codex-agent
   cp ~/.codex/auth.json ~/.codex-agent/    # или отдельный логин:
   CODEX_HOME=~/.codex-agent codex login
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
4) PATH и алиас:
   ```bash
   echo 'PATH="$HOME/codex-delegate/bin:$PATH"' >> ~/.zshrc
   echo 'alias dlg="delegate-ui"' >> ~/.zshrc
   source ~/.zshrc
   ```
5) Запустить раннер: `delegate --restart`; проверить: `delegate --status` (лог: `/tmp/delegate_runner.log`).
6) Смоук-тест с интернетом: `delegate "кто выиграл евро 2021" --research --live`.

## Использование
- Базово: `delegate "сделай X" [--cwd path] [--timeout 120] [--allow-net|--no-net] [--live] [--json]`
- Режим ресерча: `--research` (авто `--search`, просит 3–5 источников).
- Контекст файлов: `--context f1,f2` (до ~24 KB текста).
- Артефакт: `--artifact path` — сохранить stdout в файл относительно `--cwd`.
- Модель/профиль/песочница: `--model`, `--profile`, `--sandbox`.
- Стримить позже: `delegate --stream <task_id>`.
- Монитор: `delegate-ui` / `dlg` (стрелки для выбора, q — выход).

## Файлы
- `runtime/delegate.in` — входящие задачи (JSONL)
- `runtime/delegate.out` — финальные ответы (JSONL)
- `runtime/delegate.stream` — события (request/stream/final/error)
- `streams/<task>.log` — сырой stdout/stderr
- `delegate_runner.py` — обработчик очереди
- `delegate_tui.py` — TUI-монитор

## Лимиты по умолчанию
- Таймаут 90s; инструкция ~4096 символов; финальный stdout+stderr до 16 KB (дальше усечение с флагом).

## Отладка
- Лог раннера: `/tmp/delegate_runner.log`
- Нет интернета? Проверьте `web_search_request=true` и `network_access=true` в `~/.codex-agent/config.toml`, а также отсутствие `--no-net`.
