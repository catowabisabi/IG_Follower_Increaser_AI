
from dotenv import load_dotenv
load_dotenv(override=True)
import time
import subprocess
import os
import requests
import json
from websocket import create_connection
import datetime
import json
import logging

# --- 設定 ---
# 設定基本日誌記錄，以查看腳本的進度和潛在問題。
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(asctime)s - %(message)s', datefmt='%H:%M:%S')

# --- 主要類別 ---

class CDPChromeClient:

    def __init__(self, host='localhost', port=9222):
        self.host = host
        self.port = port
        self.ws = None
        self.tab_info = None
        self._message_id_counter = 0

    @staticmethod
    def launch_chrome(user_data_dir=r"C:\ChromeDebugTemp"):
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        if not os.path.exists(chrome_path):
            logging.error(f"找不到 Chrome 執行檔於: {chrome_path}")
            return False
        
        # 啟用遠端偵錯的指令。
        # --remote-allow-origins=* 允許來自任何來源的連接。
        cmd = [
            chrome_path,
            f"--remote-debugging-port=9222",
            f"--user-data-dir={user_data_dir}",
            "--remote-allow-origins=*",
            "about:blank" # 從一個空白頁面開始，以保持乾淨
        ]
        logging.info("以偵錯模式啟動 Chrome...")
        subprocess.Popen(cmd)
        return True
    
    @staticmethod
   

    def click_button_by_texts(cdp_client, texts):
        """
        傳入 cdp_client 物件同一個文字 list，幫你自動執行點擊第一個完全匹配嘅按鈕。
        回傳點擊結果或 False。
        """
        texts_js_array = json.dumps(texts)  # 轉成 JS 陣列字串
        js_code = f"""
        (function() {{
            const texts = {texts_js_array};
            const elements = document.querySelectorAll('button, div[role="button"], a');
            for (const text of texts) {{
                for (const el of elements) {{
                    const elText = (el.innerText || el.textContent || '').trim();
                    if (elText === text) {{
                        el.style.border = '2px solid red';
                        el.style.backgroundColor = 'yellow';
                        el.click();
                        return `Clicked button with exact text: ${text}`;
                    }}
                }}
            }}
            return false;
        }})()
        """
        result = cdp_client.execute_script(js_code)
        print(f"Click attempt result: {result}")
        return result


    @staticmethod
    def wait_for_debug_port(host='localhost', port=9222, timeout=20):
        logging.info(f"正在等待 Chrome 偵錯端口 {port} 就緒...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # /json/version 端點是檢查端口是否打開的可靠方法。
                response = requests.get(f"http://{host}:{port}/json/version")
                if response.status_code == 200:
                    logging.info(f"偵錯端口在 {int(time.time() - start_time)} 秒後啟用。")
                    return True
            except requests.ConnectionError:
                time.sleep(1) # 重試前等待一秒
        logging.error(f"超時：偵錯端口 {port} 在 {timeout} 秒內未就緒。")
        return False

    def connect_to_new_tab(self):
        try:
            # 通過 HTTP 端點創建一個新分頁。
            resp = requests.put(f"http://{self.host}:{self.port}/json/new")
            resp.raise_for_status()
            self.tab_info = resp.json()
            ws_url = self.tab_info["webSocketDebuggerUrl"]
            logging.info(f"CDP 客戶端 WS URL: {ws_url}")
            
            # 建立到新分頁的 WebSocket 連接。
            self.ws = create_connection(ws_url)
            logging.info(f"CDP 客戶端已連接到新分頁: {self.tab_info.get('id')}")
            return True
        except requests.RequestException as e:
            logging.error(f"無法創建或連接到新分頁: {e}")
        except Exception as e:
            logging.error(f"連接期間發生意外錯誤: {e}")
        return False

    def _send(self, method, params=None):
        self._message_id_counter += 1
        payload = {
            "id": self._message_id_counter,
            "method": method,
            "params": params or {}
        }
        self.ws.send(json.dumps(payload))
        
        # 等待與發送的消息 ID 對應的特定回應。
        while True:
            try:
                message = json.loads(self.ws.recv())
                if message.get("id") == self._message_id_counter:
                    if 'error' in message:
                        logging.warning(f"CDP 指令 '{method}' 返回錯誤: {message['error']['message']}")
                    return message.get('result')
            except json.JSONDecodeError:
                logging.error("從 WebSocket 解碼 JSON 失敗。")
                continue
            except Exception as e:
                logging.error(f"接收 WebSocket 消息時出錯: {e}")
                return None

    def navigate(self, url):
        logging.info(f"正在導航至 {url}...")
        self._send("Page.enable")
        self._send("Page.navigate", {"url": url})

    def wait_for_element(self, selector, timeout=15):
        logging.info(f"正在等待元素 '{selector}' 出現...")
        start_time = time.time()
        js_expression = f"document.querySelector('{selector}')"
        
        while time.time() - start_time < timeout:
            result = self._send("Runtime.evaluate", {"expression": js_expression})
            # 如果結果不為 null，則認為元素已找到。
            if result and result.get('result', {}).get('objectId'):
                logging.info(f"元素 '{selector}' 已找到。")
                return True
            time.sleep(0.5)
            
        logging.warning(f"超時：元素 '{selector}' 在 {timeout} 秒內未出現。")
        return False
        
    def execute_script(self, js_code, timeout=10):
        """執行一段 JavaScript 並返回結果。"""
        result = self._send("Runtime.evaluate", {"expression": js_code, "awaitPromise": True, "returnByValue": True})
        #print("Script result:", result)
        if result and 'result' in result:
            return result.get('result', {}).get('value')
        return None

    def type_into_element(self, selector, text):
        logging.info(f"正在將文本輸入到 '{selector}'...")

        escaped_text = text.replace('\\', '\\\\').replace("'", "\\'")
        js_code = f"""
            (function() {{
                const el = document.querySelector('{selector}');
                if (!el) return false;
                
                const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                nativeInputValueSetter.call(el, '{escaped_text}');
                
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                return true;
            }})()
        """
        result = self.execute_script(js_code)
        if not result:
            logging.error(f"無法輸入到元素 '{selector}'。")
            return False
        return True


    def get_html(self):
        logging.info("正在檢索頁面 HTML...")
        try:
            doc = self._send("DOM.getDocument")
            if not doc or 'root' not in doc:
                raise Exception("無效的 getDocument 回應")
            root_id = doc['root']['nodeId']
            html_data = self._send("DOM.getOuterHTML", {"nodeId": root_id})
            return html_data['outerHTML']
        except Exception as e:
            logging.error(f"獲取 HTML 失敗: {e}")
            return None

    def close(self):
        if self.ws:
            self.ws.close()
            logging.info("CDP WebSocket 連接已關閉。")
        if self.tab_info:
            try:
                # 發送指令關閉分頁。
                requests.get(f"http://{self.host}:{self.port}/json/close/{self.tab_info['id']}")
                logging.info(f"已關閉 Chrome 分頁: {self.tab_info['id']}")
            except requests.RequestException as e:
                logging.warning(f"無法關閉 Chrome 分頁: {e}")


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

def save_html_to_file(html_content):
    if not html_content:
        logging.warning("HTML 內容為空，跳過保存。")
        return
        
    output_dir = 'output'
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'instagram_page_{timestamp}.html'
    filepath = os.path.join(output_dir, filename)
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logging.info(f"HTML 已成功保存至: {filepath}")
    except IOError as e:
        logging.error(f"保存 HTML 文件失敗: {e}")

def main():
    logging.info("--- 啟動 Instagram 自動化腳本 ---")
    
    # 1. 獲取憑證
    ig_user, ig_pass = get_credentials()
    if not ig_user:
        return # 如果未設定憑證則停止

    # 2. 啟動 Chrome 並連接 CDP 客戶端
    if not CDPChromeClient.launch_chrome():
        return
        
    if not CDPChromeClient.wait_for_debug_port():
        return

    cdp_client = CDPChromeClient()
    if not cdp_client.connect_to_new_tab():
        return

    try:
        # 3. 導航到 Instagram
        cdp_client.navigate("https://www.instagram.com/")
        
        # 4. 檢測登入表單並執行登入
        username_selector = 'input[name="username"]'
        if cdp_client.wait_for_element(username_selector, timeout=20):
            logging.info("檢測到登入表單。正在進行登入。")
            
            password_selector = 'input[name="password"]'
            
            if not cdp_client.type_into_element(username_selector, ig_user): return
            time.sleep(0.5)
            if not cdp_client.type_into_element(password_selector, ig_pass): return
            time.sleep(1)

            # 改進的登入按鈕點擊邏輯
            logging.info("正在嘗試點擊登入按鈕...")
            login_script = """
(function() {
    const form = document.querySelector('form');
    if (!form) return '❌ 找不到登入表單';

    const btn = form.querySelector('button[type="submit"], input[type="submit"]');
    if (!btn) return '❌ 表單中找不到提交按鈕';

    const event = new MouseEvent('click', {
        view: window,
        bubbles: true,
        cancelable: true
    });
    btn.dispatchEvent(event);

    return `✅ 成功點擊登入按鈕：${btn.innerText || '[無文字]'}`;
})()
"""

            login_clicked = cdp_client.execute_script(login_script)

            if not login_clicked:
                logging.error("找不到或無法點擊登入按鈕。")
                # 調試：保存當前HTML以檢查頁面結構
                debug_html = cdp_client.get_html()
                save_html_to_file(debug_html)
                return

            logging.info("登入請求已提交。正在等待導航...")

            if login_clicked:
                logging.info("登入請求已提交，等待 5 秒...")
                time.sleep(5)  # 給頁面足夠時間加載
            
            # 使用多個可能的選擇器來確認登入成功，使其更穩健
            # 例如：個人資料圖標、私信圖標或主頁圖標
            success_selectors = [
                "a[href='/']",                  # 主頁圖標
                "svg[aria-label='Messenger']",  # 私信圖標
                "img[data-testid='user-avatar']" # 用戶頭像
            ]
            
            login_success = False
            for selector in success_selectors:
                if cdp_client.wait_for_element(selector, timeout=8):
                    login_success = True
                    logging.info(f"登入成功！檢測到元素 '{selector}'。")
                    break # 找到任何一個就代表成功

            if not login_success:
                logging.warning("登入可能失敗或需要額外步驟（例如 2FA）。")
        else:
            logging.info("未檢測到登入表單。假設已登入。")

        # 5. 處理潛在的「儲存資訊」和「開啟通知」彈出視窗
        logging.info("等待 5 秒，讓彈出視窗有時間出現...")
        time.sleep(5)
        
        # 使用更通用的方法點擊包含特定文本的按鈕
        def click_button_by_text(text):
            logging.info(f"正在嘗試點擊包含文字 '{text}' 的按鈕...")
            # 使用 XPath 尋找包含完全匹配文本的按鈕或可點擊的 div
            js_script = f"""
                (function() {{
                    let xpath = `//button[text()='{text}'] | //div[@role="button" and text()='{text}']`;
                    let element = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                    if (element) {{
                        element.click();
                        return true;
                    }}
                    return false;
                }})()
            """
            return cdp_client.execute_script(js_script)

        # 嘗試點擊中英文的 "Not Now"
        if not click_button_by_text('Not Now'):
             click_button_by_text('稍後再說')
        time.sleep(2)
        if not click_button_by_text('Not Now'):
             click_button_by_text('稍後再說')

        # 6. 獲取並保存最終的 HTML
        html = cdp_client.get_html()
        save_html_to_file(html)

    except Exception as e:
        logging.error(f"主流程中發生意外錯誤: {e}", exc_info=True)
    finally:
        # 7. 清理
        logging.info("--- 腳本結束。正在關閉連接。 ---")
        #cdp_client.close()


if __name__ == "__main__":
    main()
