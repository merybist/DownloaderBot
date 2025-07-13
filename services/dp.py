import sqlite3

conn_bot = sqlite3.connect('services/bot.db', check_same_thread=False)
cur_bot = conn_bot.cursor()

# Таблиця користувачів
cur_bot.execute('''CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT, 
    user_id INTEGER UNIQUE, 
    first_name TEXT, 
    last_name TEXT,
    chat_id INTEGER
)''')


cur_bot.execute('''CREATE TABLE IF NOT EXISTS search_cache (
    query TEXT PRIMARY KEY,
    results TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')

conn_bot.commit()