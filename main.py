from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from dotenv import load_dotenv
from keep_alive import keep_alive
from database import init_db, add_user, get_user_count, add_kino_code, get_kino_by_code, get_all_codes, db_pool
import os

load_dotenv()
keep_alive()

API_TOKEN = os.getenv("API_TOKEN")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")
BOT_USERNAME = os.getenv("BOT_USERNAME")

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

ADMINS = [6486825926]

class AdminStates(StatesGroup):
    waiting_for_kino_data = State()
    waiting_for_broadcast_message = State()

async def is_user_subscribed(user_id):
    try:
        m = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return m.status in ["member", "administrator", "creator"]
    except:
        return False

@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    await add_user(message.from_user.id)
    args = message.get_args()
    if args and args.isdigit():
        code = args
        if not await is_user_subscribed(message.from_user.id):
            markup = InlineKeyboardMarkup().add(
                InlineKeyboardButton("\ud83d\udce2 Obuna bo‘lish", url=f"https://t.me/{CHANNEL_USERNAME.strip('@')}"),
                InlineKeyboardButton("\u2705 Tekshirish", callback_data=f"check_sub:{code}")
            )
            await message.answer("\u2757 Anime olishdan oldin kanalga obuna bo‘ling:", reply_markup=markup)
        else:
            await send_reklama_post(message.from_user.id, code)
        return

    if message.from_user.id in ADMINS:
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("\u2795 Anime qo‘shish", "\ud83d\udcc4 Kodlar ro‘yxati")
        kb.add("\ud83d\udcca Statistika", "\ud83d\udce2 Xabar yuborish")
        kb.add("\u274c Bekor qilish")
        await message.answer("\ud83d\udc6e\u200d\u2642\ufe0f Admin panel:", reply_markup=kb)
    else:
        await message.answer("\ud83c\udfac Anime olish uchun kod kiriting:")

@dp.message_handler(lambda message: message.text.isdigit())
async def handle_code_message(message: types.Message):
    code = message.text
    if not await is_user_subscribed(message.from_user.id):
        markup = InlineKeyboardMarkup().add(
            InlineKeyboardButton("\ud83d\udce2 Obuna bo‘lish", url=f"https://t.me/{CHANNEL_USERNAME.strip('@')}"),
            InlineKeyboardButton("\u2705 Tekshirish", callback_data=f"check_sub:{code}")
        )
        await message.answer("\u2757 Anime olishdan oldin kanalga obuna bo‘ling:", reply_markup=markup)
    else:
        await send_reklama_post(message.from_user.id, code)

@dp.callback_query_handler(lambda c: c.data.startswith("check_sub:"))
async def check_sub(callback: types.CallbackQuery):
    code = callback.data.split(":")[1]
    if await is_user_subscribed(callback.from_user.id):
        await callback.message.edit_text("\u2705 Obuna tasdiqlandi!")
        await send_reklama_post(callback.from_user.id, code)
    else:
        await callback.answer("\u2757 Obuna bo‘lmagansiz!", show_alert=True)

async def send_reklama_post(user_id, code):
    data = await get_kino_by_code(code)
    if not data:
        await bot.send_message(user_id, "\u274c Kod topilmadi.")
        return

    channel, reklama_id, post_count = data["channel"], data["message_id"], data["post_count"]
    buttons = [InlineKeyboardButton(str(i), callback_data=f"kino:{code}:{i}") for i in range(1, post_count + 1)]
    keyboard = InlineKeyboardMarkup(row_width=5)
    keyboard.add(*buttons)

    try:
        await bot.copy_message(user_id, channel, reklama_id - 1, reply_markup=keyboard)
    except:
        await bot.send_message(user_id, "\u274c Reklama postni yuborib bo‘lmadi.")

@dp.callback_query_handler(lambda c: c.data.startswith("kino:"))
async def kino_button(callback: types.CallbackQuery):
    _, code, number = callback.data.split(":")
    number = int(number)
    result = await get_kino_by_code(code)
    if not result:
        await callback.message.answer("\u274c Kod topilmadi.")
        return

    channel, base_id, post_count = result["channel"], result["message_id"], result["post_count"]
    if number > post_count:
        await callback.answer("\u274c Bunday post yo‘q!", show_alert=True)
        return

    await bot.copy_message(callback.from_user.id, channel, base_id + number - 1)
    await callback.answer()

@dp.message_handler(lambda m: m.text == "\u2795 Anime qo‘shish")
async def add_start(message: types.Message):
    if message.from_user.id in ADMINS:
        await AdminStates.waiting_for_kino_data.set()
        await message.answer("\ud83d\udcdd Format: `KOD @kanal REKLAMA_ID POST_SONI`\nMasalan: `91 @MyKino 4 12`", parse_mode="Markdown")

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
            InlineKeyboardButton("\ud83d\udce5 Yuklab olish", url=f"https://t.me/{BOT_USERNAME}?start={code}")
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

    await message.answer(f"\u2705 Yangi kodlar qo‘shildi:\n\n\u2705 Muvaffaqiyatli: {successful}\n\u274c Xatolik: {failed}")
    await state.finish()

@dp.message_handler(lambda m: m.text == "\ud83d\udcc4 Kodlar ro‘yxati")
async def kodlar(message: types.Message):
    kodlar = await get_all_codes()
    if not kodlar:
        await message.answer("\ud83d\udcc2 Kodlar yo‘q.")
        return
    text = "\ud83d\udcc4 Kodlar:\n"
    for row in kodlar:
        code, ch, msg_id, count = row["code"], row["channel"], row["message_id"], row["post_count"]
        text += f"\ud83d\udd39 {code} \u2192 {ch} | {msg_id} ({count} post)\n"
    await message.answer(text)

@dp.message_handler(lambda m: m.text == "\ud83d\udcca Statistika")
async def stats(message: types.Message):
    kodlar = await get_all_codes()
    foydalanuvchilar = await get_user_count()
    await message.answer(f"\ud83d\udcc6 Kodlar: {len(kodlar)}\n\ud83d\udc65 Foydalanuvchilar: {foydalanuvchilar}")

@dp.message_handler(lambda m: m.text == "\ud83d\udce2 Xabar yuborish")
async def ask_code_for_reply(message: types.Message):
    if message.from_user.id in ADMINS:
        await AdminStates.waiting_for_broadcast_message.set()
        await message.answer("\u270d\ufe0f Format: `kod matn`\nMasalan: `57 Bu animening 2-qismi yaqin kunlarda chiqadi!`")

@dp.message_handler(state=AdminStates.waiting_for_broadcast_message)
async def send_reply_to_users(message: types.Message, state: FSMContext):
    await state.finish()
    try:
        code, matn = message.text.strip().split(" ", 1)
    except:
        await message.answer("\u2757 Noto‘g‘ri format. Masalan: `57 Sizga yoqdimi?`")
        return

    data = await get_kino_by_code(code)
    if not data:
        await message.answer("\u274c Kod topilmadi.")
        return

    channel = data["channel"]
    reklama_id = data["message_id"] - 1
    count = 0

    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM users")
        for row in rows:
            try:
                await bot.send_message(
                    chat_id=row['user_id'],
                    text=matn,
                    reply_to_message_id=reklama_id,
                    allow_sending_without_reply=True
                )
                count += 1
            except:
                pass

    await message.answer(f"\u2705 Xabar {count} foydalanuvchiga yuborildi.")

@dp.message_handler(lambda m: m.text == "\u274c Bekor qilish", state="*")
async def cancel(message: types.Message, state: FSMContext):
    await state.finish()
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("\u2795 Anime qo‘shish", "\ud83d\udcc4 Kodlar ro‘yxati")
    kb.add("\ud83d\udcca Statistika", "\ud83d\udce2 Xabar yuborish")
    kb.add("\u274c Bekor qilish")
    await message.answer("\u274c Bekor qilindi", reply_markup=kb)

async def on_startup(dp):
    await init_db()
    print("\u2705 PostgreSQL bazaga ulandi!")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
