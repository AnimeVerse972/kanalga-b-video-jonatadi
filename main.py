from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from dotenv import load_dotenv
import os
import json

# === YUKLAMALAR ===
load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")
BOT_USERNAME = os.getenv("BOT_USERNAME")

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

ADMINS = [6486825926]

# === FAYL FUNKSIYALARI ===
def load_codes():
    if not os.path.exists("kino_posts.json"):
        with open("kino_posts.json", "w") as f:
            json.dump({}, f)
    with open("kino_posts.json", "r") as f:
        return json.load(f)

def save_codes(data):
    with open("kino_posts.json", "w") as f:
        json.dump(data, f, indent=4)

def load_users():
    if not os.path.exists("users.json"):
        with open("users.json", "w") as f:
            json.dump([], f)
    with open("users.json", "r") as f:
        return json.load(f)

def save_users(data):
    with open("users.json", "w") as f:
        json.dump(data, f, indent=4)

# === HOLATLAR ===
class AdminStates(StatesGroup):
    waiting_for_kino_data = State()
    waiting_for_remove_code = State()
    waiting_for_post_count = State()  # Yangi holat post sonini belgilash uchun

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
    # foydalanuvchini saqlaymiz
    users = load_users()
    if message.from_user.id not in users:
        users.append(message.from_user.id)
        save_users(users)

    args = message.get_args()
    # agar start bilan kod kelgan bo‘lsa
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

    # oddiy /start: admin yoki foydalanuvchi
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
    data = load_codes().get(code)
    if data:
        channel = data["channel"]
        message_id = data["message_id"]
        
        # Birinchi postni yuborish
        await bot.copy_message(chat_id, channel, message_id)
        
        # Keyingi postlarni yuborish
        for i in range(1, post_count):
            await bot.copy_message(chat_id, channel, message_id + i)
    else:
        await bot.send_message(chat_id, "❌ Bunday kod topilmadi.")

# === ➕ Kino qo‘shish boshlandi ===
@dp.message_handler(lambda m: m.text == "➕ Anime qo‘shish")
async def cmd_add_start(message: types.Message):
    if message.from_user.id in ADMINS:
        await AdminStates.waiting_for_kino_data.set()
        await message.answer("📝 Format: `KOD @ServerChannel REKLAMA_POST_ID`\nMasalan: `91 @SDSSSASASD 4`", parse_mode="Markdown")

# === Kino qo‘shish handler ===
@dp.message_handler(state=AdminStates.waiting_for_kino_data)
async def add_kino_handler(message: types.Message, state: FSMContext):
    parts = message.text.strip().split()
    if len(parts) == 3 and parts[0].isdigit() and parts[2].isdigit():
        code, channel, rekl_id = parts
        kino = load_codes()
        kino[code] = {
            "channel": channel,
            "message_id": int(rekl_id) + 1  # reklama postdan keyingi kino post
        }
        save_codes(kino)
        # reklama postni kanalga yuboramiz
        url = f"https://t.me/{BOT_USERNAME.strip('@')}?start={code}"
        text = message.text  # foydalanuvchi yozgan matnni o'zini yuboramiz
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("📥 Yuklab olish", url=url))
        await bot.send_message(channel, text, reply_markup=kb, parse_mode="Markdown")
        await message.answer("✅ Anime qo‘shildi va reklama post yuborildi!")
    else:
        await message.answer("❌ Noto‘g‘ri format!\nMasalan: `91 @SDSSSASASD 4`", parse_mode="Markdown")
    await state.finish()

# === Yuklab olish tugmasi ===
@dp.message_handler(lambda m: m.text == "📥 Yuklab olish")
async def download_handler(message: types.Message):
    await message.answer("📥 Nechta post yuborilsin? (1 dan 10 gacha son kiriting):")
    await AdminStates.waiting_for_post_count.set()

@dp.message_handler(state=AdminStates.waiting_for_post_count)
async def post_count_handler(message: types.Message, state: FSMContext):
    post_count = message.text.strip()
    if post_count.isdigit() and 1 <= int(post_count) <= 10:
        code = ...  # Foydalanuvchidan kodni olish
        await send_kino_by_code(message.from_user.id, code, int(post_count))
        await message.answer(f"✅ {post_count} ta post yuborildi.")
    else:
        await message.answer("❌ Iltimos, 1 dan 10 gacha son kiriting.")
    await state.finish()

# === ❌ Kodni o‘chirish boshlandi ===
@dp.message_handler(lambda m: m.text == "❌ Kodni o‘chirish")
async def cmd_remove_start(message: types.Message):
    if message.from_user.id in ADMINS:
        await AdminStates.waiting_for_remove_code.set()
        await message.answer("🗑 O‘chirmoqchi bo‘lgan kodni yozing:")

# === Kodni o‘chirish handler ===
@dp.message_handler(state=AdminStates.waiting_for_remove_code)
async def remove_kino_handler(message: types.Message, state: FSMContext):
    code = message.text.strip()
    kino = load_codes()
    if code in kino:
        kino.pop(code)
        save_codes(kino)
        await message.answer(f"✅ Kod {code} o‘chirildi.")
    else:
        await message.answer("❌ Bunday kod topilmadi.")
    await state.finish()

# === 📄 Kodlar ro‘yxati ===
@dp.message_handler(lambda m: m.text == "📄 Kodlar ro‘yxati")
async def list_kodlar(message: types.Message):
    kino = load_codes()
    if not kino:
        return await message.answer("📂 Hech qanday kod yo‘q.")
    txt = "📄 Kodlar ro‘yxati:\n"
    for k, v in kino.items():
        txt += f"🔹 {k} → kanal {v['channel']} | kino_post={v['message_id']}\n"
    await message.answer(txt)

# === 📊 Statistika ===
@dp.message_handler(lambda m: m.text == "📊 Statistika")
async def stats(message: types.Message):
    kino = load_codes()
    users = load_users()
    await message.answer(f"📦 Kodlar: {len(kino)}\n👥 Foydalanuvchilar: {len(users)}")

# === ❌ Bekor qilish handler ===
@dp.message_handler(lambda m: m.text == "❌ Bekor qilish", state='*')
async def cancel_handler(message: types.Message, state: FSMContext):
    await state.finish()
    # qaytadan admin keyboard
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Anime qo‘shish", "❌ Kodni o‘chirish")
    kb.add("📄 Kodlar ro‘yxati", "📊 Statistika")
    kb.add("❌ Bekor qilish")
    await message.answer("❌ Amal bekor qilindi.", reply_markup=kb)

# === ISHGA TUSHURISH ===
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
