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

class InstagramBot:
    def __init__(self, username=None, password=None, chromedriver_path=None, comment_list=None, openai_api_key=None):
        self.username = username
        self.password = password
        self.comment_list = comment_list
        self.openai_api_key = openai_api_key
        self.new_followed = []
        self.prev_user_list = []
        self.liked = 0
        self.followed = 0
        self.commented = 0
        if chromedriver_path:
            service = Service(chromedriver_path)
            self.driver = webdriver.Chrome(service=service)
        else:
            self.driver = webdriver.Chrome()
        if openai_api_key:
            openai.api_key = openai_api_key
        self.init_database()

    def wait(self, seconds=2):
        time.sleep(seconds)

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

    def login(self):
        print("[Login] Navigating to login page...")
        self.driver.get("https://www.instagram.com/accounts/login/")
        self.wait(5)
        print("[Login] Entering username and password")
        self.driver.find_element(By.NAME, 'username').send_keys(self.username)
        self.wait()
        self.driver.find_element(By.NAME, 'password').send_keys(self.password)
        self.wait()
        print("[Login] Submitting login form")
        self.driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        self.wait(8)
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

    def explore_hashtags(self, hashtags, max_posts_per_tag=10):
        for tag in hashtags:
            print(f"\n[Exploring Hashtag] #{tag}")
            self.driver.get(f"https://www.instagram.com/explore/tags/{tag}/")
            self.wait(5)
            print(f"[Action] Loaded hashtag page for #{tag}")

            try:
                print("[Search] Looking for first post thumbnail")
                first_thumb = self.driver.find_element(By.XPATH, "//section/main//a")
                first_thumb.click()
                print(f"[Success] Clicked on first post for #{tag}")
                self.wait(5)
            except:
                print("[Error] Failed to find or click first post")
                continue

            for i in range(max_posts_per_tag):
                print(f"\n[Post #{i+1}] Processing post")
                try:
                    print("[Search] Looking for username link")
                    user = self.driver.find_element(By.XPATH, "//header//a").text
                    self.wait()
                    print(f"[Found] Post owner: {user}")
                    if user not in self.prev_user_list:
                        try:
                            follow_btn = self.driver.find_element(By.XPATH, "//header//button")
                            self.wait()
                            print(f"[Search] Found follow button: {follow_btn.text}")
                            if follow_btn.text.lower() in ['follow', 'follow back', '追蹤']:
                                follow_btn.click()
                                print(f"[Action] Followed {user}")
                                self.wait()
                                self.new_followed.append(user)
                                self.followed += 1

                                try:
                                    like_btn = self.driver.find_element(By.XPATH, "//section/span/button")
                                    like_btn.click()
                                    self.liked += 1
                                    print(f"[Action] Liked post from {user}")
                                    self.wait()
                                except:
                                    print("[Error] Like button not found")

                                if self.comment_list:
                                    try:
                                        comment = random.choice(self.comment_list)
                                        self.leave_comment(comment)
                                        print(f"[Action] Commented on {user}'s post: {comment}")
                                        self.wait()
                                    except:
                                        print("[Error] Failed to comment")
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
                    next_btn.click()
                    print("[Action] Attempting to click Next button")
                    self.wait(3)
                except:
                    print("[End] Next button not found, ending loop")
                    break

    def leave_comment(self, text):
        try:
            comment_area = self.driver.find_element(By.XPATH, "//textarea")
            comment_area.click()
            self.wait()
            comment_area.send_keys(text)
            self.wait()
            comment_area.send_keys(Keys.ENTER)
            self.commented += 1
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
    import os
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
    bot.load_previous_users()
    bot.explore_hashtags(hashtags, max_posts_per_tag=5)
    bot.gpt_reply_to_top_comments()
    bot.save_followed()
    bot.quit() #"""