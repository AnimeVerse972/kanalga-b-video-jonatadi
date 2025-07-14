from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from dotenv import load_dotenv
from keep_alive import keep_alive
from database import add_admin_db, init_db
from database import (
    init_db, add_user, get_user_count,
    add_kino_code, get_kino_by_code, get_all_codes,
    delete_kino_code, get_code_stat, increment_stat,
    get_admins, add_admin_db, remove_admin_db,
    get_channels, add_channel_db, remove_channel_db
)
import os
import asyncio

# === YUKLAMALAR ===
load_dotenv()
keep_alive()

API_TOKEN = os.getenv("API_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME")

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

ADMINS = []
SUB_CHANNELS = []

# === HOLATLAR ===
class AdminStates(StatesGroup):
    waiting_for_kino_data = State()
    waiting_for_delete_code = State()
    waiting_for_stat_code = State()

class SettingsState(StatesGroup):
    waiting_for_admin_id = State()
    waiting_for_admin_remove = State()
    waiting_for_channel_add = State()
    waiting_for_channel_remove = State()

# === /start ===
@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    await add_user(message.from_user.id)
    args = message.get_args()
    if args and args.isdigit():
        code = args
        for channel in SUB_CHANNELS:
            try:
                m = await bot.get_chat_member(channel, message.from_user.id)
                if m.status not in ["member", "administrator", "creator"]:
                    raise Exception
            except:
                markup = InlineKeyboardMarkup().add(
                    InlineKeyboardButton("📢 Obuna bo‘lish", url=f"https://t.me/{channel.strip('@')}"),
                    InlineKeyboardButton("✅ Tekshirish", callback_data=f"check_sub:{code}")
                )
                await message.answer("❗ Kino olishdan oldin kanalga obuna bo‘ling:", reply_markup=markup)
                return
        await send_reklama_post(message.from_user.id, code)
        return

    if message.from_user.id in ADMINS:
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("➕ Anime qo‘shish", "📄 Kodlar ro‘yxati")
        kb.add("📊 Statistika", "📈 Kod statistikasi")
        kb.add("❌ Kodni o‘chirish", "⚙️ Sozlamalar")
        await message.answer("👮‍♂️ Admin panel:", reply_markup=kb)
    else:
        await message.answer("🎬 Botga xush kelibsiz!\nKod kiriting:")

# === Obuna tekshirish callback
@dp.callback_query_handler(lambda c: c.data.startswith("check_sub:"))
async def check_sub(callback: types.CallbackQuery):
    code = callback.data.split(":")[1]
    for channel in SUB_CHANNELS:
        try:
            m = await bot.get_chat_member(channel, callback.from_user.id)
            if m.status not in ["member", "administrator", "creator"]:
                raise Exception
        except:
            await callback.answer("❗ Obuna bo‘lmagansiz!", show_alert=True)
            return
    await callback.message.edit_text("✅ Obuna tasdiqlandi!")
    await send_reklama_post(callback.from_user.id, code)

# === Kod yuborilganda
@dp.message_handler(lambda message: message.text.isdigit())
async def handle_code_message(message: types.Message):
    code = message.text
    for channel in SUB_CHANNELS:
        try:
            m = await bot.get_chat_member(channel, message.from_user.id)
            if m.status not in ["member", "administrator", "creator"]:
                raise Exception
        except:
            markup = InlineKeyboardMarkup().add(
                InlineKeyboardButton("📢 Obuna bo‘lish", url=f"https://t.me/{channel.strip('@')}"),
                InlineKeyboardButton("✅ Tekshirish", callback_data=f"check_sub:{code}")
            )
            await message.answer("❗ Kino olishdan oldin kanalga obuna bo‘ling:", reply_markup=markup)
            return
    await increment_stat(code, "init")
    await increment_stat(code, "searched")
    await send_reklama_post(message.from_user.id, code)
    await increment_stat(code, "viewed")

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

# === Admin sozlamalari va kanal boshqaruvi (INLINE QISMI)
# Shu yerga oldin yozilgan "inline keyboard settings" qismini qo‘shing

# === Statistika va kod funksiyalari
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

@dp.message_handler(lambda m: m.text == "➕ Anime qo‘shish")
async def add_start(message: types.Message):
    if message.from_user.id in ADMINS:
        await AdminStates.waiting_for_kino_data.set()
        await message.answer("📝 Format: `KOD @kanal REKLAMA_ID POST_SONI`\nMasalan: `91 @MyKino 4 12`", parse_mode="Markdown")

@dp.message_handler(state=AdminStates.waiting_for_kino_data)
async def add_kino_handler(message: types.Message, state: FSMContext):
    rows = message.text.strip().split("\n")
    successful, failed = 0, 0
    for row in rows:
        parts = row.strip().split()
        if len(parts) != 4 or not all(p.isdigit() if i != 1 else True for i, p in enumerate(parts)):
            failed += 1
            continue
        code, ch, reklama_id, count = parts
        await add_kino_code(code, ch, int(reklama_id) + 1, int(count))
        download_btn = InlineKeyboardMarkup().add(
            InlineKeyboardButton("📥 Yuklab olish", url=f"https://t.me/{BOT_USERNAME}?start={code}")
        )
        try:
            await bot.copy_message(chat_id=ch, from_chat_id=ch, message_id=int(reklama_id), reply_markup=download_btn)
            successful += 1
        except:
            failed += 1
    await message.answer(f"✅ Qo‘shildi: {successful}\n❌ Xatolik: {failed}")
    await state.finish()

@dp.message_handler(lambda m: m.text == "📄 Kodlar ro‘yxati")
async def kodlar(message: types.Message):
    kodlar = await get_all_codes()
    if not kodlar:
        await message.answer("📂 Kodlar yo‘q.")
        return
    text = "📄 Kodlar:\n"
    for row in kodlar:
        text += f"🔹 {row['code']} → {row['channel']} | {row['message_id']} ({row['post_count']} post)\n"
    await message.answer(text)

@dp.message_handler(lambda m: m.text == "📊 Statistika")
async def stats(message: types.Message):
    foydalanuvchilar = await get_user_count()
    kodlar = await get_all_codes()
    await message.answer(f"📦 Kodlar: {len(kodlar)}\n👥 Foydalanuvchilar: {foydalanuvchilar}")

@dp.message_handler(lambda m: m.text == "❌ Kodni o‘chirish")
async def ask_delete_code(message: types.Message):
    if message.from_user.id in ADMINS:
        await AdminStates.waiting_for_delete_code.set()
        await message.answer("🗑 Kodni yuboring:")

@dp.message_handler(state=AdminStates.waiting_for_delete_code)
async def delete_code_handler(message: types.Message, state: FSMContext):
    await state.finish()
    code = message.text.strip()
    deleted = await delete_kino_code(code)
    if deleted:
        await message.answer(f"✅ Kod {code} o‘chirildi.")
    else:
        await message.answer("❌ Kod topilmadi.")

# === START ===
async def on_startup(dp):
    global ADMINS, SUB_CHANNELS
    await init_db()
    ADMINS = await get_admins()
    SUB_CHANNELS = await get_channels()
    print("✅ Bot ishga tushdi!")

# 🔽 BUNI QO‘SHASIZ
import asyncio
from database import add_admin_db, init_db

async def add_myself_as_admin():
    await init_db()
    await add_admin_db(6486825926)  # 👈 bu yerga ID yozing

asyncio.run(add_myself_as_admin())  # 🟢 Bu yerni ishga tushiradi

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
