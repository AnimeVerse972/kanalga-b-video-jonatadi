from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from dotenv import load_dotenv
from database import *  # <- SQLite funksiyalar
from keep_alive import keep_alive
import os

# === YUKLAMALAR ===
load_dotenv()
keep_alive()

API_TOKEN = os.getenv("API_TOKEN")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")
BOT_USERNAME = os.getenv("BOT_USERNAME")

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

ADMINS = [6486825926]

# === HOLATLAR ===
class AdminStates(StatesGroup):
    waiting_for_kino_data = State()
    waiting_for_remove_code = State()
    waiting_for_post_count = State()

# === OBUNA TEKSHIRISH ===
async def is_user_subscribed(user_id):
    try:
        m = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return m.status in ["member", "administrator", "creator"]
    except:
        return False

# === /start ===
@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    add_user(message.from_user.id)

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
            await send_kino_by_code(message.from_user.id, code)
        return

    if message.from_user.id in ADMINS:
        admin_kb = ReplyKeyboardMarkup(resize_keyboard=True)
        admin_kb.add("➕ Anime qo‘shish", "❌ Kodni o‘chirish")
        admin_kb.add("📄 Kodlar ro‘yxati", "📊 Statistika")
        admin_kb.add("❌ Bekor qilish")
        await message.answer("👮‍♂️ Admin panel:", reply_markup=admin_kb)
    else:
        user_kb = ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("🎬 Kino kodi yuborish"))
        await message.answer("🎬 Botga xush kelibsiz!\nAnimeni ko'rish uchun kod yuboring.", reply_markup=user_kb)

@dp.callback_query_handler(lambda c: c.data.startswith("check_sub:"))
async def check_sub(callback: types.CallbackQuery):
    code = callback.data.split(":", 1)[1]
    if await is_user_subscribed(callback.from_user.id):
        await callback.message.edit_text("✅ Obuna tasdiqlandi, anime yuborilmoqda...")
        await send_kino_by_code(callback.from_user.id, code)
    else:
        await callback.answer("❗ Hali obuna bo'lmagansiz!", show_alert=True)

# === KINO YUBORISH ===
async def send_kino_by_code(chat_id, code, post_count=1):
    result = get_kino_by_code(code)
    if result:
        channel, message_id = result
        await bot.copy_message(chat_id, channel, message_id)
        for i in range(1, post_count):
            await bot.copy_message(chat_id, channel, message_id + i)
    else:
        await bot.send_message(chat_id, "❌ Bunday kod topilmadi.")

# === ➕ Kino qo‘shish ===
@dp.message_handler(lambda m: m.text == "➕ Anime qo‘shish")
async def cmd_add_start(message: types.Message):
    if message.from_user.id in ADMINS:
        await AdminStates.waiting_for_kino_data.set()
        await message.answer("📝 Format: `KOD @Kanal 4`\nMasalan: `91 @MyChannel 4`", parse_mode="Markdown")

@dp.message_handler(state=AdminStates.waiting_for_kino_data)
async def add_kino_handler(message: types.Message, state: FSMContext):
    parts = message.text.strip().split()
    if len(parts) == 3 and parts[0].isdigit() and parts[2].isdigit():
        code, channel, rekl_id = parts
        add_kino_code(code, channel, int(rekl_id) + 1)

        url = f"https://t.me/{BOT_USERNAME.strip('@')}?start={code}"
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("📥 Yuklab olish", callback_data=f"download:{code}"))
        await bot.send_message(channel, message.text, reply_markup=kb, parse_mode="Markdown")
        await message.answer("✅ Anime qo‘shildi va reklama post yuborildi!")
    else:
        await message.answer("❌ Noto‘g‘ri format!\nMasalan: `91 @Kanal 4`", parse_mode="Markdown")
    await state.finish()

# === 📥 Yuklab olish ===
@dp.callback_query_handler(lambda c: c.data.startswith("download:"))
async def ask_post_count(callback: types.CallbackQuery, state: FSMContext):
    code = callback.data.split(":", 1)[1]
    await state.update_data(code=code)
    await AdminStates.waiting_for_post_count.set()
    await callback.message.answer("📥 Nechta post yuborilsin? (1 dan 10 gacha son kiriting):")

@dp.message_handler(state=AdminStates.waiting_for_post_count)
async def post_count_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()
    code = data.get("code")
    post_count = message.text.strip()

    if post_count.isdigit() and 1 <= int(post_count) <= 10:
        await send_kino_by_code(message.from_user.id, code, int(post_count))
        await message.answer(f"✅ {post_count} ta post yuborildi.")
    else:
        await message.answer("❌ Iltimos, 1 dan 10 gacha son kiriting.")
    await state.finish()

# === ❌ Kodni o‘chirish ===
@dp.message_handler(lambda m: m.text == "❌ Kodni o‘chirish")
async def cmd_remove_start(message: types.Message):
    if message.from_user.id in ADMINS:
        await AdminStates.waiting_for_remove_code.set()
        await message.answer("🗑 O‘chirmoqchi bo‘lgan kodni yozing:")

@dp.message_handler(state=AdminStates.waiting_for_remove_code)
async def remove_kino_handler(message: types.Message, state: FSMContext):
    code = message.text.strip()
    if get_kino_by_code(code):
        remove_kino_code(code)
        await message.answer(f"✅ Kod {code} o‘chirildi.")
    else:
        await message.answer("❌ Bunday kod topilmadi.")
    await state.finish()

# === 📄 Kodlar ro‘yxati ===
@dp.message_handler(lambda m: m.text == "📄 Kodlar ro‘yxati")
async def list_kodlar(message: types.Message):
    kino = get_all_codes()
    if not kino:
        return await message.answer("📂 Hech qanday kod yo‘q.")
    txt = "📄 Kodlar ro‘yxati:\n"
    for code, channel, msg_id in kino:
        txt += f"🔹 {code} → kanal {channel} | kino_post={msg_id}\n"
    await message.answer(txt)

# === 📊 Statistika ===
@dp.message_handler(lambda m: m.text == "📊 Statistika")
async def stats(message: types.Message):
    await message.answer(f"📦 Kodlar: {len(get_all_codes())}\n👥 Foydalanuvchilar: {get_user_count()}")

# === ❌ Bekor qilish ===
@dp.message_handler(lambda m: m.text == "❌ Bekor qilish", state='*')
async def cancel_handler(message: types.Message, state: FSMContext):
    await state.finish()
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Anime qo‘shish", "❌ Kodni o‘chirish")
    kb.add("📄 Kodlar ro‘yxati", "📊 Statistika")
    kb.add("❌ Bekor qilish")
    await message.answer("❌ Amal bekor qilindi.", reply_markup=kb)

# === ISHGA TUSHURISH ===
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
