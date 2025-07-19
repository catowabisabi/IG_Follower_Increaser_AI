import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))  # 如果是兩層就加 '..', '..'
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import logging
import time
from controller.class_cdp import CDPChromeClient # 控制
from utils.html_fetcher import HtmlSaver

# 加入設計好的步驟
from utils.press_sequence import follow_sequence, img_info_page_sequence, sequence_logout


logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(asctime)s - %(message)s', datefmt='%H:%M:%S')
# --- 主要類別 ---




    


class IGController:
    def __init__(self, ws_url=None):
        if ws_url:
            self.ws_url = ws_url
            self.cdp_client = CDPChromeClient(ws_url=self.ws_url)
            logging.info(f"--- 連接到現有Broswer, WS URL 為 : {self.ws_url} ---")
        else:
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
        
        browser_created = self.start_new_broswer()
        if not browser_created:
            return
        
        try:
            # 去 IG
            self.cdp_client.navigate("https://www.instagram.com/")
            
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
                login_clicked = self.cdp_client.click_login_button(self.cdp_client)

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
        self.cdp_client.click_element_by_aria_label(['关键词'])
    
    def save_html (self):
        fetcher = HtmlSaver()
        html = self.cdp_client.get_html()
        fetcher.save_html_to_file(html)
        
    


if __name__ == "__main__":
    ig = IGController(ws_url="ws://localhost:9222/devtools/page/B26E2C5BFC98B0A0B62C7A436014D0A3")
    ig.logout()