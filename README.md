# tg-claude

Telegram-бот, который выполняет задачи на этой машине через Claude Agent SDK.

## Установка

1. `uv sync`
2. `cp config.example.toml config.toml` и заполнить:
   - `bot_token` — от @BotFather
   - `allowed_user_id` — твой Telegram user_id (узнать у @userinfobot)
   - `chat_id` — id супергруппы с включёнными topics
   - `default_cwd` — каталог по умолчанию
3. `chmod 600 config.toml`

## Запуск

Вручную: `uv run python -m tgclaude.bot`

Автозапуск. Сначала подставь в `launchd/com.nvinnikov.tg-claude.plist` свои пути
вместо `/Users/YOUR_USERNAME/tg-claude` (`WorkingDirectory` и пути логов), при
необходимости поправь путь к `uv` (`which uv`). Затем:

```bash
ln -sf "$PWD/launchd/com.nvinnikov.tg-claude.plist" ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.nvinnikov.tg-claude.plist
```

Остановить: `launchctl unload ~/Library/LaunchAgents/com.nvinnikov.tg-claude.plist`

## Использование

Каждый topic супергруппы — отдельная сессия со своим `cwd` и контекстом.

| Команда | Действие |
|---|---|
| `/new` | Сбросить сессию в текущем topic |
| `/cd <путь>` | Сменить рабочий каталог |
| `/pwd` | Показать `cwd` и id сессии |
| `/stop` | Прервать текущий прогон |
| `/status` | Состояние всех сессий |

Любое другое сообщение — задача для агента.

## Права

`rules.toml` задаёт два списка регулярных выражений:

- `deny` — запрещено всегда, кнопкой не обходится;
- `allow` — выполняется без подтверждения.

Всё остальное присылает в чат кнопки «Разрешить» / «Запретить». Без ответа
в течение `approval_timeout_s` секунд вызов отклоняется.

**Ограничение:** агент работает под твоим пользователем и видит все токены в `~`.
Изоляции нет — это осознанный размен на доступ к рабочей машине.

## Тесты

`uv run pytest`
