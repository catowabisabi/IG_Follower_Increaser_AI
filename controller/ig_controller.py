import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))  # 如果是兩層就加 '..', '..'
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import logging
import time
import random
from controller.class_cdp import CDPChromeClient # 控制
from utils.html_fetcher import HtmlSaver


from config import random_reply
import random




# 加入設計好的步驟
from utils.press_sequence import sequence_img_info_page, sequence_logout, sequence_login
from config import hashtags, search_keywords, random_reply


logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(asctime)s - %(message)s', datefmt='%H:%M:%S')
# --- 主要類別 ---



class IGController:
    def __init__(self, ws_url=None):
        if ws_url:
            self.ws_url = ws_url
            self.cdp_client = CDPChromeClient(ws_url=self.ws_url)
            logging.info(f"--- 連接到現有Broswer, WS URL 為 : {self.ws_url} ---")
        else:
            self.ws_url = None
            logging.info(f"--- 無法連接到現有Broswer, 沒有輸入 WS URL... ---")
            

    
    def start_new_broswer(self):
        try:
            if not CDPChromeClient.launch_chrome():
                return
                
            if not CDPChromeClient.wait_for_debug_port():
                return

            self.cdp_client = CDPChromeClient()
            if not self.cdp_client.connect_to_new_tab():
                return
            
            self.ws_url = self.cdp_client.get_ws_url()
            logging.info(f"--- 連接到新建立Broswer, WS URL 為 : {self.ws_url} ---")
            return True
        except Exception as e:
            logging.error(f"開啓新 Broswer 時發生意外錯誤: {e}", exc_info=True)

    def logout(self):
        self.cdp_client.press_button_sequence(sequence_logout, delay=2.5)


    def login(self):
        
        def get_credentials():
            username = os.environ.get('IG_USERNAME')
            password = os.environ.get('IG_PASSWORD')
            
            if not username or not password:
                logging.error("環境變數 IG_USERNAME 和/或 IG_PASSWORD 未設定。")
                logging.error("請在運行腳本前設定它們。")
                logging.error("範例: set IG_USERNAME=your_username")
                return None, None
                
            logging.info("憑證已成功從環境變數加載。")
            return username, password
    
        ig_user, ig_pass = get_credentials()
        if not ig_user:
            return
        if not self.ws_url:
            browser_created = self.start_new_broswer()
            if not browser_created:
                return
        
        try:
            # 去 IG
            
            self.cdp_client.navigate("https://www.instagram.com/")
            self.cdp_client.wait_for_element('button, div[role="button"]', timeout=5)
            self.cdp_client.press_button_sequence(sequence_login)
            #self.cdp_client.click_button_by_texts(sequence_login[0])
            # 如果是登入頁, 先登入
            username_selector = 'input[name="username"]'
            if self.cdp_client.wait_for_element(username_selector, timeout=20):
                logging.info("檢測到登入表單。正在進行登入。")
                
                password_selector = 'input[name="password"]'
                
                if not self.cdp_client.type_into_element(username_selector, ig_user): return
                time.sleep(0.5)
                if not self.cdp_client.type_into_element(password_selector, ig_pass): return
                time.sleep(1)

                logging.info("正在嘗試點擊登入按鈕...")
                login_clicked = self.cdp_client.click_login_button()

                if not login_clicked:
                    logging.error("找不到或無法點擊登入按鈕。")
                    # 如果有需要, 可以開黎用, 睇下個website係咩
                # debug_html = cdp_client.get_html()
                # cdp_client.save_html_to_file(debug_html)
                    return

                logging.info("登入請求已提交。正在等待導航...")
                time.sleep(5)
                
                success_selectors = [
                    "a[href='/']",
                    "svg[aria-label='Messenger']",
                    "img[data-testid='user-avatar']"
                ]
                
                login_success = False
                for selector in success_selectors:
                    if self.cdp_client.wait_for_element(selector, timeout=8):
                        login_success = True
                        logging.info(f"登入成功！檢測到元素 '{selector}'。")
                        break

                if not login_success:
                    logging.warning("登入可能失敗或需要額外步驟（例如 2FA）。")
            else:
                logging.info("未檢測到登入表單。假設已登入。")

            

            logging.info("等待 3 秒，讓彈出視窗有時間出現...")
            time.sleep(3)

            # 取消一開始的window
            self.cdp_client.click_button_by_texts(['保存信息', '儲存資料'])
            logging.info(f"已完成登入: {ig_user}")
        
        except Exception as e:
            logging.error(f"登入流程中發生意外錯誤: {e}", exc_info=True)
            
    def close(self):
        logging.info("--- 腳本結束。正在關閉連接 ---")
        time.sleep(2)
        self.cdp_client.close()
        logging.info("--- 連接中斷 ---")

    def search(self, keyword):
        self.cdp_client.click_element_by_aria_label(['首页'])
        self.cdp_client.click_element_by_aria_label(['搜索'])
        self.cdp_client.type_into_element_by_aria_label('搜索输入', keyword)
        time.sleep(2)
        if '#' in keyword:
            self.cdp_client.click_element_by_aria_label(['话题标签'])
        else:
            self.cdp_client.click_element_by_aria_label(['关键词'])

    def save_followed_user(self, username, file_path='followed_user.txt'):
        """
        如果 username 未存在於 txt 檔中，就將佢加一行到檔案，避免重覆紀錄。
        """
        if not username or not isinstance(username, str):
            logging.warning("⚠️ username 無效，無儲存")
            return

        try:
            # 嘗試讀檔案，搵下有冇記錄過
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    existing = set(line.strip() for line in f.readlines())
            else:
                existing = set()

            # 如果冇記錄，就寫入
            if username not in existing:
                with open(file_path, 'a', encoding='utf-8') as f:
                    f.write(username + '\n')
                logging.info(f"✅ 已儲存用戶名：{username}")
            else:
                logging.info(f"⚠️ 用戶名已存在：{username}，跳過儲存")

        except Exception as e:
            logging.error(f"❌ 儲存用戶名失敗：{e}")

    def save_html (self):
        fetcher = HtmlSaver()
        html = self.cdp_client.get_html()
        fetcher.save_html_to_file(html)

    def _is_not_followed(self, text = "关注"):
        found, count = self.cdp_client.check_text_exists(text)
        #if found:
        #    print(f"找到 {count} 次'{text}'文字")

        return found, count
    
    def _find_element_by_text(self, text="登入", tag_names=['button', 'a'] ):
        result = self.cdp_client.find_elements_by_text(text, tag_names=tag_names)
        if result['totalMatches'] > 0:
            logging.info(f"找到 {result['totalMatches']} 個 '{text}' in '{tag_names}'")
            return True
        else: 
            return False

    def _find_many_elements_by_text(self, keywords =["登入", "註冊", "用户", "密碼"], mode = 'any' ):
        
        result = self.cdp_client.check_multiple_keywords(keywords, mode=mode) # any or all
        if result['success']:
            if mode=='any':
                logging.info("頁面包含至少一個關鍵字")
            else:
                logging.info("頁面包含所有關鍵字")
            return True
        else:
            logging.info("頁面找不齊所需要的關鍵字")
            return False
    
    def _wait_for_text_appear(self, text = "載入完成", timeout=20):
        logging.info(f"等候 '{text}' 元素, 等候時間: {timeout} 秒...")
        return self.cdp_client.wait_for_text_appear(text, timeout=timeout)




    def follow_user_on_image_page(self):
        comment_to_use_this_time = random.choice(random_reply)
        sequence_follow = [
            ['关注'],
            ['赞'],
            ['评论'],
            {
                'method': 'add_comment',
                'param': comment_to_use_this_time
            },
            ['发布']
        ]
        if self._is_not_followed:
            self.cdp_client.press_button_sequence(sequence_follow, delay=2.5)
            self.cdp_client.press_button_sequence(sequence_img_info_page, delay=2.5)
            time.sleep(2)
            username = self.cdp_client.get_bk_components_heading()
            if username:
                logging.info(f"已 follow 用戶: {username[0]['text']}")
                self.cdp_client.click_button_by_texts(['关闭'])
                self.save_followed_user(username=username[0]['text'])
                return {'user':username}
            else:
                return {'user': 'user is null'}
        else: 
            time.sleep(1)
            return {'user': 'already followed'}
    
    def close_img(self):
        self.cdp_client.close_img()
    
    


    def scroll_down(self):
        self.cdp_client.scroll_down()

    def keep_scrolling_down(self,times=10, interval=1.5):
        self.cdp_client.scroll_down_loop(times=times, interval=interval)
    
    @staticmethod
    def my_callback(img_id, index):
        print(f"📸 已點擊 {img_id}，準備截圖或收集內容（第 {index + 1} 張）")
        # 例如：self.save_screenshot(f"screenshot_{index}.png")


    def click_all_images_one_by_one(self, callback = None, max_follow=6):
        self.cdp_client.click_all_images_one_by_one(delay=3, callback=callback, max_follow=max_follow)


 
    def img_page_following_and_comment(self):
        user = self.follow_user_on_image_page()
        self.cdp_client.close_img()
        if user == {'user': 'already followed'}:
            logging.info(f"之前已經 Follow 了這個用戶...")
            
            return False
        else:
            logging.info(f"已經 Follow 用戶 {user['user']}")
            return True


    
    def search_keywords(self, court = 5, click_court=5):

        random_keywords = random.sample(search_keywords, court)
        logging.info(f"--- Search Keywords {random_keywords} ---")
        
        for keywords in random_keywords:
            self.search(keywords)
            time.sleep(3)
            self.click_all_images_one_by_one(callback=lambda *args, **kwargs: self.img_page_following_and_comment())
            


            this_click_court = click_court

            time.sleep(5)
  

    

    


if __name__ == "__main__":
    ig = IGController(ws_url="ws://localhost:9222/devtools/page/F3F25069B29A7B9FA0C81ACF43B92FDE")
    
    
    #ig = IGController()
    #ig.login()

    # follow, comment, and like one by one

    ig._find_element_by_text(text="关注", tag_names=['button', 'a'])
    #ig.search_keywords()
