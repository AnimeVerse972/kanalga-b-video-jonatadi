from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from dotenv import load_dotenv
from keep_alive import keep_alive
from database import init_db, add_user, get_user_count, add_kino_code, get_kino_by_code, get_all_codes, delete_kino_code, get_code_stat, increment_stat
import os

# === YUKLAMALAR ===
load_dotenv()
keep_alive()

API_TOKEN = os.getenv("API_TOKEN")
CHANNEL_USERNAMES = os.getenv("CHANNEL_USERNAME").split(",")
BOT_USERNAME = os.getenv("BOT_USERNAME")

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

ADMINS = [6486825926,8017776953]

# === HOLATLAR ===
class AdminStates(StatesGroup):
    waiting_for_kino_data = State()
    waiting_for_delete_code = State()
    waiting_for_stat_code = State()

# === OBUNA TEKSHIRISH ===
async def is_user_subscribed(user_id):
    try:
        for channel_username in CHANNEL_USERNAMES:
            m = await bot.get_chat_member(channel_username.strip(), user_id)
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
        kb.add("📊 Statistika", "📈 Kod statistikasi")
        kb.add("❌ Kodni o‘chirish", "❌ Bekor qilish")
        await message.answer("👮‍♂️ Admin panel:", reply_markup=kb)
    else:
        await message.answer("🎬 Botga xush kelibsiz!\nKod kiriting:")

# === Kod statistikasi tugmasi ===
@dp.message_handler(lambda m: m.text == "📈 Kod statistikasi")
async def ask_stat_code(message: types.Message):
    if message.from_user.id not in ADMINS:
        return
    await message.answer("📥 Kod raqamini yuboring:")
    await AdminStates.waiting_for_stat_code.set()

@dp.message_handler(state=AdminStates.waiting_for_stat_code)
async def show_code_stat(message: types.Message, state: FSMContext):
    await state.finish()
    code = message.text.strip()
    if not code:
        await message.answer("❗ Kod yuboring.")
        return
    stat = await get_code_stat(code)
    if not stat:
        await message.answer("❗ Bunday kod statistikasi topilmadi.")
        return

    await message.answer(
        f"📊 <b>{code} statistikasi:</b>\n"
        f"🔍 Qidirilgan: <b>{stat['searched']}</b>\n"
        f"👁 Ko‘rilgan: <b>{stat['viewed']}</b>",
        parse_mode="HTML"
    )

# === Oddiy raqam yuborilganda
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
        await increment_stat(code, "init")
        await increment_stat(code, "searched")
        await send_reklama_post(message.from_user.id, code)
        await increment_stat(code, "viewed")

# Statistikani oddiy foydalanuvchiga ko‘rsatish qismi olib tashlandi

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

# === Tugma orqali kino post yuborish
@dp.callback_query_handler(lambda c: c.data.startswith("kino:"))
async def kino_button(callback: types.CallbackQuery):
    _, code, number = callback.data.split(":")
    number = int(number)

    result = await get_kino_by_code(code)
    if not result:
        await callback.message.answer("❌ Kod topilmadi.")
        return

    channel, base_id, post_count = result["channel"], result["message_id"], result["post_count"]

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

# === Kodlar ro‘yxati
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

# === Statistika
@dp.message_handler(lambda m: m.text == "📊 Statistika")
async def stats(message: types.Message):
    kodlar = await get_all_codes()
    foydalanuvchilar = await get_user_count()
    await message.answer(f"📦 Kodlar: {len(kodlar)}\n👥 Foydalanuvchilar: {foydalanuvchilar}")

# === ❌ Kodni o‘chirish
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

# === Bekor qilish
@dp.message_handler(lambda m: m.text == "❌ Bekor qilish", state="*")
async def cancel(message: types.Message, state: FSMContext):
    await state.finish()
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Anime qo‘shish", "📄 Kodlar ro‘yxati")
    kb.add("📊 Statistika", "📈 Kod statistikasi")
    kb.add("❌ Kodni o‘chirish", "❌ Bekor qilish")
    await message.answer("❌ Bekor qilindi", reply_markup=kb)

# === START ===
async def on_startup(dp):
    await init_db()
    print("✅ PostgreSQL bazaga ulandi!")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
