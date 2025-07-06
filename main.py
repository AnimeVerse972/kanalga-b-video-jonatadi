from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from dotenv import load_dotenv
from keep_alive import keep_alive
from database import (
    init_db, add_user, get_user_count, add_kino_code, get_kino_by_code,
    get_all_codes, db_pool, delete_kino_code, increment_stat,
    add_required_channel, get_required_channels
)
import os

load_dotenv()
keep_alive()

API_TOKEN = os.getenv("API_TOKEN")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")  # faqat 1 kanal uchun eski tizimda kerak bo‘lgan
BOT_USERNAME = os.getenv("BOT_USERNAME")

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

ADMINS = [6486825926]

class AdminStates(StatesGroup):
    waiting_for_kino_data = State()
    waiting_for_delete_code = State()
    waiting_for_channel_name = State()
    waiting_for_feedback = State()

# === Majburiy obunani tekshiruvchi ===
async def is_user_subscribed(user_id):
    try:
        channels = await get_required_channels()
        for ch in channels:
            m = await bot.get_chat_member(ch['channel'], user_id)
            if m.status not in ["member", "administrator", "creator"]:
                return False
        return True
    except:
        return False

# === /start ===
@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    await add_user(message.from_user.id)
    args = message.get_args()

    if args and args.isdigit():
        code = args
        if not await is_user_subscribed(message.from_user.id):
            markup = InlineKeyboardMarkup()
            for ch in await get_required_channels():
                markup.add(InlineKeyboardButton("📢 Obuna bo‘lish", url=f"https://t.me/{ch['channel'].strip('@')}"))
            markup.add(InlineKeyboardButton("✅ Tekshirish", callback_data=f"check_sub:{code}"))
            await message.answer("❗ Anime olishdan oldin quyidagi kanallarga obuna bo‘ling:", reply_markup=markup)
        else:
            await send_reklama_post(message.from_user.id, code)
        return

    if message.from_user.id in ADMINS:
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("➕ Anime qo‘shish", "📄 Kodlar ro‘yxati")
        kb.add("📊 Statistika", "❌ Kodni o‘chirish")
        kb.add("➕ Kanal qo‘shish", "❌ Bekor qilish")
        await message.answer("👮‍♂️ Admin panel:", reply_markup=kb)
    else:
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("✉️ Fikr bildirish")
        await message.answer("🎬 Anime olish uchun kod kiriting:", reply_markup=kb)

# === Kodni qabul qilish ===
@dp.message_handler(lambda message: message.text.isdigit())
async def handle_code_message(message: types.Message):
    code = message.text
    await increment_stat(code, "searched")
    if not await is_user_subscribed(message.from_user.id):
        markup = InlineKeyboardMarkup()
        for ch in await get_required_channels():
            markup.add(InlineKeyboardButton("📢 Obuna bo‘lish", url=f"https://t.me/{ch['channel'].strip('@')}"))
        markup.add(InlineKeyboardButton("✅ Tekshirish", callback_data=f"check_sub:{code}"))
        await message.answer("❗ Anime olishdan oldin quyidagi kanallarga obuna bo‘ling:", reply_markup=markup)
    else:
        await send_reklama_post(message.from_user.id, code)

@dp.callback_query_handler(lambda c: c.data.startswith("check_sub:"))
async def check_sub(callback: types.CallbackQuery):
    code = callback.data.split(":")[1]
    if await is_user_subscribed(callback.from_user.id):
        await callback.message.edit_text("✅ Obuna tasdiqlandi!")
        await send_reklama_post(callback.from_user.id, code)
    else:
        await callback.answer("❗ Obuna bo‘lmagansiz!", show_alert=True)

# === Reklama postni yuborish ===
async def send_reklama_post(user_id, code):
    data = await get_kino_by_code(code)
    if not data:
        await bot.send_message(user_id, "❌ Kod topilmadi.")
        return

    channel, reklama_id, post_count = data["channel"], data["message_id"], data["post_count"]
    buttons = [InlineKeyboardButton(str(i), callback_data=f"kino:{code}:{i}") for i in range(1, post_count + 1)]
    keyboard = InlineKeyboardMarkup(row_width=5)
    keyboard.add(*buttons)

    try:
        await bot.copy_message(user_id, channel, reklama_id - 1, reply_markup=keyboard)
    except:
        await bot.send_message(user_id, "❌ Reklama postni yuborib bo‘lmadi.")

# === Qismni yuborish ===
@dp.callback_query_handler(lambda c: c.data.startswith("kino:"))
async def kino_button(callback: types.CallbackQuery):
    _, code, number = callback.data.split(":")
    number = int(number)
    result = await get_kino_by_code(code)
    if not result:
        await callback.message.answer("❌ Kod topilmadi.")
        return

    await increment_stat(code, "loaded")

    channel, base_id, post_count = result["channel"], result["message_id"], result["post_count"]
    if number > post_count:
        await callback.answer("❌ Bunday post yo‘q!", show_alert=True)
        return

    await bot.copy_message(callback.from_user.id, channel, base_id + number - 1)
    await callback.answer()

# === Kod qo‘shish ===
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
        await add_kino_code(code, server_channel, reklama_id + 1, post_count)

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

# === Kodlar ro‘yxati ===
@dp.message_handler(lambda m: m.text == "📄 Kodlar ro‘yxati")
async def kodlar(message: types.Message):
    kodlar = await get_all_codes()
    if not kodlar:
        await message.answer("📂 Kodlar yo‘q.")
        return
    text = "📄 Kodlar:\n"
    for row in kodlar:
        code, ch, msg_id, count = row["code"], row["channel"], row["message_id"], row["post_count"]
        text += f"🔹 {code} → {ch} | {msg_id} ({count} post)\n"
    await message.answer(text)

# === Statistika ===
@dp.message_handler(lambda m: m.text == "📊 Statistika")
async def stats(message: types.Message):
    if message.from_user.id not in ADMINS:
        return
    kodlar = await get_all_codes()
    foydalanuvchilar = await get_user_count()
    text = f"📦 Kodlar: {len(kodlar)}\n👥 Foydalanuvchilar: {foydalanuvchilar}\n\n📊 Kodlar statistikasi:\n"
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT code, searched, loaded FROM stats")
        for row in rows:
            text += f"🔹 {row['code']} → 🔍 {row['searched']} ta qidiruv | 📥 {row['loaded']} yuklash\n"
    await message.answer(text)

# === Kodni o‘chirish ===
@dp.message_handler(lambda m: m.text == "❌ Kodni o‘chirish")
async def ask_delete_code(message: types.Message):
    if message.from_user.id in ADMINS:
        await AdminStates.waiting_for_delete_code.set()
        await message.answer("🗑 Qaysi kodni o‘chirmoqchisiz? Kodni yuboring.")

@dp.message_handler(state=AdminStates.waiting_for_delete_code)
async def delete_code_handler(message: types.Message, state: FSMContext):
    await state.finish()
    code = message.text.strip()
    if not code.isdigit():
        await message.answer("❗ Noto‘g‘ri format. Kod raqamini yuboring.")
        return
    deleted = await delete_kino_code(code)
    if deleted:
        await message.answer(f"✅ Kod {code} o‘chirildi.")
    else:
        await message.answer("❌ Kod topilmadi yoki o‘chirib bo‘lmadi.")

# === Kanal qo‘shish ===
@dp.message_handler(lambda m: m.text == "➕ Kanal qo‘shish")
async def ask_channel_name(message: types.Message):
    if message.from_user.id in ADMINS:
        await AdminStates.waiting_for_channel_name.set()
        await message.answer("📢 Kanal username’ini yuboring (masalan: @mychannel)")

@dp.message_handler(state=AdminStates.waiting_for_channel_name)
async def save_channel_name(message: types.Message, state: FSMContext):
    channel = message.text.strip()
    if not channel.startswith("@"):
        await message.answer("❗ To‘g‘ri formatda yuboring, masalan: @mychannel")
        return
    await add_required_channel(channel)
    await message.answer(f"✅ {channel} kanal majburiy obunaga qo‘shildi")
    await state.finish()

# === Fikr bildirish ===
@dp.message_handler(lambda m: m.text == "✉️ Fikr bildirish")
async def start_feedback(message: types.Message):
    await AdminStates.waiting_for_feedback.set()
    await message.answer("✍️ Fikr yoki savolingizni yozing. Adminlar ko‘radi.")

@dp.message_handler(state=AdminStates.waiting_for_feedback, content_types=types.ContentType.ANY)
async def handle_feedback(message: types.Message, state: FSMContext):
    await state.finish()
    for admin_id in ADMINS:
        try:
            await bot.copy_message(chat_id=admin_id, from_chat_id=message.chat.id, message_id=message.message_id)
            await bot.send_message(chat_id=admin_id, text=f"✉️ Yuqoridagi xabar {message.from_user.id} dan keldi. Javob yozish uchun shu xabarga reply qiling.")
        except:
            pass

@dp.message_handler(lambda m: m.reply_to_message and "dan keldi" in m.reply_to_message.text, content_types=types.ContentType.ANY)
async def reply_to_feedback(message: types.Message):
    try:
        lines = message.reply_to_message.text.strip().split()
        user_id = int(lines[-3])
        await bot.copy_message(chat_id=user_id, from_chat_id=message.chat.id, message_id=message.message_id)
        await message.answer("✅ Xabar foydalanuvchiga yuborildi.")
    except Exception as e:
        await message.answer("❌ Xatolik yuz berdi: " + str(e))

# === Bekor qilish ===
@dp.message_handler(lambda m: m.text == "❌ Bekor qilish", state="*")
async def cancel(message: types.Message, state: FSMContext):
    await state.finish()
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Anime qo‘shish", "📄 Kodlar ro‘yxati")
    kb.add("📊 Statistika", "❌ Kodni o‘chirish")
    kb.add("➕ Kanal qo‘shish", "❌ Bekor qilish")
    await message.answer("❌ Bekor qilindi", reply_markup=kb)

# === Botni ishga tushurish ===
async def on_startup(dp):
    await init_db()
    print("✅ PostgreSQL bazaga ulandi!")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
