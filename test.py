import time
import random
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import openai
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import sqlite3
from datetime import datetime
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
import os
import threading
from flask import Flask, request, jsonify
import logging
import uuid
from werkzeug.utils import secure_filename

# ========== SessionManager ========== #
class SessionManager:
    _instances = {}
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls, username, password, chromedriver_path=None, comment_list=None, openai_api_key=None):
        with cls._lock:
            if username not in cls._instances:
                # 每個帳號一個 user-data-dir
                user_data_dir = os.path.join(os.getcwd(), 'user_data', username)
                os.makedirs(user_data_dir, exist_ok=True)
                bot = InstagramBot(
                    username=username,
                    password=password,
                    chromedriver_path=chromedriver_path,
                    comment_list=comment_list,
                    openai_api_key=openai_api_key,
                    user_data_dir=user_data_dir
                )
                cls._instances[username] = bot
            return cls._instances[username]

    @classmethod
    def remove_instance(cls, username):
        with cls._lock:
            if username in cls._instances:
                try:
                    cls._instances[username].quit()
                except Exception:
                    pass
                del cls._instances[username]

    @classmethod
    def all_usernames(cls):
        return list(cls._instances.keys())

# ========== 日誌設置 ========== #
logging.basicConfig(filename='igbot.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# ========== InstagramBot 增強 ========== #
class InstagramBot:
    def __init__(self, username=None, password=None, chromedriver_path=None, comment_list=None, openai_api_key=None, user_data_dir=None):
        self.username = username
        self.password = password
        self.comment_list = comment_list
        self.openai_api_key = openai_api_key
        self.new_followed = []
        self.prev_user_list = []
        self.liked = 0
        self.followed = 0
        self.commented = 0
        self.daily_followed = 0
        self.daily_liked = 0
        self.daily_commented = 0
        self.last_action_date = None
        self.user_data_dir = user_data_dir
        options = Options()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-web-security")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")
        if user_data_dir:
            options.add_argument(f"--user-data-dir={user_data_dir}")
        if chromedriver_path:
            service = Service(chromedriver_path)
            self.driver = webdriver.Chrome(service=service, options=options)
        else:
            self.driver = webdriver.Chrome(options=options)
        if openai_api_key:
            openai.api_key = openai_api_key
        self.init_database()
        self._login()

    def wait(self, min_seconds=2, max_seconds=6):
        time.sleep(random.uniform(min_seconds, max_seconds))

    def init_database(self):
        self.conn = sqlite3.connect('instagram_bot.db')
        self.cursor = self.conn.cursor()
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS followed_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                followed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                bot_username TEXT NOT NULL
            )
        ''')
        self.conn.commit()

    def _login(self):
        try:
            print(f"[Login] {self.username} Navigating to login page...")
            self.driver.get("https://www.instagram.com/accounts/login/")
            self.wait(5, 8)
            print("[Login] Entering username and password")
            self.driver.find_element(By.NAME, 'username').send_keys(self.username)
            self.wait()
            self.driver.find_element(By.NAME, 'password').send_keys(self.password)
            self.wait()
            print("[Login] Submitting login form")
            self.driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
            self.wait(8, 12)
            try:
                self.driver.find_element(By.XPATH, "//button[contains(text(), 'Not Now')]").click()
                self.wait()
                print("[Login] Dismissed save login info")
            except:
                pass
            try:
                self.driver.find_element(By.XPATH, "//button[contains(text(), 'Not Now')]").click()
                self.wait()
                print("[Login] Dismissed notifications")
            except:
                pass
            print("[Login] Login successful")
            logging.info(f"[Login] {self.username} login successful")
        except Exception as e:
            print(f"[Login Error] {e}")
            logging.error(f"[Login Error] {self.username}: {e}")
            SessionManager.remove_instance(self.username)
            raise

    def _handle_session_error(self, func):
        try:
            return func()
        except Exception as e:
            if "login" in str(e).lower() or "session" in str(e).lower():
                print(f"[Session] 失效，重新登入: {self.username}")
                logging.warning(f"[Session] 失效，重新登入: {self.username}")
                self._login()
                return func()
            raise

    def load_previous_users(self, days_limit=30):
        print("[Database] Loading previously followed users...")
        try:
            query = '''
                SELECT username FROM followed_users 
                WHERE bot_username = ? 
                AND followed_date >= datetime('now', ?)
            '''
            self.cursor.execute(query, (self.username, f'-{days_limit} days'))
            results = self.cursor.fetchall()
            self.prev_user_list = [row[0] for row in results]
        except sqlite3.Error as e:
            print(f"[Database Error] {e}")
            self.prev_user_list = []
        print(f"[Database] Loaded {len(self.prev_user_list)} previously followed users.")

    def random_human_action(self):
        try:
            width = self.driver.execute_script("return window.innerWidth")
            height = self.driver.execute_script("return window.innerHeight")
            x = random.randint(0, max(1, width)-1)
            y = random.randint(0, max(1, height)-1)
            ActionChains(self.driver).move_by_offset(x, y).perform()
            scroll_y = random.randint(0, height)
            self.driver.execute_script(f"window.scrollTo(0, {scroll_y});")
            time.sleep(random.uniform(1, 3))
        except Exception as e:
            print(f"[HumanAction] 模擬人類行為失敗: {e}")

    # 操作頻率限制
    def check_daily_limit(self, follow_limit=100, like_limit=200, comment_limit=50):
        today = datetime.now().date()
        if self.last_action_date != today:
            self.daily_followed = 0
            self.daily_liked = 0
            self.daily_commented = 0
            self.last_action_date = today
        if self.daily_followed >= follow_limit:
            raise Exception("今日 follow 已達上限")
        if self.daily_liked >= like_limit:
            raise Exception("今日 like 已達上限")
        if self.daily_commented >= comment_limit:
            raise Exception("今日 comment 已達上限")

    # CAPTCHA 偵測時自動暫停
    def is_captcha_present(self):
        try:
            if "challenge" in self.driver.current_url or "checkpoint" in self.driver.current_url:
                print("[警告] 檢測到 CAPTCHA/驗證頁面！")
                logging.warning(f"[CAPTCHA] {self.username} hit CAPTCHA!")
                # 這裡可擴充 email/line 通知
                return True
        except:
            pass
        return False

    def explore_hashtags(self, hashtags, max_posts_per_tag=10):
        for tag in hashtags:
            print(f"\n[Exploring Hashtag] #{tag}")
            self.driver.get(f"https://www.instagram.com/explore/tags/{tag}/")
            self.wait(3, 7)
            self.random_human_action()
            print(f"[Action] Loaded hashtag page for #{tag}")

            if self.is_captcha_present():
                print("[Block] 偵測到驗證碼，結束本次 hashtag 探索。")
                return

            try:
                print("[Search] Looking for first post thumbnail")
                first_thumb = self.driver.find_element(By.XPATH, "//section/main//a")
                self.random_human_action()
                first_thumb.click()
                print(f"[Success] Clicked on first post for #{tag}")
                self.wait(3, 7)
            except:
                print("[Error] Failed to find or click first post")
                continue

            for i in range(max_posts_per_tag):
                print(f"\n[Post #{i+1}] Processing post")
                self.random_human_action()
                if self.is_captcha_present():
                    print("[Block] 偵測到驗證碼，結束 hashtag 探索。")
                    return
                try:
                    print("[Search] Looking for username link")
                    user = self.driver.find_element(By.XPATH, "//header//a").text
                    self.wait()
                    print(f"[Found] Post owner: {user}")
                    if user not in self.prev_user_list:
                        try:
                            follow_btn = self.driver.find_element(By.XPATH, "//header//button")
                            self.random_human_action()
                            self.wait()
                            print(f"[Search] Found follow button: {follow_btn.text}")
                            if follow_btn.text.lower() in ['follow', 'follow back', '追蹤']:
                                follow_btn.click()
                                print(f"[Action] Followed {user}")
                                self.wait()
                                self.random_human_action()
                                self.new_followed.append(user)
                                self.followed += 1
                                self.daily_followed += 1
                                self.check_daily_limit()

                                try:
                                    like_btn = self.driver.find_element(By.XPATH, "//section/span/button")
                                    self.random_human_action()
                                    like_btn.click()
                                    self.liked += 1
                                    self.daily_liked += 1
                                    self.check_daily_limit()
                                    print(f"[Action] Liked post from {user}")
                                    self.wait()
                                except:
                                    print("[Error] Like button not found")

                                if self.comment_list:
                                    try:
                                        comment = random.choice(self.comment_list)
                                        self.random_human_action()
                                        self.leave_comment(comment)
                                        print(f"[Action] Commented on {user}'s post: {comment}")
                                        self.wait()
                                    except:
                                        print("[Error] Failed to comment")
                                        self.daily_commented += 1
                                        self.check_daily_limit()
                            else:
                                print("[Skip] Already followed user")
                        except:
                            print("[Error] Follow/Like/Comment actions failed")
                    else:
                        print("[Skip] User already in database")
                except:
                    print("[Error] Failed to get user info")

                try:
                    print("[Navigation] Trying to move to the next post.")
                    next_btn = self.driver.find_element(By.XPATH, "//button[contains(@aria-label, 'Next')]")
                    self.random_human_action()
                    next_btn.click()
                    print("[Action] Attempting to click Next button")
                    self.wait(2, 5)
                except:
                    print("[End] Next button not found, ending loop")
                    break

    def leave_comment(self, text):
        try:
            comment_area = self.driver.find_element(By.XPATH, "//textarea")
            self.random_human_action()
            comment_area.click()
            self.wait()
            comment_area.send_keys(text)
            self.wait()
            comment_area.send_keys(Keys.ENTER)
            self.commented += 1
            self.daily_commented += 1
            self.check_daily_limit()
            self.wait()
        except:
            print("[Error] Commenting failed")

    def gpt_reply_to_top_comments(self, max_comments=10):
        print("[GPT] Generating replies to top comments...")
        try:
            comments = self.driver.find_elements(By.XPATH, "//ul[contains(@class, 'Mr508')]//span")
            comment_likes = self.driver.find_elements(By.XPATH, "//button[contains(@aria-label, 'likes')]")
            top_comments = sorted(
                zip(comments, comment_likes),
                key=lambda x: int(x[1].text.replace(',', '')) if x[1].text else 0,
                reverse=True
            )[:max_comments]

            for comment, _ in top_comments:
                reply = self.generate_gpt_reply(comment.text)
                try:
                    comment.find_element(By.XPATH, "..//..//..//button[contains(text(),'Reply')]").click()
                    self.wait()
                    reply_box = self.driver.find_element(By.XPATH, "//textarea")
                    reply_box.send_keys(reply)
                    self.wait()
                    reply_box.send_keys(Keys.ENTER)
                    self.wait()
                    print(f"[GPT] Replied: {reply}")
                except:
                    print("[Error] Failed to reply to a top comment")
        except Exception as e:
            print(f"[Error] GPT comment reply failed: {e}")

    def generate_gpt_reply(self, comment_text):
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a witty and kind Instagram influencer."},
                    {"role": "user", "content": f"Reply to this comment: '{comment_text}'"}
                ],
                max_tokens=50,
                temperature=0.8
            )
            return response.choices[0].message.content.strip()
        except:
            return "Thanks for your comment!"

    def save_followed(self):
        print("[Database] Saving followed users...")
        try:
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            data = [(user, current_time, self.username) for user in self.new_followed]
            self.cursor.executemany(
                'INSERT INTO followed_users (username, followed_date, bot_username) VALUES (?, ?, ?)',
                data
            )
            self.conn.commit()
            print(f"[Database] Saved {len(data)} users.")
        except sqlite3.Error as e:
            print(f"[Database Error] {e}")
        self.conn.close()

    def quit(self):
        print("[System] Quitting browser...")
        self.driver.quit()






if __name__ == "__main__":

    from dotenv import load_dotenv
    load_dotenv(override=True)
    from config import comment_list, hashtags



    username = os.getenv("USERNAME")
    password = os.getenv("PASSWORD")
    chromedriver_path = os.getenv("CHROMEDRIVER_PATH")
    openai_api_key = os.getenv("OPENAI_API_KEY")

    print(f"\nStarting IG Bot for: {username}\n")

    bot = InstagramBot(
    username=username,
    password=password,
    chromedriver_path=chromedriver_path,
    comment_list=comment_list,
    openai_api_key=openai_api_key
    )

    bot.login()
    input("Login 完成，請按 Enter 關閉瀏覽器...")
    bot.quit()
   
# ========== 多帳號排程/自動切換 ========== #
def multi_account_scheduler(accounts, hashtags, comment_list, chromedriver_path=None, openai_api_key=None, interval=600):
    """
    accounts: List[Dict]，每個 dict 包含 username, password
    interval: 每個帳號操作間隔秒數
    """
    while True:
        for acc in accounts:
            try:
                bot = SessionManager.get_instance(
                    username=acc['username'],
                    password=acc['password'],
                    chromedriver_path=chromedriver_path,
                    comment_list=comment_list,
                    openai_api_key=openai_api_key
                )
                bot._handle_session_error(lambda: bot.load_previous_users())
                bot._handle_session_error(lambda: bot.explore_hashtags(hashtags, max_posts_per_tag=5))
                bot._handle_session_error(lambda: bot.gpt_reply_to_top_comments())
                bot._handle_session_error(lambda: bot.save_followed())
                logging.info(f"[Scheduler] {acc['username']} 完成一輪操作")
            except Exception as e:
                logging.error(f"[Scheduler] {acc['username']} error: {e}")
            time.sleep(interval)

# ========== Flask API 介面 ========== #
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/login', methods=['POST'])
def api_login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    chromedriver_path = data.get('chromedriver_path')
    openai_api_key = data.get('openai_api_key')
    # comment_list, hashtags 可根據需求傳入
    try:
        bot = SessionManager.get_instance(username, password, chromedriver_path, comment_list=None, openai_api_key=openai_api_key)
        return jsonify({'message': f'{username} login success'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/explore', methods=['POST'])
def api_explore():
    data = request.json
    username = data.get('username')
    hashtags = data.get('hashtags', [])
    try:
        bot = SessionManager._instances[username]
        bot._handle_session_error(lambda: bot.explore_hashtags(hashtags, max_posts_per_tag=5))
        return jsonify({'message': 'explore finished'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/comment', methods=['POST'])
def api_comment():
    data = request.json
    username = data.get('username')
    comment = data.get('comment')
    try:
        bot = SessionManager._instances[username]
        bot._handle_session_error(lambda: bot.leave_comment(comment))
        return jsonify({'message': 'comment finished'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/upload', methods=['POST'])
def api_upload():
    if 'photo' not in request.files:
        return jsonify({"error": "請求中沒有照片"}), 400
    username = request.form.get('username')
    password = request.form.get('password')
    chromedriver_path = request.form.get('chromedriver_path')
    openai_api_key = request.form.get('openai_api_key')
    file = request.files['photo']
    caption = request.form.get('caption', '')
    if file.filename == '':
        return jsonify({"error": "沒有選擇文件"}), 400
    filename = secure_filename(file.filename)
    unique_filename = f"{uuid.uuid4()}_{filename}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
    try:
        file.save(filepath)
        bot = SessionManager.get_instance(username, password, chromedriver_path, comment_list=None, openai_api_key=openai_api_key)
        # 這裡可擴充 bot 上傳圖片功能
        # bot.upload_photo(filepath, caption)
        return jsonify({"message": "照片上傳成功（功能待擴充）"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)

@app.route('/status', methods=['GET'])
def api_status():
    return jsonify({
        'active_users': SessionManager.all_usernames(),
        'log': open('igbot.log').read()[-2000:] # 回傳最後 2000 字元日誌
    })

# ========== 主程式入口 ========== #
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(override=True)
    from config import comment_list, hashtags
    username = os.getenv("USERNAME")
    password = os.getenv("PASSWORD")
    chromedriver_path = os.getenv("CHROMEDRIVER_PATH")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    # 啟動 Flask API
    app.run(host='0.0.0.0', port=5005)
    # 或啟動多帳號排程
    # accounts = [
    #     {'username': username, 'password': password},
    #     # ... 其他帳號 ...
    # ]
    # multi_account_scheduler(accounts, hashtags, comment_list, chromedriver_path, openai_api_key, interval=600)
   