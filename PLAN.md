# Delegated Codex runner — уточнённый план

## Цель
Ведущий Codex (ты общаешься со мной) отдаёт задачи второму экземпляру Codex (“agent”) с отдельной сессией и интернетом. Я формулирую краткие поручения, слежу за лимитами и собираю результат. В будущем — GUI-мониторинг переписки и статусов.

## Ключевые решения (уточнённые)
- Изоляция: отдельный конфиг/сессия `agent` в каталоге `~/.codex-agent` (отдельный токен/логи), не смешиваем с `~/.codex`.
- Управление: единый runner на `pexpect`, держит `codex --session agent`.
- Транспорт: JSON Lines через файлы (надёжно) + потоковый файл для живого вывода.
- Формат: запрос `task_id,instruction,cwd,timeout_s,context_files?,allow_net?`; ответ `status,summary,stdout,stderr,truncated,duration_ms`.
- Лимиты по умолчанию “как часы”: timeout 90s; инструкция ≤ 4k; совокупный stdout/stderr ≤ 16 KB (усекаем с пометкой).
- Стриминг: runner сразу пишет строки агента в `runtime/streams/<task_id>.log` и события в `runtime/delegate.stream` (JSONL), финальный ответ — в `delegate.out`.
- Безопасность: писать разрешено (агент полноценный исполнитель); секреты не пересылаем; при нужде — отдельный токен в `~/.codex-agent/config.toml`.
- Наблюдаемость: health/status, лог `delegate.log`, файлы `delegate.out` (финал), `delegate.stream` (события).
- UX: CLI helper `delegate` + alias; в будущем GUI/панель над `delegate.stream/delegate.out`.

## Архитектура v1
- `delegate_runner.py`
  - Стартует `codex` из `CODEX_AGENT_BIN` (env) или `codex` в PATH, с `CODEX_HOME=~/.codex-agent`.
  - Слушает `runtime/delegate.in` (JSONL), обрабатывает последовательно.
  - Подаёт задачу агенту, стримит stdout/stderr в `runtime/streams/<task_id>.log` и события в `runtime/delegate.stream`.
  - Финал (усечённый до 16 KB) пишет в `runtime/delegate.out` (JSONL).
  - Таймаут по умолчанию 90s; на истечение — Ctrl+C, статус `timeout`.
  - Автоперезапуск агента при падении; `--status` отдаёт состояние.
- `delegate` (CLI helper)
  - `delegate "сделай X" [--cwd path] [--timeout 120] [--allow-net]`.
  - Ждёт финал по `task_id`, печатает summary + хвост stdout (усечённый), non-zero exit на ошибке/timeout.
  - `delegate --stream TASK` tails поток по конкретной задаче.
  - `delegate --restart`, `delegate --status` управляют runner’ом.
- Файлы:
  - `~/codex-delegate/runtime/delegate.in|out|stream`, `streams/<task>.log`, `delegate.log`.
  - Агентский конфиг: `~/.codex-agent/config.toml` (отдельный путь, не путаться с основным).

## GUI-направление (v2)
- Веб/Tauri монитор поверх `delegate.stream`: лента событий (request/stream/final), статус runner’а, restart, просмотр логов.
- Альтернатива: TUI (fzf/terminal) с live tail и выбором задачи.

## Доп. требования от пользователя
- У агента есть интернет (используем стандартный Codex с сетью).
- Отдельный путь, чтобы не путаться с основным Codex.

## Открытые вопросы (для финализации перед кодом)
- Ок ли лимиты: timeout 60s, stdout/stderr 12k?
- Нужен ли стриминг частичных ответов в v1 или хватит финального?
- Разрешаем ли агенту писать в проект (rw) или по умолчанию read-only? (могу сделать флаг `--readonly` и cwd-копию).
- Где лежит бинарь Codex с интернетом? (если нестандартный путь — зададим `CODEX_AGENT_BIN`).

## Next steps (после подтверждения)
1) Скелет `delegate_runner.py` + `runtime/` структура.
2) CLI `delegate` (bash/zsh).
3) README с примерами и схемой.
4) Smoke-тест с локальной задачей (без сети, если недоступно).
