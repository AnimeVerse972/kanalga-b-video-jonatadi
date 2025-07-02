import sqlite3

def create_tables():
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS posts (
        code TEXT PRIMARY KEY,
        message_id INTEGER
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY
    )''')

    conn.commit()
    conn.close()

def add_user(user_id):
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def get_users_count():
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    count = c.fetchone()[0]
    conn.close()
    return count

def add_code(code, message_id):
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("REPLACE INTO posts (code, message_id) VALUES (?, ?)", (code, message_id))
    conn.commit()
    conn.close()

def remove_code(code):
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("DELETE FROM posts WHERE code=?", (code,))
    conn.commit()
    conn.close()

def get_all_codes():
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("SELECT code, message_id FROM posts")
    data = c.fetchall()
    conn.close()
    return {code: message_id for code, message_id in data}

def code_exists(code):
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("SELECT message_id FROM posts WHERE code=?", (code,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def add_admin(user_id):
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def is_admin(user_id):
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("SELECT 1 FROM admins WHERE user_id=?", (user_id,))
    res = c.fetchone()
    conn.close()
    return bool(res)

def get_admins():
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("SELECT user_id FROM admins")
    data = [row[0] for row in c.fetchall()]
    conn.close()
    return data

def get_codes_count():
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM posts")
    count = c.fetchone()[0]
    conn.close()
    return count
