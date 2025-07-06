import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL")

db_pool = None

async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL)
    async with db_pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY
        );
        """)
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS kino (
            code TEXT PRIMARY KEY,
            channel TEXT,
            message_id INTEGER,
            post_count INTEGER
        );
        """)
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS stats (
            code TEXT PRIMARY KEY,
            searched INTEGER DEFAULT 0,
            loaded INTEGER DEFAULT 0
        );
        """)
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS required_channels (
            id SERIAL PRIMARY KEY,
            channel TEXT UNIQUE
        );
        """)

# === Foydalanuvchilar ===
async def add_user(user_id):
    async with db_pool.acquire() as conn:
        await conn.execute("INSERT INTO users (user_id) VALUES ($1) ON CONFLICT DO NOTHING", user_id)

async def get_user_count():
    async with db_pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM users")

# === Kino kodlari ===
async def add_kino_code(code, channel, message_id, post_count):
    async with db_pool.acquire() as conn:
        await conn.execute("""
        INSERT INTO kino (code, channel, message_id, post_count)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (code) DO UPDATE SET channel = $2, message_id = $3, post_count = $4
        """, code, channel, message_id, post_count)

        await conn.execute("INSERT INTO stats (code) VALUES ($1) ON CONFLICT DO NOTHING", code)

async def get_kino_by_code(code):
    async with db_pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM kino WHERE code = $1", code)

async def get_all_codes():
    async with db_pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM kino ORDER BY message_id")

async def delete_kino_code(code):
    async with db_pool.acquire() as conn:
        result = await conn.execute("DELETE FROM kino WHERE code = $1", code)
        return result.endswith("1")

# === Statistika ===
async def increment_stat(code, field):
    if field not in ("searched", "loaded"):
        return
    async with db_pool.acquire() as conn:
        await conn.execute(f"UPDATE stats SET {field} = {field} + 1 WHERE code = $1", code)

# === Majburiy obuna kanallari ===
async def add_required_channel(channel: str):
    async with db_pool.acquire() as conn:
        await conn.execute("INSERT INTO required_channels (channel) VALUES ($1) ON CONFLICT DO NOTHING", channel)

async def get_required_channels():
    async with db_pool.acquire() as conn:
        return await conn.fetch("SELECT channel FROM required_channels")
