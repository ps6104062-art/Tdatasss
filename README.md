# 🤖 Менеджер TG аккаунтов

## Установка

```bash
pip install telethon python-telegram-bot
```

## Настройка

Открой `bot.py` и заполни в начале файла:

```python
BOT_TOKEN = "YOUR_BOT_TOKEN"   # Токен от @BotFather
ADMIN_ID = 123456789            # Твой Telegram ID (узнай у @userinfobot)
API_ID = 2040                   # Можно оставить как есть (Telegram Desktop)
API_HASH = "b18441a1ff607e10a989891a5462e627"
```

## Структура папок

```
bot.py
requirements.txt
sessions/          ← сюда кидай .session файлы
  8692729337.session
```

## Запуск

```bash
python bot.py
```

## Использование

1. Кинь `.session` файлы в папку `sessions/` (или отправь файл прямо в бот)
2. Напиши `/start` боту
3. Нажми **📱 Мои аккаунты**
4. Выбери аккаунт → **📨 Получить код**
5. Код придёт автоматически как только Telegram его пришлёт

## Как работает

- Бот подключается к каждому `.session` файлу через Telethon
- Слушает входящие сообщения от Telegram (отправитель 777000)
- Вытаскивает 5-6 значный код через regex
- Мгновенно пересылает тебе с кнопкой "Готово"
