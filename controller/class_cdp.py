from dotenv import load_dotenv
load_dotenv(override=True)
import time
import subprocess
import os
import requests
import json
from websocket import create_connection
import datetime
import logging
import random
from config import search_keywords
# --- 設定 ---
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(asctime)s - %(message)s', datefmt='%H:%M:%S')

# --- 主要類別 ---

class CDPChromeClient:

    def __init__(self, host='localhost', port=9222, ws_url = None):
        self.host = host
        self.port = port
        self.ws = ws_url
        if ws_url:
            self.ws = create_connection(ws_url)
        self.tab_info = None
        self._message_id_counter = 0

    @staticmethod
    def launch_chrome(user_data_dir=r"C:\ChromeDebugTemp"):
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        if not os.path.exists(chrome_path):
            logging.error(f"找不到 Chrome 執行檔於: {chrome_path}")
            return False
        
        cmd = [
            chrome_path,
            f"--remote-debugging-port=9222",
            f"--user-data-dir={user_data_dir}",
            "--remote-allow-origins=*",
           # "about:blank"
        ]
        logging.info("以偵錯模式啟動 Chrome...")
        subprocess.Popen(cmd)
        return True

    @staticmethod
    def wait_for_debug_port(host='localhost', port=9222, timeout=20):
        logging.info(f"正在等待 Chrome 偵錯端口 {port} 就緒...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"http://{host}:{port}/json/version")
                if response.status_code == 200:
                    logging.info(f"偵錯端口在 {int(time.time() - start_time)} 秒後啟用。")
                    return True
            except requests.ConnectionError:
                time.sleep(1)
        logging.error(f"超時：偵錯端口 {port} 在 {timeout} 秒內未就緒。")
        return False
    
    def click_login_button(self):
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
        login_clicked = self.execute_script(login_script)
        return login_clicked

    def connect_to_new_tab_0(self):
        try:
            resp = requests.put(f"http://{self.host}:{self.port}/json/new")
            resp.raise_for_status()
            self.tab_info = resp.json()
            ws_url = self.tab_info["webSocketDebuggerUrl"]
            logging.info(f"CDP 客戶端 WS URL: {ws_url}")
            
            self.ws = create_connection(ws_url)
            logging.info(f"CDP 客戶端已連接到新分頁: {self.tab_info.get('id')}")
            return True
        except requests.RequestException as e:
            logging.error(f"無法創建或連接到新分頁: {e}")
        except Exception as e:
            logging.error(f"連接期間發生意外錯誤: {e}")
        return False
    
    def connect_to_new_tab(self):
        try:
            tabs = requests.get(f"http://{self.host}:{self.port}/json").json()
            self.tab_info = tabs[0]  # 用第一個已存在的 tab
            self.ws_url = self.tab_info["webSocketDebuggerUrl"]
            logging.info(f"CDP 客戶端 WS URL: {self.ws_url}")
            
            self.ws = create_connection(self.ws_url)
            logging.info(f"CDP 客戶端已連接到既有分頁: {self.tab_info.get('id')}")
            return True
        except Exception as e:
            logging.error(f"連接分頁時出錯: {e}")
        return False
    
    def get_ws_url(self):
        logging.info(f"提取 CDP 客戶端 WS URL: {self.ws_url}")
        return self.ws_url
        


    def _send(self, method, params=None):
        self._message_id_counter += 1
        payload = {
            "id": self._message_id_counter,
            "method": method,
            "params": params or {}
        }
        self.ws.send(json.dumps(payload))
        
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
            if result and result.get('result', {}).get('objectId'):
                logging.info(f"元素 '{selector}' 已找到。")
                return True
            time.sleep(0.5)
            
        logging.warning(f"超時：元素 '{selector}' 在 {timeout} 秒內未出現。")
        return False
        
    def execute_script(self, js_code, timeout=10):
        result = self._send("Runtime.evaluate", {
            "expression": js_code,
            "awaitPromise": True,  # ⬅️ 呢個一定要有
            "returnByValue": True
        })
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

    def type_into_element_by_aria_label_0(self, aria_label, text):
        """
        用 aria-label 搵元素並輸入文字
        """
        logging.info(f"試圖向 aria-label = '{aria_label}' 嘅元素輸入文字：{text}")

        aria_label_js = json.dumps(aria_label)
        text_js = json.dumps(text)

        js_code = f"""
        (function() {{
            const el = document.querySelector('[aria-label=' + {aria_label_js} + ']');
            if (!el) {{
                return "❌ 找不到 aria-label 為 " + {aria_label_js} + " 嘅元素";
            }}

            const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            nativeInputValueSetter.call(el, {text_js});

            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            return "✅ 已輸入文字：" + {text_js} + " 至 aria-label = " + {aria_label_js};
        }})()
        """
        return self.execute_script(js_code)

    def count_textareas(self):
        """
        統計頁面上有幾多個 <textarea> 元素
        """
        logging.info("統計頁面上嘅 <textarea> 數量...")
        js_code = """
            (function() {
                return document.querySelectorAll('textarea').length;
            })()
        """
        return self.execute_script(js_code)
    
    def list_textarea_labels(self):
        """
        列出所有 <textarea> 嘅 aria-label、placeholder 同埋現有 value
        """
        logging.info("列出所有 <textarea> 元素嘅屬性...")
        js_code = """
            (function() {
                const areas = document.querySelectorAll('textarea');
                return Array.from(areas).map(el => ({
                    'ariaLabel': el.getAttribute('aria-label'),
                    'placeholder': el.getAttribute('placeholder'),
                    'value': el.value
                }));
            })()
        """
        return self.execute_script(js_code)



    def type_into_element_by_aria_label(self, aria_label, text):
        """
        用 aria-label 搵元素（input 或 textarea）並模擬輸入文字（帶有事件）
        """
        logging.info(f"試圖向 aria-label = '{aria_label}' 嘅元素輸入文字：{text}")

        aria_label_js = json.dumps(aria_label)
        text_js = json.dumps(text)

        js_code = f"""
        (function() {{
            const el = document.querySelector('[aria-label=' + {aria_label_js} + ']');
            if (!el) {{
                return "❌ 找不到 aria-label 為 " + {aria_label_js} + " 嘅元素";
            }}

            el.focus();
            el.style.border = "2px solid red";
            el.style.backgroundColor = "lightyellow";

            let setter;
            if (el.tagName === 'TEXTAREA') {{
                setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
            }} else {{
                setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
            }}
            setter.call(el, {text_js});

            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            el.dispatchEvent(new Event('change', {{ bubbles: true }}));

            // 模擬打字事件（某些網站依賴鍵盤事件）
            const keyboardEventInit = {{
                bubbles: true,
                cancelable: true,
                key: '',
                code: '',
                view: window
            }};
            el.dispatchEvent(new KeyboardEvent('keydown', keyboardEventInit));
            el.dispatchEvent(new KeyboardEvent('keypress', keyboardEventInit));
            el.dispatchEvent(new KeyboardEvent('keyup', keyboardEventInit));

            return "✅ 已輸入文字：" + {text_js} + " 至 aria-label = " + {aria_label_js};
        }})()
        """
        return self.execute_script(js_code)

    def simulate_real_typing_to_textarea(self, text):
        """
        真實模擬打字落 <textarea>，並喚醒 React 令 submit 按鈕變 active
        """
        logging.info(f"模擬真實逐字輸入到 textarea：{text}")
        text_js = json.dumps(text)

        js_code = f"""
        (async function() {{
            const textarea = Array.from(document.querySelectorAll('textarea')).find(t =>
                t.getAttribute('aria-label') === '添加评论...' ||
                t.getAttribute('placeholder') === '添加评论...'
            );

            if (!textarea) return "❌ 找唔到 textarea";

            textarea.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
            textarea.focus();

            const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;

            for (let i = 0; i < {text_js}.length; i++) {{
                const char = {text_js}[i];
                textarea.value += char;

                const event = new Event('input', {{ bubbles: true }});
                textarea.dispatchEvent(event);
                await new Promise(resolve => setTimeout(resolve, 50));
            }}

            // 👇 模擬按 space 令 React 醒覺
            textarea.value += ' ';
            textarea.dispatchEvent(new Event('input', {{ bubbles: true }}));
            textarea.dispatchEvent(new KeyboardEvent('keydown', {{ key: ' ', code: 'Space', bubbles: true }}));
            textarea.dispatchEvent(new KeyboardEvent('keyup', {{ key: ' ', code: 'Space', bubbles: true }}));

            return "✅ 模擬輸入完成 + React 醒咗";
        }})()
        """
        return self.execute_script(js_code)




    def add_comment(self, comment_text):
        """
        對 Instagram 帖子模擬輸入留言（針對 React 控制元件）
        """
        logging.info(f"🔧 準備輸入留言：{comment_text}")
        text_js = json.dumps(comment_text)

        js_code = f"""
        (function() {{
            const textarea = Array.from(document.querySelectorAll('textarea')).find(t =>
                t.getAttribute('aria-label') === '添加评论...' ||
                t.getAttribute('placeholder') === '添加评论...'
            );
            
            if (!textarea) {{
                return "❌ 找唔到留言框";
            }}

            textarea.scrollIntoView({{ behavior: 'instant', block: 'center' }});
            textarea.focus();

            // 利用原生 setter 方法設值（React-compatible）
            const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
            nativeSetter.call(textarea, {text_js});

            // 強制 React 感知輸入變化
            const inputEvent = new Event('input', {{ bubbles: true }});
            textarea.dispatchEvent(inputEvent);

            const changeEvent = new Event('change', {{ bubbles: true }});
            textarea.dispatchEvent(changeEvent);

            const keydown = new KeyboardEvent('keydown', {{ bubbles: true, key: ' ', code: 'Space' }});
            textarea.dispatchEvent(keydown);

            const keyup = new KeyboardEvent('keyup', {{ bubbles: true, key: ' ', code: 'Space' }});
            textarea.dispatchEvent(keyup);

            return textarea.value === {text_js} ? "✅ 已成功輸入留言" : "⚠️ 未能設置留言值";
        }})()
        """

        result = self.execute_script(js_code)
        logging.info(f"📥 輸入留言結果：{result}")
        return result



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
                requests.get(f"http://{self.host}:{self.port}/json/close/{self.tab_info['id']}")
                logging.info(f"已關閉 Chrome 分頁: {self.tab_info['id']}")
            except requests.RequestException as e:
                logging.warning(f"無法關閉 Chrome 分頁: {e}")

    
    def click_element_by_aria_label(self, aria_label):
        """
        用 aria-label 精準搵元素並點擊（使用 MouseEvent 模擬真實點擊）
        """
        logging.info(f"試圖點擊 aria-label = '{aria_label}' 嘅元素")

        aria_label_js = json.dumps(aria_label)

        js_code = f"""
        (function() {{
            const target = document.querySelector('[aria-label=' + {aria_label_js} + ']');
            if (target) {{
                target.style.border = '2px solid red';
                target.style.backgroundColor = 'yellow';

                const rect = target.getBoundingClientRect();
                const isVisible = (rect.width > 0 && rect.height > 0);

                if (!isVisible) {{
                    return "⚠️ 元素存在但不可見或被遮住";
                }}

                const event = new MouseEvent('click', {{
                    view: window,
                    bubbles: true,
                    cancelable: true
                }});
                target.dispatchEvent(event);

                return "✅ Dispatched click event to element with aria-label: " + {aria_label_js};
            }} else {{
                return "❌ No element found with aria-label: " + {aria_label_js};
            }}
        }})()
        """

        result = self.execute_script(js_code)
        time.sleep(2)
        print(f"Click attempt result: {result}")
        if not result:
            logging.info("未搵到任何彈窗按鈕")
        else:
            logging.info(f"點擊結果：{result}")

        return result
    
    def scroll_down(self, pixels=500):
        """
        向下捲動頁面指定像素（預設 500px）
        """
        logging.info(f"🔽 開始向下滾動 {pixels}px...")

        js_code = f"""
        (function() {{
            window.scrollBy({{ top: {pixels}, behavior: 'smooth' }});
            return "✅ 滾動完成";
        }})()
        """

        result = self.execute_script(js_code)
        logging.info(f"📜 滾動結果：{result}")
        return result

    def scroll_down_loop(self, times=5, interval=2):
        """
        連續滾動多次，每次間隔 interval 秒
        """
        logging.info(f"🔁 將滾動 {times} 次，每次間隔 {interval} 秒")
        for i in range(times):
            self.scroll_down(800)
            time.sleep(interval)
        logging.info("📄 完成所有滾動")
    
    def close_img(self):
        """
        尋找頁面上第一個 <polyline> 元素並模擬點擊，常用於關閉圖片彈窗
        """
        logging.info("🔍 嘗試關閉圖片視窗（搜尋 <polyline>）")

        js_code = """
        (function() {
            const polyline = document.querySelector('polyline');
            if (!polyline) {
                return "❌ 找唔到 <polyline> 元素";
            }

            // 嘗試向上找可以點擊的父級
            let clickable = polyline;
            for (let i = 0; i < 5; i++) {
                if (clickable && typeof clickable.click === 'function') {
                    clickable.click();
                    return "✅ 已點擊 <polyline> 或其父元素";
                }
                clickable = clickable.parentElement;
            }

            return "⚠️ 雖然找到 <polyline>，但無可點擊的父級元素";
        })()
        """

        result = self.execute_script(js_code)
        logging.info(f"🧪 關閉結果：{result}")
        return result




    def click_button_by_texts(self, texts):
        """
        傳入 cdp_client 物件同一個文字 list，幫你自動執行點擊第一個完全匹配嘅按鈕。
        回傳點擊結果或 False。
        """
        texts_js_array = json.dumps(texts)
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
                    
                        return `Clicked button with exact text: ${{text}}`;
                    }}
                }}
            }}
            return false;
        }})()
        """
        result = self.execute_script(js_code)
        time.sleep(2)
        print(f"Click attempt result: {result}")
        if not result:
            logging.info("未搵到任何彈窗按鈕")
        else:
            logging.info(f"點擊結果：{result}")

        return result
    
    def get_bk_components_heading(self):
        js_code = """
        (function() {
            const elements = Array.from(document.querySelectorAll('span[data-bloks-name="bk.components.Text"][role="heading"]'));
            return elements.map(el => ({
                aria_label: el.getAttribute('aria-label'),
                text: el.innerText
            }));
        })()
        """
        return self.execute_script(js_code)


    
    def follow_user(self, delay = 1):
        logging.info("開始點擊Follow...")
        #result = self.click_button_by_texts(['保存信息', '儲存資料'])
        #result = self.click_element_by_aria_label(['首页'])
        #result = self.type_into_element_by_aria_label('搜索输入', 'AI 美女')
        time.sleep(2)


        
    
    def click_all_images_one_by_one(self, delay=5):
        """
        點擊頁面上所有 <img>，每次點擊後等 delay 秒。
        """
        logging.info("開始循環點擊所有 <img> 元素...")

        js_code = """
        (function() {
            const images = Array.from(document.querySelectorAll('img'));
            return images.map((img, idx) => {
                img.setAttribute('data-img-id', 'img_' + idx);
                return img.getAttribute('data-img-id');
            });
        })()
        """
        img_ids = self.execute_script(js_code)

        if not img_ids:
            logging.warning("找不到任何 <img> 元素")
            return

        logging.info(f"發現 {len(img_ids)} 張圖片，準備逐一點擊...")

        for img_id in img_ids:
            logging.info(f"🖱️ 點擊圖片：{img_id}")

            click_script = f"""
            (function() {{
                const target = document.querySelector('[data-img-id="{img_id}"]');
                if (!target) return "❌ 找唔到 {img_id}";
                target.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                target.click();
                return "✅ Clicked image: {img_id}";
            }})()
            """
            result = self.execute_script(click_script)
            logging.info(result)

            # ✨ 你可以喺呢度做你想做嘅事，例如收集 modal 內容、save html、screenshot 等

            # 等 5~10 秒（可調整）
            wait_time = delay + (random.random() * 2)  # 少少變化
            logging.info(f"等緊 {wait_time:.1f} 秒再處理下一張...")
            time.sleep(wait_time)

        logging.info("🎉 完成所有圖片處理")

    

    def press_button_sequence(self, order=[], delay=2.0):
        """
        根據順序執行點擊 / 輸入 / 自訂方法，每步後延遲隨機時間
        :param order: 執行步驟清單
        :param delay: 每步最大延遲秒數（最少 0.8 秒）
        """
        for idx, item in enumerate(order):
            try:
                logging.info(f"➡️ 開始第 {idx + 1} 步：{item}")

                # Case 1: 普通 list，例如 ['關注']
                if isinstance(item, list) and all(isinstance(sub, str) for sub in item):
                    # 嘗試用 click_button_by_texts
                    result = self.click_button_by_texts(item)
                    if not result:
                        logging.info(f"🔍 button_by_texts 未點擊成功，嘗試 aria-label: {item}")
                        result = self.click_element_by_aria_label(item)
                    logging.info(f"✅ 點擊結果: {result}")

                # Case 2: List of two string → 當作輸入
                elif isinstance(item, list) and len(item) == 2 and all(isinstance(sub, str) for sub in item):
                    aria_label, text = item
                    result = self.type_into_element_by_aria_label(aria_label, text)
                    logging.info(f"📝 輸入 [{text}] 至 [{aria_label}]，結果：{result}")

                # Case 3: method dictionary
                elif isinstance(item, dict) and 'method' in item:
                    method_name = item['method']
                    param = item.get('param', None)

                    if hasattr(self, method_name):
                        method = getattr(self, method_name)
                        if callable(method):
                            result = method(param) if param is not None else method()
                            logging.info(f"🔧 執行 {method_name} 結果：{result}")
                        else:
                            logging.warning(f"❌ {method_name} 不是可執行方法")
                    else:
                        logging.warning(f"❌ 未找到方法：{method_name}")

                else:
                    logging.warning(f"⚠️ 不支持的指令格式：{item}")

                # ✅ 每步後加入隨機延遲
                min_delay = 0.8
                actual_delay = random.uniform(min_delay, max(delay, min_delay))
                logging.info(f"⏳ 等待 {actual_delay:.2f} 秒...")
                time.sleep(actual_delay)

            except Exception as e:
                logging.error(f"❌ 第 {idx + 1} 步發生錯誤：{e}", exc_info=True)


