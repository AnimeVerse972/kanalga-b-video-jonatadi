import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from dotenv import load_dotenv
import os

# === YUKLAMALAR ===
load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")
BOT_USERNAME = os.getenv("BOT_USERNAME")

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

ADMINS = [6486825926]  # Admin ID

# === BAZA TAYYORLASH ===
def init_db():
    with sqlite3.connect("kino.db") as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS kino (
                code TEXT PRIMARY KEY,
                channel TEXT,
                message_id INTEGER,
                count INTEGER
            )
        ''')

init_db()

# === DB FUNKSIYALAR ===
def get_kino_by_code(code):
    with sqlite3.connect("kino.db") as conn:
        c = conn.cursor()
        c.execute("SELECT channel, message_id, count FROM kino WHERE code = ?", (code,))
        return c.fetchone()

def add_kino_code(code, channel, message_id, count):
    with sqlite3.connect("kino.db") as conn:
        conn.execute("""
            INSERT OR REPLACE INTO kino (code, channel, message_id, count)
            VALUES (?, ?, ?, ?)
        """, (code, channel, message_id, count))

# === HOLAT ===
class AdminStates(StatesGroup):
    waiting_for_kino_data = State()

# === OBUNA TEKSHIRISH ===
async def is_user_subscribed(user_id):
    try:
        m = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return m.status in ["member", "administrator", "creator"]
    except:
        return False

# === START ===
@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    args = message.get_args()
    if args and args.isdigit():
        code = args
        if not await is_user_subscribed(message.from_user.id):
            markup = InlineKeyboardMarkup().add(
                InlineKeyboardButton("📢 Obuna bo‘lish", url=f"https://t.me/{CHANNEL_USERNAME.strip('@')}"),
                InlineKeyboardButton("✅ Tekshirish", callback_data=f"check_sub:{code}")
            )
            await message.answer("❗ Kino olishdan oldin kanalga obuna bo‘ling:", reply_markup=markup)
        else:
            await send_reklama_post(message.from_user.id, code)
        return
    await message.answer("🎬 Kod yuboring yoki reklama tugmasini bosing.")

@dp.callback_query_handler(lambda c: c.data.startswith("check_sub:"))
async def check_sub(callback: types.CallbackQuery):
    code = callback.data.split(":")[1]
    if await is_user_subscribed(callback.from_user.id):
        await callback.message.edit_text("✅ Obuna tasdiqlandi!")
        await send_reklama_post(callback.from_user.id, code)
    else:
        await callback.answer("❗ Obuna bo‘lmagansiz!", show_alert=True)

# === FILMNI YUBORISH ===
async def send_reklama_post(chat_id, code):
    data = get_kino_by_code(code)
    if not data:
        return await bot.send_message(chat_id, "❌ Kod topilmadi.")

    channel, reklama_id, post_count = data
    await bot.copy_message(chat_id, channel, reklama_id - 1)

    buttons = [InlineKeyboardButton(str(i), callback_data=f"kino:{code}:{i}") for i in range(1, post_count + 1)]
    kb = InlineKeyboardMarkup(row_width=5)
    kb.add(*buttons)

    await bot.send_message(chat_id, "🎬 Qismlarni tanlang:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("kino:"))
async def kino_button(callback: types.CallbackQuery):
    _, code, number = callback.data.split(":")
    number = int(number)

    result = get_kino_by_code(code)
    if not result:
        return await callback.message.answer("❌ Kod topilmadi.")

    channel, base_id, post_count = result

    if number > post_count:
        return await callback.answer("❌ Bunday post yo‘q!", show_alert=True)

    for i in range(number):
        await bot.copy_message(callback.from_user.id, channel, base_id + i)

    await callback.answer()

# === ADMIN KOD QO‘SHISH ===
@dp.message_handler(commands=['add'])
async def cmd_add_start(message: types.Message):
    if message.from_user.id in ADMINS:
        await AdminStates.waiting_for_kino_data.set()
        await message.answer("📝 Format: `KOD @ServerChannel REKLAMA_POST_ID POST_SONI`\nMasalan: `91 @KinoServer 4 12`", parse_mode="Markdown")

@dp.message_handler(state=AdminStates.waiting_for_kino_data)
async def add_kino_handler(message: types.Message, state: FSMContext):
    parts = message.text.strip().split()
    if len(parts) != 4:
        await message.answer("❌ Format noto‘g‘ri!")
        return await state.finish()

    code, server_channel, reklama_id, post_count = parts
    if not (code.isdigit() and reklama_id.isdigit() and post_count.isdigit()):
        await message.answer("❌ Kod, post ID va son raqam bo‘lishi kerak.")
        return await state.finish()

    reklama_id = int(reklama_id)
    post_count = int(post_count)

    add_kino_code(code, server_channel, reklama_id + 1, post_count)

    await bot.copy_message(
        chat_id=CHANNEL_USERNAME,
        from_chat_id=server_channel,
        message_id=reklama_id
    )

    dl_url = f"https://t.me/{BOT_USERNAME.strip('@')}?start={code}"
    dl_kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("📥 Yuklab olish", url=dl_url)
    )

    await bot.send_message(
        chat_id=CHANNEL_USERNAME,
        text="📥 Yuklab olish:",
        reply_markup=dl_kb
    )

    await message.answer("✅ Kod qo‘shildi va reklama kanalga yuborildi!")
    await state.finish()

# === ISHGA TUSHURISH ===
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
