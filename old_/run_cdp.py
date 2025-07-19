import pyautogui
import time
import win32api
import win32gui
import subprocess
import os

import requests
import json
from websocket import create_connection
import datetime


class CDPChromeClient:

    @staticmethod
    def wait_debug_port(host='localhost', port=9222, timeout=15):
        url = f"http://{host}:{port}/json"
        for i in range(timeout):
            try:
                res = requests.get(url)
                if res.status_code == 200:
                    print(f"[CDP] Debug port ready after {i} seconds")
                    return True
            except:
                pass
            print(f"[CDP] Waiting for debug port... {i+1}s")
            time.sleep(1)
        print("[CDP] Timeout waiting for debug port")
        return False

    def __init__(self, host='localhost', port=9222, username=None, password=None):
        self.host = host
        self.port = port
        self.ws = None
        self.tab_info = None
        self.ig_user_id = username
        self.ig_user_pw = password

    def connect(self, url="https://www.instagram.com/"):
        # 1. 新開一個 tab（PUT）
        resp = requests.put(f"http://{self.host}:{self.port}/json/new")
        print("[DEBUG] /json/new 回傳：", resp.text)
        new_tab = resp.json()
        self.tab_info = new_tab
        ws_url = self.tab_info["webSocketDebuggerUrl"]
        self.ws = create_connection(ws_url)
        print(f"[CDP] Connected to new tab: {self.tab_info.get('url')}")
        # 2. 先啟用 Page domain
        self._send("Page.enable")
        # 3. 跳轉
        self._send("Page.navigate", {"url": url})
        # 4. 等 2 秒再等事件
        time.sleep(2)

    def navigate(self, url):
        print(f"Navigating to {url}")
        result = self._send("Page.navigate", {"url": url})
        print(result)
        time.sleep(2)
        return result
    
    def enable_page(self):
        print('Enabled Page')
        self._send("Page.enable")
        time.sleep(2)

    def _send(self, method, params=None, _id=1):
        payload = {
            "id": _id,
            "method": method,
            "params": params or {}
        }
        self.ws.send(json.dumps(payload))
        while True:
            result = json.loads(self.ws.recv())
            # 只回傳 id 對得上的回應
            if result.get("id") == _id:
                return result
            # 事件就略過

    def get_html(self):
        self._send("DOM.enable")  # 記得 enable DOM domain

        doc = self._send("DOM.getDocument")
        print("[DEBUG] DOM.getDocument response:", doc)

        if 'result' not in doc or 'root' not in doc['result']:
            raise Exception(f"[CDP] Invalid getDocument response: {doc}")

        root_id = doc['result']['root']['nodeId']
        html = self._send("DOM.getOuterHTML", {"nodeId": root_id})
        return html['result']['outerHTML']

    def wait_for_load(self, timeout=30):
        """改進的等待頁面加載方法"""
        print(f"[CDP] Waiting for page load (timeout: {timeout}s)")
        self._send("Page.enable")
        start = time.time()
        
        while time.time() - start < timeout:
            try:
                remaining_time = timeout - (time.time() - start)
                self.ws.settimeout(min(remaining_time, 1))  # 最多等1秒
                msg = json.loads(self.ws.recv())
                print(f"[DEBUG] 收到事件：{msg.get('method', 'unknown')}")
                
                if msg.get("method") == "Page.loadEventFired":
                    print("[CDP] Page load event fired")
                    return True
                elif msg.get("method") == "Page.domContentEventFired":
                    print("[CDP] DOM content loaded")
                    # 可以選擇在這裡就返回，不等 loadEventFired
                    
            except Exception as e:
                # 超時或其他錯誤，繼續等待
                pass
        
        print(f"[CDP] Timeout waiting for page load after {timeout}s")
        return False

    def wait_for_ready_state(self, timeout=30):
        """替代方法：檢查頁面的 readyState"""
        print(f"[CDP] Checking page ready state (timeout: {timeout}s)")
        start = time.time()
        
        while time.time() - start < timeout:
            try:
                # 啟用 Runtime domain
                self._send("Runtime.enable")
                
                # 執行 JavaScript 檢查 document.readyState
                result = self._send("Runtime.evaluate", {
                    "expression": "document.readyState",
                    "returnByValue": True
                })
                
                if result.get('result', {}).get('result', {}).get('value') == 'complete':
                    print("[CDP] Page ready state is 'complete'")
                    return True
                elif result.get('result', {}).get('result', {}).get('value') == 'interactive':
                    print("[CDP] Page ready state is 'interactive'")
                    # 可以選擇在這裡就返回，或繼續等待 complete
                    
                time.sleep(1)
                
            except Exception as e:
                print(f"[CDP] Error checking ready state: {e}")
                time.sleep(1)
        
        print(f"[CDP] Timeout checking ready state after {timeout}s")
        return False

    def check_page_loaded(self):
        """簡單檢查頁面是否已加載完成"""
        try:
            self._send("Runtime.enable")
            result = self._send("Runtime.evaluate", {
                "expression": "document.readyState === 'complete' && document.body !== null",
                "returnByValue": True
            })
            
            is_loaded = result.get('result', {}).get('result', {}).get('value', False)
            print(f"[CDP] Page loaded check: {is_loaded}")
            return is_loaded
        except Exception as e:
            print(f"[CDP] Error checking if page loaded: {e}")
            return False

    def has_login_form(self):
        """檢查是否存在登入表單"""
        try:
            self._send("Runtime.enable")
            
            # 使用 XPath 查找登入表單元素
            xpath_expression = '//*[@id="loginForm"]/div[1]/div[1]/div/label/span'
            js_code = f"""
            (function() {{
                function getElementByXpath(path) {{
                    return document.evaluate(path, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                }}
                
                var element = getElementByXpath('{xpath_expression}');
                return element !== null;
            }})()
            """
            
            result = self._send("Runtime.evaluate", {
                "expression": js_code,
                "returnByValue": True
            })
            
            has_form = result.get('result', {}).get('result', {}).get('value', False)
            print(f"[CDP] Login form exists: {has_form}")
            return has_form
            
        except Exception as e:
            print(f"[CDP] Error checking login form: {e}")
            return False

    def has_login_form_alternative(self):
        """替代方法：檢查登入表單（使用 querySelector）"""
        try:
            self._send("Runtime.enable")
            
            # 使用 CSS selector 作為替代方法
            js_code = """
            (function() {
                // 方法1：檢查 loginForm ID
                var loginForm = document.getElementById('loginForm');
                if (loginForm) {
                    var span = loginForm.querySelector('div:first-child div:first-child div label span');
                    if (span) return true;
                }
                
                // 方法2：檢查常見的登入表單元素
                var usernameInput = document.querySelector('input[name="username"]');
                var passwordInput = document.querySelector('input[name="password"]');
                var loginButton = document.querySelector('button[type="submit"]');
                
                return usernameInput && passwordInput && loginButton;
            })()
            """
            
            result = self._send("Runtime.evaluate", {
                "expression": js_code,
                "returnByValue": True
            })
            
            has_form = result.get('result', {}).get('result', {}).get('value', False)
            print(f"[CDP] Login form exists (alternative): {has_form}")
            return has_form
            
        except Exception as e:
            print(f"[CDP] Error checking login form (alternative): {e}")
            return False

    def login_to_instagram(self):
        """自動登入 Instagram"""
        if not self.ig_user_id or not self.ig_user_pw:
            print("[ERROR] 缺少帳號或密碼資訊")
            return False
        
        try:
            print(f"[INFO] 開始自動登入，帳號：{self.ig_user_id}")
            self._send("Runtime.enable")
            
            # 等待登入表單完全加載
            time.sleep(2)
            
            # 填入帳號
            print("[INFO] 填入帳號...")
            username_script = f"""
            (function() {{
                var usernameInput = document.querySelector('input[name="username"]');
                if (usernameInput) {{
                    usernameInput.value = '{self.ig_user_id}';
                    usernameInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    usernameInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    return true;
                }}
                return false;
            }})()
            """
            
            result = self._send("Runtime.evaluate", {
                "expression": username_script,
                "returnByValue": True
            })
            
            if not result.get('result', {}).get('result', {}).get('value', False):
                print("[ERROR] 無法找到帳號輸入框")
                return False
            
            time.sleep(1)
            
            # 填入密碼
            print("[INFO] 填入密碼...")
            password_script = f"""
            (function() {{
                var passwordInput = document.querySelector('input[name="password"]');
                if (passwordInput) {{
                    passwordInput.value = '{self.ig_user_pw}';
                    passwordInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    passwordInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    return true;
                }}
                return false;
            }})()
            """
            
            result = self._send("Runtime.evaluate", {
                "expression": password_script,
                "returnByValue": True
            })
            
            if not result.get('result', {}).get('result', {}).get('value', False):
                print("[ERROR] 無法找到密碼輸入框")
                return False
            
            time.sleep(1)
            
            # 點擊登入按鈕
            print("[INFO] 點擊登入按鈕...")
            login_script = """
            (function() {
                // 嘗試多種方法找到登入按鈕
                var loginButton = document.querySelector('button[type="submit"]');
                if (!loginButton) {
                    loginButton = document.querySelector('form button');
                }
                if (!loginButton) {
                    loginButton = document.querySelector('div[role="button"]');
                }
                if (!loginButton) {
                    // 尋找包含 "登入" 或 "Log In" 文字的按鈕
                    var buttons = document.querySelectorAll('button');
                    for (var i = 0; i < buttons.length; i++) {
                        var text = buttons[i].textContent.trim().toLowerCase();
                        if (text.includes('log in') || text.includes('登入') || text.includes('login')) {
                            loginButton = buttons[i];
                            break;
                        }
                    }
                }
                
                if (loginButton) {
                    loginButton.click();
                    return true;
                }
                return false;
            })()
            """
            
            result = self._send("Runtime.evaluate", {
                "expression": login_script,
                "returnByValue": True
            })
            
            if not result.get('result', {}).get('result', {}).get('value', False):
                print("[ERROR] 無法找到登入按鈕")
                return False
            
            print("[INFO] 登入表單已提交，等待處理...")
            time.sleep(5)  # 等待登入處理
            
            # 檢查是否成功登入（檢查是否還有登入表單）
            if not self.has_login_form() and not self.has_login_form_alternative():
                print("[SUCCESS] 登入成功！")
                return True
            else:
                print("[WARN] 登入可能失敗或需要額外驗證")
                return False
            
        except Exception as e:
            print(f"[ERROR] 登入過程中發生錯誤：{e}")
            return False

    def wait_for_login_completion(self, timeout=30):
        """等待登入完成"""
        print(f"[INFO] 等待登入完成（超時：{timeout}秒）")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # 檢查是否還有登入表單
                if not self.has_login_form() and not self.has_login_form_alternative():
                    print("[INFO] 登入表單已消失，登入可能成功")
                    return True
                
                # 檢查是否有錯誤信息
                error_check = """
                (function() {
                    var errorElements = document.querySelectorAll('[role="alert"], .error, .alert');
                    for (var i = 0; i < errorElements.length; i++) {
                        if (errorElements[i].textContent.trim() !== '') {
                            return errorElements[i].textContent.trim();
                        }
                    }
                    return null;
                })()
                """
                
                result = self._send("Runtime.evaluate", {
                    "expression": error_check,
                    "returnByValue": True
                })
                
                error_msg = result.get('result', {}).get('result', {}).get('value')
                if error_msg:
                    print(f"[ERROR] 登入錯誤信息：{error_msg}")
                    return False
                
                time.sleep(2)
                
            except Exception as e:
                print(f"[ERROR] 檢查登入狀態時發生錯誤：{e}")
                time.sleep(2)
        
        print("[WARN] 等待登入完成超時")
        return False

    def close(self):
        if self.ws:
            self.ws.close()
            print("[CDP] Connection closed")


class WinController:

    @staticmethod
    def launch_chrome_debug():
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        user_data_dir = r"C:\ChromeDebug1"
        cmd = f'"{chrome_path}" --remote-debugging-port=9222 --remote-allow-origins=* --user-data-dir="{user_data_dir}"'
        subprocess.Popen(cmd)
        time.sleep(2)

    @staticmethod
    def change_en():
        ENG_US = '00000409'  # HKL 字串格式，英文美式
        # load keyboard layout 並直接 activate (flag 1 表示 KLF_ACTIVATE)
        hkl = win32api.LoadKeyboardLayout(ENG_US, 1)
        time.sleep(0.5)

    @staticmethod
    def minimize_window():
        WinController.maximize_window()
        time.sleep(1)
        WinController.right_click_left_top_window()
        pyautogui.press('n')
        time.sleep(0.2)

    @staticmethod
    def dock_window_to_left():
        WinController.maximize_window()
        time.sleep(1)
        pyautogui.hotkey('win', 'left')
        time.sleep(2)

    @staticmethod
    def select_left_top_window():
        pyautogui.click(x=700, y=10) 
        time.sleep(1)

    @staticmethod
    def right_click_left_top_window():
        pyautogui.rightClick(x=700, y=10)
        time.sleep(1)

    @staticmethod
    def maximize_window():
        pyautogui.keyDown('win')
        for _ in range(6):
            pyautogui.press('up')
            time.sleep(1)
        pyautogui.keyUp('win')
        time.sleep(1)
        pyautogui.hotkey('win', 'left')
        time.sleep(2)
        WinController.right_click_left_top_window()
        pyautogui.press('x')
        time.sleep(2)

    @staticmethod
    def open_software(software_name="chrome"):
        pyautogui.press('win')
        time.sleep(2)
        pyautogui.write(software_name, interval=0.1)
        time.sleep(1)
        pyautogui.press('enter')
        time.sleep(3)
        WinController.dock_window_to_left()
        time.sleep(1)
    
    @staticmethod
    def close_software():
        pyautogui.hotkey('alt', 'f4')
        time.sleep(0.2)

    @staticmethod
    def go_url(input_url='https://www.instagram.com/'):
        url = input_url + "/"
        pyautogui.write(url, interval=0.05)
        pyautogui.press('backspace')
        time.sleep(1)
        pyautogui.press('enter')
        time.sleep(3)


def save_html_to_output_folder(html):
    output_dir = 'output'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    now = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'instagram_{now}.html'
    filepath = os.path.join(output_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"[INFO] HTML 已儲存到 {filepath}")


if __name__ == "__main__":
    print('Start')

    wc = WinController()
    
    wc.change_en()
    wc.launch_chrome_debug()
    
    if CDPChromeClient.wait_debug_port():
        print('連接到 Debug Port 9222...')
        
        cdp = CDPChromeClient()
        cdp.connect("https://www.instagram.com/")
        cdp.enable_page()
        cdp.navigate("https://www.instagram.com/")
        
        print("[INFO] 等待頁面加載...")
        time.sleep(5)  # 給頁面一些時間加載
        
        # 嘗試多種方法等待頁面加載
        load_success = False
        
        # 方法1：等待 loadEventFired 事件
        print("[INFO] 方法1：等待 loadEventFired 事件")
        if cdp.wait_for_load(timeout=15):
            load_success = True
        
        # 方法2：如果方法1失敗，檢查 readyState
        if not load_success:
            print("[INFO] 方法2：檢查 document.readyState")
            if cdp.wait_for_ready_state(timeout=15):
                load_success = True
        
        # 方法3：如果前兩種方法都失敗，簡單檢查頁面狀態
        if not load_success:
            print("[INFO] 方法3：簡單檢查頁面狀態")
            time.sleep(3)  # 再等一下
            if cdp.check_page_loaded():
                load_success = True
        
        # 無論如何都嘗試獲取 HTML
        if load_success:
            print("[INFO] 頁面加載成功，獲取 HTML")
        else:
            print("[WARN] 頁面加載狀態不確定，仍嘗試獲取 HTML")
        
        # 檢查是否有登入表單
        print("[INFO] 檢查登入表單...")
        if cdp.has_login_form():
            print("[INFO] ✓ 找到登入表單！")
        else:
            print("[INFO] 使用替代方法檢查登入表單...")
            if cdp.has_login_form_alternative():
                print("[INFO] ✓ 找到登入表單（替代方法）！")
            else:
                print("[INFO] ✗ 未找到登入表單")
        
        try:
            html = cdp.get_html()
            save_html_to_output_folder(html)
            print("[INFO] 成功獲取並保存 HTML")
        except Exception as e:
            print(f"[ERROR] 獲取 HTML 失敗：{e}")
            print("[INFO] 等待 3 秒後重試...")
            time.sleep(3)
            try:
                html = cdp.get_html()
                save_html_to_output_folder(html)
                print("[INFO] 重試成功獲取並保存 HTML")
            except Exception as e2:
                print(f"[ERROR] 重試後仍然失敗：{e2}")
        
        cdp.close()
        
    else:
        print("[ERROR] Debug port not ready, exit")