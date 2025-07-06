# database.py
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

db_pool = None

async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        database=os.getenv("DB_NAME"),
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT"))
    )
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS kino_codes (
                code TEXT PRIMARY KEY,
                channel TEXT,
                message_id INTEGER,
                post_count INTEGER
            );
        """)

async def add_user(user_id):
    async with db_pool.acquire() as conn:
        await conn.execute("INSERT INTO users (user_id) VALUES ($1) ON CONFLICT DO NOTHING", user_id)

async def get_user_count():
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT COUNT(*) FROM users")
        return row[0]

async def add_kino_code(code, channel, message_id, post_count):
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO kino_codes (code, channel, message_id, post_count)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (code) DO UPDATE SET
                channel = EXCLUDED.channel,
                message_id = EXCLUDED.message_id,
                post_count = EXCLUDED.post_count;
        """, code, channel, message_id, post_count)

async def get_kino_by_code(code):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT channel, message_id, post_count FROM kino_codes WHERE code = $1
        """, code)
        return row

async def get_all_codes():
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM kino_codes")
        return rows
