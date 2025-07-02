from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from dotenv import load_dotenv
from keep_alive import keep_alive
import os
import sqlite3

load_dotenv()
keep_alive()

API_TOKEN = os.getenv("API_TOKEN")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

class AdminStates(StatesGroup):
    waiting_for_code = State()
    waiting_for_remove = State()
    waiting_for_admin_id = State()

# SQLite ma'lumotlar bazasi bilan ishlash funksiyalari
def create_tables():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            user_id INTEGER UNIQUE
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS codes (
            code TEXT PRIMARY KEY,
            msg_id INTEGER
        )
    ''')
    
    conn.commit()
    conn.close()

def add_user(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
    
    conn.commit()
    conn.close()

def get_users_count():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM users')
    count = cursor.fetchone()[0]
    
    conn.close()
    return count

def add_code(code, msg_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    cursor.execute('INSERT OR REPLACE INTO codes (code, msg_id) VALUES (?, ?)', (code, msg_id))
    
    conn.commit()
    conn.close()

def remove_code(code):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM codes WHERE code = ?', (code,))
    
    conn.commit()
    conn.close()

def get_all_codes():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT code, msg_id FROM codes')
    codes = {row[0]: row[1] for row in cursor.fetchall()}
    
    conn.close()
    return codes

def code_exists(code):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT msg_id FROM codes WHERE code = ?', (code,))
    result = cursor.fetchone()
    
    conn.close()
    return result[0] if result else None

def is_admin(user_id):
    # Admin ID'larini tekshirish
    return user_id == 6486825926  # O'z ID'ingizni qo'shing

async def is_user_subscribed(user_id):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        print(f"Error checking subscription: {e}")  # Xatolikni konsolga chiqarish
        return False

@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    add_user(message.from_user.id)  # Foydalanuvchini qo'shish

    if await is_user_subscribed(message.from_user.id):
        buttons = [[KeyboardButton("📢 Reklama"), KeyboardButton("💼 Homiylik")]]
        if is_admin(message.from_user.id):  # await qo'shilmadi, chunki bu sinxron funksiya
            buttons.append([KeyboardButton("🛠 Admin panel")])
        markup = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
        await message.answer("✅ Obuna bor. Kodni yuboring:", reply_markup=markup)
    else:
        markup = InlineKeyboardMarkup().add(
            InlineKeyboardButton("Kanal", url=f"https://t.me/{CHANNEL_USERNAME.strip('@')}")
        ).add(
            InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")
        )
        await message.answer("❗ Iltimos, kanalga obuna bo‘ling:", reply_markup=markup)

@dp.message_handler(commands=["myid"])
async def get_my_id(message: types.Message):
    status = "Admin" if is_admin(message.from_user.id) else "Oddiy foydalanuvchi"
    await message.answer(f"🆔 ID: `{message.from_user.id}`\n👤 Holat: {status}", parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data == "check_sub")
async def check_subscription(callback_query: types.CallbackQuery):
    if await is_user_subscribed(callback_query.from_user.id):
        await callback_query.message.edit_text("\u2705 Obuna tekshirildi. Kod yuboring.")
    else:
        await callback_query.answer("\u2757 Hali ham obuna emassiz!", show_alert=True)

@dp.message_handler(lambda message: message.text == "📢 Reklama")
async def reklama_handler(message: types.Message):
    await message.answer("📢 Reklama bo‘limi. Reklama uchun @DiyorbekPTMA ga murojat qiling.")

@dp.message_handler(lambda message: message.text == "💼 Homiylik")
async def homiylik_handler(message: types.Message):
    await message.answer("💼 Homiylik bo‘limi. Homiylik uchun karta: ''8800904257677885''")

@dp.message_handler(lambda m: m.text == "🛠 Admin panel")
async def admin_handler(message: types.Message):
    if await is_user_subscribed(message.from_user.id) and is_admin(message.from_user.id):
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(
            KeyboardButton("➕ Kod qo‘shish"), KeyboardButton("📄 Kodlar ro‘yxati")
        )
        markup.add(
            KeyboardButton("❌ Kodni o‘chirish"), KeyboardButton("📊 Statistika")
        )
        markup.add(
            KeyboardButton("👤 Admin qo‘shish"), KeyboardButton("🔙 Orqaga")
        )
        await message.answer("👮‍♂️ Admin paneliga xush kelibsiz!", reply_markup=markup)
    else:
        await message.answer("⛔ Siz admin emassiz yoki kanalga obuna bo'lmagansiz!")

@dp.message_handler(lambda m: m.text == "🔙 Orqaga")
async def back_to_menu(message: types.Message):
    buttons = [[KeyboardButton("📢 Reklama"), KeyboardButton("💼 Homiylik")]]
    if is_admin(message.from_user.id):  # await qo'shilmadi, chunki bu sinxron funksiya
        buttons.append([KeyboardButton("🛠 Admin panel")])
    markup = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    await message.answer("🏠 Asosiy menyuga qaytdingiz.", reply_markup=markup)

@dp.message_handler(lambda m: m.text == "➕ Kod qo‘shish")
async def start_add_code(message: types.Message):
    await message.answer("➕ Yangi kod va post ID ni yuboring. Masalan: 47 1000")
    await AdminStates.waiting_for_code.set()

@dp.message_handler(state=AdminStates.waiting_for_code)
async def add_code_handler(message: types.Message, state: FSMContext):
    # Kodlarni vergul bilan ajratish
    code_pairs = message.text.strip().split(',')  # Kod va msg_id juftliklarini olish
    success_count = 0  # Qo'shilgan kodlar sonini hisoblash

    for pair in code_pairs:
        pair = pair.strip()  # Har bir juftlikni tozalash
        parts = pair.split()  # Kod va msg_id ni ajratish
        if len(parts) != 2 or not all(p.isdigit() for p in parts):
            await message.answer(f"❌ Noto‘g‘ri format: {pair}. Masalan: 47 1000")
            continue
        
        code, msg_id = parts  # Kod va msg_id ni olish
        add_code(code, int(msg_id))  # Kodni ma'lumotlar bazasiga qo'shish
        success_count += 1

    await message.answer(f"✅ {success_count} ta kod qo‘shildi.")
    await state.finish()


@dp.message_handler(lambda m: m.text == "❌ Kodni o‘chirish")
async def start_remove_code(message: types.Message):
    await message.answer("🗑 O‘chirmoqchi bo‘lgan kodni yuboring:")
    await AdminStates.waiting_for_remove.set()

@dp.message_handler(state=AdminStates.waiting_for_remove)
async def remove_code_handler(message: types.Message, state: FSMContext):
    # Kodlarni vergul bilan ajratish
    codes = message.text.strip().split(',')  # O'chirilishi kerak bo'lgan kodlarni olish
    success_count = 0  # O'chirilgan kodlar sonini hisoblash

    for code in codes:
        code = code.strip()  # Har bir kodni tozalash
        if code.isdigit():  # Kod raqam ekanligini tekshirish
            if code_exists(int(code)):  # Kod mavjudligini tekshirish
                remove_code(int(code))  # Kodni ma'lumotlar bazasidan o'chirish
                success_count += 1
            else:
                await message.answer(f"❌ Bunday kod yo‘q: {code}")
        else:
            await message.answer(f"❌ Noto‘g‘ri kod: {code}")

    await message.answer(f"✅ {success_count} ta kod o‘chirildi.")
    await state.finish()


@dp.message_handler(lambda m: m.text == "📄 Kodlar ro‘yxati")
async def list_codes_handler(message: types.Message):
    codes = get_all_codes()
    if not codes:
        await message.answer("📜 Hozircha hech qanday kod yo‘q.")
    else:
        text = "📄 Kodlar ro‘yxati:\n"
        for code, msg_id in codes.items():
            text += f"🔑 {code} — ID: {msg_id}\n"
        await message.answer(text)

@dp.message_handler(lambda m: m.text == "📊 Statistika")
async def stat_handler(message: types.Message):
    try:
        chat = await bot.get_chat(CHANNEL_USERNAME)
        members = await bot.get_chat_members_count(chat.id)
        users = get_users_count()
        codes = len(get_all_codes())  # Kodlar sonini olish
        await message.answer(f"👥 Obunachilar: {members}\n📜 Kodlar soni: {codes} ta\n👤 Foydalanuvchilar: {users} ta")
    except Exception as e:
        await message.answer("⚠️ Statistika olishda xatolik!")

@dp.message_handler(lambda m: m.text == "👤 Admin qo‘shish")
async def start_add_admin(message: types.Message):
    await message.answer("🆕 Yangi adminning Telegram ID raqamini yuboring:")
    await AdminStates.waiting_for_admin_id.set()

@dp.message_handler(state=AdminStates.waiting_for_admin_id)
async def add_admin_handler(message: types.Message, state: FSMContext):
    user_id = message.text.strip()
    if user_id.isdigit():
        user_id = int(user_id)
        if not is_admin(user_id):  # await qo'shilmadi, chunki bu sinxron funksiya
            # Admin qo'shish logikasi
            await message.answer(f"✅ Admin qo‘shildi: `{user_id}`")
        else:
            await message.answer("⚠️ Bu foydalanuvchi allaqachon admin.")
    else:
        await message.answer("❌ Noto‘g‘ri ID!")
    await state.finish()

@dp.message_handler(lambda msg: msg.text.strip().isdigit())
async def handle_code(message: types.Message):
    code = message.text.strip()
    if not await is_user_subscribed(message.from_user.id):
        await message.answer("❗ Koddan foydalanish uchun avval kanalga obuna bo‘ling.")
        return
    msg_id = code_exists(code)
    if msg_id:
        await bot.copy_message(
            chat_id=message.chat.id,
            from_chat_id=CHANNEL_USERNAME,
            message_id=msg_id,
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("📥 Yuklab olish", url=f"https://t.me/{CHANNEL_USERNAME.strip('@')}/{msg_id}")
            )
        )
    else:
        await message.answer("❌ Bunday kod topilmadi. Iltimos, to‘g‘ri kod yuboring.")

if __name__ == '__main__':
    create_tables()  # Jadvalni yaratish
    executor.start_polling(dp, skip_updates=True)
