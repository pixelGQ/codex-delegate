# Delegate (agent) — полное руководство

## Что это
Делегат — второй экземпляр Codex с отдельным конфигом (`~/.codex-agent`), которому можно отдавать задачи из шелла. Он имеет свой токен и может использовать интернет. Задачи идут в очередь через файлы, ответы стримятся и логируются.

## Быстрая установка (уже проделано)
1) Каталог: `~/codex-delegate/`
2) Токен агента: `cp ~/.codex/auth.json ~/.codex-agent/` (уже сделано)
3) Конфиг агента `~/.codex-agent/config.toml` (отдельно от основного Codex):
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
4) PATH/алиасы: в `~/.zshrc` добавлено `PATH="$HOME/codex-delegate/bin:$PATH"` и алиас `dlg=delegate-ui`.

## Установка на другую машину (пошагово)
1) Установить зависимость: `sudo apt-get install -y python3-pexpect` (или `pip install -r requirements.txt` в каталоге проекта).  
2) Клонировать проект в `~/codex-delegate` (или другой путь, поправив alias/PATH).  
3) Токен: `mkdir -p ~/.codex-agent && cp ~/.codex/auth.json ~/.codex-agent/` **или** `CODEX_HOME=~/.codex-agent codex login`.  
4) Конфиг `~/.codex-agent/config.toml` как в блоке выше; поменяйте `/home/pixel` на свой `$HOME`.  
5) Обновить `~/.zshrc`:  
   ```
   export PATH="$HOME/codex-delegate/bin:$PATH"
   alias dlg="delegate-ui"
   ```  
   затем `source ~/.zshrc`.  
6) Запустить раннер: `delegate --restart`; проверить `delegate --status`.  
7) Проверка: `delegate "скажи погоду в Париже" --research --live` — должно стримить ответ и источники.

## CLI-команды
- `delegate "текст задачи"` — отправить задачу.
- Опции:
  - `--cwd PATH` — рабочая директория задачи.
  - `--timeout N` — таймаут в секундах (по умолчанию 90).
  - `--allow-net` / `--no-net` — включить/выключить web_search (`--allow-net` по умолчанию).
  - `--research` — заставить агента сделать веб-исследование (авто `--search`, промпт: «дай краткое резюме + 3–5 источников»).
  - `--live` — сразу показывать поток событий (request/stream/final).
  - `--json` — вернуть финальный ответ в JSON.
  - `--label TXT` — метка задачи (видна в stream/TUI).
  - `--model NAME` — выбрать модель.
  - `--profile NAME` — профиль из config.
  - `--sandbox MODE` — sandbox-политика для exec.
  - `--artifact PATH` — сохранить stdout задачи в файл (путь относительно `cwd`).
  - `--context f1,f2` — подмешать содержимое файлов в инструкцию (до 24 KB суммарно).
  - `--stream TASK_ID` — tail поток по задаче.
  - `--status` — состояние runner'а.
  - `--restart` — перезапуск runner'а.
- Короткий запуск TUI-монитора: `dlg` (или `delegate-ui`).

## Файлы/структура
- `runtime/delegate.in` — входящие запросы (JSONL).
- `runtime/delegate.out` — финальные ответы (JSONL).
- `runtime/delegate.stream` — события (request/stream/final/error).
- `streams/<task>.log` — сырой лог stdout/stderr задачи.
- `delegate_runner.py` — обработчик очереди, запускает `codex exec`.
- `delegate_tui.py` — curses-монитор (лево: задачи, право: лог выбранной).

## Примеры
```bash
delegate "echo hello"
delegate "Напиши 6 строк стиха про котов-космонавтов" --live
delegate "Найди 3 свежих факта про Artemis" --allow-net --timeout 120 --live
delegate "Напиши fizzbuzz на Python до 30 и выведи результат" --live
```

## Как читать вывод
- При `--live` видно поток: `[request] ...`, `[stdout]/[stderr] ...`, `[final] status=...`.
- Финал всегда в `runtime/delegate.out`; стрим — в `runtime/delegate.stream` и `streams/<task>.log`.
- TUI: `dlg`, стрелками выбрать задачу, q — выход.

## Лимиты и поведение
- Таймаут по умолчанию: 90s.
- Макс размер финального stdout+stderr: 16 KB (усечка с пометкой).
- Шумные строки баннера Codex фильтруются.
- Агент может писать в рабочую директорию (sandbox runner — по умолчанию read-only от Codex, но команды exec — реальные).

## Частые проблемы
- Нет токена у агента: убедиться, что `~/.codex-agent/auth.json` существует (скопировать из `~/.codex/auth.json`).
- Runner не запущен: `delegate --status` (если down — `delegate --restart`).
- Пустой TUI: пока нет новых задач или выбранная задача без вывода.

## Что можно улучшить далее
- Ротация логов (`delegate.out/stream`, `streams/*`).
- Фильтры/поиск в TUI.
- Веб/desktop UI поверх `delegate.stream`.
- Параллельные агенты/пул.
