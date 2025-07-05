from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from dotenv import load_dotenv
from keep_alive import keep_alive
from database import *
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
            await send_reklama_post(message.from_user.id, code)
        return

    if message.from_user.id in ADMINS:
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("➕ Anime qo‘shish", "📄 Kodlar ro‘yxati")
        kb.add("📊 Statistika", "❌ Bekor qilish")
        await message.answer("👮‍♂️ Admin panel:", reply_markup=kb)
    else:
        await message.answer("🎬 Botga xush kelibsiz!\nKod kiriting:")

# === Oddiy raqam yuborilganda (masalan: "57")
@dp.message_handler(lambda message: message.text.isdigit())
async def handle_code_message(message: types.Message):
    code = message.text
    if not await is_user_subscribed(message.from_user.id):
        markup = InlineKeyboardMarkup().add(
            InlineKeyboardButton("📢 Obuna bo‘lish", url=f"https://t.me/{CHANNEL_USERNAME.strip('@')}"),
            InlineKeyboardButton("✅ Tekshirish", callback_data=f"check_sub:{code}")
        )
        await message.answer("❗ Kino olishdan oldin kanalga obuna bo‘ling:", reply_markup=markup)
    else:
        await send_reklama_post(message.from_user.id, code)

# === Obuna tekshirish callback
@dp.callback_query_handler(lambda c: c.data.startswith("check_sub:"))
async def check_sub(callback: types.CallbackQuery):
    code = callback.data.split(":")[1]
    if await is_user_subscribed(callback.from_user.id):
        await callback.message.edit_text("✅ Obuna tasdiqlandi!")
        await send_reklama_post(callback.from_user.id, code)
    else:
        await callback.answer("❗ Obuna bo‘lmagansiz!", show_alert=True)

# === Reklama postni yuborish
async def send_reklama_post(user_id, code):
    data = get_kino_by_code(code)
    if not data:
        await bot.send_message(user_id, "❌ Kod topilmadi.")
        return

    channel, reklama_id, post_count = data

    # Tugmalarni yasash
    buttons = [InlineKeyboardButton(str(i), callback_data=f"kino:{code}:{i}") for i in range(1, post_count + 1)]
    keyboard = InlineKeyboardMarkup(row_width=5)
    keyboard.add(*buttons)

    try:
        await bot.copy_message(user_id, channel, reklama_id - 1, reply_markup=keyboard)
    except:
        await bot.send_message(user_id, "❌ Reklama postni yuborib bo‘lmadi.")

# === Tugmani bosganda kino post yuborish
@dp.callback_query_handler(lambda c: c.data.startswith("kino:"))
async def kino_button(callback: types.CallbackQuery):
    _, code, number = callback.data.split(":")
    number = int(number)

    result = get_kino_by_code(code)
    if not result:
        await callback.message.answer("❌ Kod topilmadi.")
        return

    channel, base_id, post_count = result

    if number > post_count:
        await callback.answer("❌ Bunday post yo‘q!", show_alert=True)
        return

    await bot.copy_message(callback.from_user.id, channel, base_id + number - 1)
    await callback.answer()

# === ➕ Anime qo‘shish
@dp.message_handler(lambda m: m.text == "➕ Anime qo‘shish")
async def add_start(message: types.Message):
    if message.from_user.id in ADMINS:
        await AdminStates.waiting_for_kino_data.set()
        await message.answer("📝 Format: `KOD @kanal REKLAMA_ID POST_SONI`\nMasalan: `91 @MyKino 4 12`", parse_mode="Markdown")

@dp.message_handler(state=AdminStates.waiting_for_kino_data)
async def add_kino_handler(message: types.Message, state: FSMContext):
    rows = message.text.strip().split("\n")
    successful = 0
    failed = 0
    for row in rows:
        parts = row.strip().split()
        if len(parts) != 4:
            failed += 1
            continue

        code, server_channel, reklama_id, post_count = parts
        if not (code.isdigit() and reklama_id.isdigit() and post_count.isdigit()):
            failed += 1
            continue

        reklama_id = int(reklama_id)
        post_count = int(post_count)
        add_kino_code(code, server_channel, reklama_id + 1, post_count)

        # Yuklab olish tugmasi
        download_btn = InlineKeyboardMarkup().add(
            InlineKeyboardButton("📥 Yuklab olish", url=f"https://t.me/{BOT_USERNAME}?start={code}")
        )

        try:
            await bot.copy_message(
                chat_id=CHANNEL_USERNAME,
                from_chat_id=server_channel,
                message_id=reklama_id,
                reply_markup=download_btn
            )
            successful += 1
        except:
            failed += 1

    await message.answer(f"✅ Yangi kodlar qo‘shildi:\n\n✅ Muvaffaqiyatli: {successful}\n❌ Xatolik: {failed}")
    await state.finish()
    
# === Kodlar ro‘yxati
@dp.message_handler(lambda m: m.text == "📄 Kodlar ro‘yxati")
async def kodlar(message: types.Message):
    kodlar = get_all_codes()
    if not kodlar:
        await message.answer("📂 Kodlar yo‘q.")
        return
    text = "📄 Kodlar:\n"
    for code, ch, msg_id, count in kodlar:
        text += f"🔹 {code} → {ch} | {msg_id} ({count} post)\n"
    await message.answer(text)

# === Statistika
@dp.message_handler(lambda m: m.text == "📊 Statistika")
async def stats(message: types.Message):
    await message.answer(f"📦 Kodlar: {len(get_all_codes())}\n👥 Foydalanuvchilar: {get_user_count()}")

# === Bekor qilish
@dp.message_handler(lambda m: m.text == "❌ Bekor qilish", state="*")
async def cancel(message: types.Message, state: FSMContext):
    await state.finish()
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Anime qo‘shish", "📄 Kodlar ro‘yxati")
    kb.add("📊 Statistika", "❌ Bekor qilish")
    await message.answer("❌ Bekor qilindi", reply_markup=kb)

# === BOT START
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
