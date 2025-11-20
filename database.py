import sqlite3
import logging
from datetime import datetime
import config

# إعداد التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_NAME = 'host_bot.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # جدول المستخدمين
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            is_admin BOOLEAN DEFAULT 0,
            is_banned BOOLEAN DEFAULT 0,
            join_date TEXT
        )
    """)
    
    # جدول الملفات المرفوعة
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            file_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_type TEXT NOT NULL, -- 'py', 'js', 'zip'
            status TEXT DEFAULT 'stopped', -- 'running', 'stopped', 'error'
            process_id INTEGER, -- PID of the running script
            upload_date TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    
    # جدول إعدادات البوت العامة (مثل حالة القفل)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    # التأكد من وجود إعداد قفل البوت
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ('bot_locked', '0'))
    
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully.")

def get_db_connection():
    return sqlite3.connect(DB_NAME)

# --- وظائف المستخدمين ---

def get_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    return user_data

def add_user(user_id, username, first_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    join_date = datetime.now().isoformat()
    try:
        cursor.execute("""
            INSERT INTO users (user_id, username, first_name, join_date)
            VALUES (?, ?, ?, ?)
        """, (user_id, username, first_name, join_date))
        conn.commit()
        logger.info(f"New user added: {user_id}")
        return True
    except sqlite3.IntegrityError:
        # المستخدم موجود بالفعل
        return False
    finally:
        conn.close()

def is_admin(user_id):
    # المالك هو دائماً مسؤول
    if user_id == config.ADMIN_ID:
        return True
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result and result[0] == 1

def set_admin(user_id, is_admin_status):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_admin = ? WHERE user_id = ?", (1 if is_admin_status else 0, user_id))
    conn.commit()
    conn.close()

def is_banned(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result and result[0] == 1

def ban_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def unban_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_all_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, first_name, is_admin, is_banned, join_date FROM users")
    users = cursor.fetchall()
    conn.close()
    return users

# --- وظائف الملفات ---

def add_file(user_id, file_name, file_path, file_type):
    conn = get_db_connection()
    cursor = conn.cursor()
    upload_date = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO files (user_id, file_name, file_path, file_type, upload_date)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, file_name, file_path, file_type, upload_date))
    conn.commit()
    file_id = cursor.lastrowid
    conn.close()
    return file_id

def get_user_files(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT file_id, file_name, file_type, status, process_id FROM files WHERE user_id = ?", (user_id,))
    files = cursor.fetchall()
    conn.close()
    return files

def get_file_details(file_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT file_id, user_id, file_name, file_path, file_type, status, process_id FROM files WHERE file_id = ?", (file_id,))
    file_data = cursor.fetchone()
    conn.close()
    return file_data

def update_file_status(file_id, status, process_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if process_id is not None:
        cursor.execute("UPDATE files SET status = ?, process_id = ? WHERE file_id = ?", (status, process_id, file_id))
    else:
        cursor.execute("UPDATE files SET status = ? WHERE file_id = ?", (status, file_id))
    conn.commit()
    conn.close()

def delete_file_from_db(file_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM files WHERE file_id = ?", (file_id,))
    conn.commit()
    conn.close()

def get_all_running_files():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT file_id, user_id, file_path, process_id FROM files WHERE status = 'running'")
    files = cursor.fetchall()
    conn.close()
    return files

def get_all_files():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT file_id, user_id, file_name, file_path, file_type, status, process_id FROM files")
    files = cursor.fetchall()
    conn.close()
    return files

# --- وظائف إعدادات البوت ---

def get_setting(key):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def set_setting(key, value):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def is_bot_locked():
    return get_setting('bot_locked') == '1'

# --- وظائف الإحصائيات ---

def get_statistics():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM files")
    total_files = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM files WHERE status = 'running'")
    running_files = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1")
    banned_users = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'total_users': total_users,
        'total_files': total_files,
        'running_files': running_files,
        'banned_users': banned_users
    }

if __name__ == '__main__':
    init_db()
    # مثال لإضافة مستخدم أدمن عند التشغيل لأول مرة
    # set_admin(YOUR_ADMIN_ID, True)
    # print(get_statistics())
