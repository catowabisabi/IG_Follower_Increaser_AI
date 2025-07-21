import sqlite3
import threading

class FollowedUserDB:
    def __init__(self, db_path='followed_user.db'):
        self.db_path = db_path
        self.lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    email TEXT
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS followed (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    followed_username TEXT,
                    UNIQUE(user_id, followed_username)
                )
            ''')
            conn.commit()

    def add_user(self, user_id, email=None):
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute('INSERT OR IGNORE INTO users (user_id, email) VALUES (?, ?)', (user_id, email))
                conn.commit()

    def add_followed_user(self, user_id, followed_username):
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                try:
                    c.execute('INSERT INTO followed (user_id, followed_username) VALUES (?, ?)', (user_id, followed_username))
                    conn.commit()
                    return True
                except sqlite3.IntegrityError:
                    return False  # 已存在

    def has_followed(self, user_id, followed_username):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT 1 FROM followed WHERE user_id = ? AND followed_username = ?', (user_id, followed_username))
            return c.fetchone() is not None

    def get_followed_users(self, user_id):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT followed_username FROM followed WHERE user_id = ?', (user_id,))
            return [row[0] for row in c.fetchall()]

    def get_user_email(self, user_id):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT email FROM users WHERE user_id = ?', (user_id,))
            row = c.fetchone()
            return row[0] if row else None
