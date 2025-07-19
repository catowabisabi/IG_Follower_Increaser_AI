from flask import Flask, request, jsonify
import subprocess
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
import socket
import threading
import logging
import requests
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import random
import math
import os
import json
import tempfile
from pathlib import Path
from openai import OpenAI
from datetime import datetime
import sys


class ChromeWithPrefs(webdriver.Chrome):
    """自定義 Chrome 類別，確保 preferences 正確設置"""
    
    def __init__(self, *args, **kwargs):
        options = kwargs.get('options', None)
        if options:
            if "prefs" in options._experimental_options:
                self._handle_prefs(options)
        super().__init__(*args, **kwargs)
    
    def _handle_prefs(self, options):
        """處理 Chrome preferences"""
        prefs = options._experimental_options["prefs"]
        
        # 建立臨時用戶資料目錄
        user_data_dir = os.path.normpath(tempfile.mkdtemp())
        options.add_argument(f"--user-data-dir={user_data_dir}")
        
        # 確保 Default 目錄存在
        default_dir = os.path.join(user_data_dir, "Default")
        os.makedirs(default_dir, exist_ok=True)
        
        # 將點號分隔的鍵轉換為巢狀字典
        def convert_dot_keys(prefs):
            result = {}
            for key, value in prefs.items():
                parts = key.split('.')
                target = result
                for part in parts[:-1]:
                    target = target.setdefault(part, {})
                target[parts[-1]] = value
            return result
        
        # 寫入 Preferences 檔案
        prefs_file = os.path.join(default_dir, "Preferences")
        converted_prefs = convert_dot_keys(prefs)
        with open(prefs_file, 'w') as f:
            json.dump(converted_prefs, f)
        
        # 避免 Selenium 重複處理
        del options._experimental_options["prefs"]


class WebScraperAPI:

    def __init__(self):
        self.app = Flask(__name__)
        self._setup_routes()
        self.chrome_session_lock = threading.Lock()
        self.chrome_session_running = False
        self.request_semaphore = threading.Semaphore(3)
        self.start_time = None
        self.max_retries = 3  # 最大重試次數
        
        # 設置 OpenAI API
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        if not self.openai_api_key:
            logging.warning("未設置 OPENAI_API_KEY 環境變數")

        # User Agent 池
        self.user_agent_pool = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
            "Mozilla/5.0 (Linux; Android 12; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.5672.92 Mobile Safari/537.36",
        ]

        # 清理臨時目錄
        import atexit
        atexit.register(self._cleanup_temp_dirs)
        
        monitor_thread              = threading.Thread(target=self._monitor_chrome_session, daemon=True)
        monitor_thread.start()

    def _cleanup_temp_dirs(self):
        """清理臨時建立的用戶資料目錄"""
        temp_dir = tempfile.gettempdir()
        for item in os.listdir(temp_dir):
            if item.startswith('tmp'):
                try:
                    path = os.path.join(temp_dir, item)
                    if os.path.isdir(path):
                        import shutil
                        shutil.rmtree(path, ignore_errors=True)
                except Exception as e:
                    logging.warning(f"清理臨時目錄失敗: {str(e)}")

    def _simulate_human_delay(self, min_sec=0.5, max_sec=1):
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)
        return delay

    def _bezier_curve(self, start, end, control, t):
        """生成貝茲曲線上的點，實現平滑的滑鼠移動"""
        x = int((1 - t) * (1 - t) * start[0] + 2 * (1 - t) * t * control[0] + t * t * end[0])
        y = int((1 - t) * (1 - t) * start[1] + 2 * (1 - t) * t * control[1] + t * t * end[1])
        return (x, y)

    def _natural_mouse_movement(self, driver, element=None, end_x=None, end_y=None):
        """實現自然的滑鼠移動"""
        action = ActionChains(driver)

        try:
            # 獲取視窗和視口大小
            window_size = driver.get_window_size()
            viewport_width = driver.execute_script("return window.innerWidth;")
            viewport_height = driver.execute_script("return window.innerHeight;")
            
            # 使用較小的值作為邊界
            max_x = min(window_size['width'], viewport_width) - 20
            max_y = min(window_size['height'], viewport_height) - 20
            
            if max_x <= 20 or max_y <= 20:
                logging.warning("視窗或視口大小異常，跳過滑鼠移動")
                return
            
            # 確保起始位置在安全範圍內
            start_x = random.randint(20, max_x - 20)
            start_y = random.randint(20, max_y - 20)
            
            # 如果提供了元素，確保元素在視口內
            if element:
                try:
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", element)
                    time.sleep(0.1)  # 等待滾動完成
                    
                    location = element.location
                    size = element.size
                    
                    # 確保元素位置在視口內
                    end_x = min(max(20, location['x'] + size['width'] // 2), max_x - 20)
                    end_y = min(max(20, location['y'] + size['height'] // 2), max_y - 20)
                except Exception as e:
                    logging.warning(f"元素定位失敗: {str(e)}")
                    return
            else:
                # 確保目標位置在安全範圍內
                end_x = min(max(20, end_x if end_x is not None else random.randint(20, max_x - 20)), max_x - 20)
                end_y = min(max(20, end_y if end_y is not None else random.randint(20, max_y - 20)), max_y - 20)
            
            # 生成控制點（確保在起點和終點形成的矩形內）
            min_x = min(start_x, end_x) + 20
            max_control_x = max(start_x, end_x) - 20
            min_y = min(start_y, end_y) + 20
            max_control_y = max(start_y, end_y) - 20
            
            if min_x >= max_control_x or min_y >= max_control_y:
                control_x = (start_x + end_x) // 2
                control_y = (start_y + end_y) // 2
            else:
                control_x = random.randint(min_x, max_control_x)
                control_y = random.randint(min_y, max_control_y)
            
            # 生成平滑的移動路徑
            current_x, current_y = start_x, start_y
            steps = 30
            
            for i in range(steps + 1):
                t = i / steps
                next_x, next_y = self._bezier_curve((start_x, start_y), (end_x, end_y), (control_x, control_y), t)
                
                # 確保每個點都在安全範圍內
                next_x = min(max(20, next_x), max_x - 20)
                next_y = min(max(20, next_y), max_y - 20)
                
                # 計算實際需要移動的距離
                offset_x = next_x - current_x
                offset_y = next_y - current_y
                
                if abs(offset_x) > 0 or abs(offset_y) > 0:
                    action.move_by_offset(offset_x, offset_y)
                    current_x, current_y = next_x, next_y
                
                action.pause(random.uniform(0.001, 0.003))
            
            action.perform()
            
        except Exception as e:
            logging.warning(f"滑鼠移動失敗: {str(e)}")
            return

    def _smooth_scroll(self, driver, scroll_amount):
        """實現平滑滾動"""
        steps = 10
        for i in range(steps):
            step = scroll_amount / steps
            driver.execute_script(f"window.scrollBy(0, {step});")
            time.sleep(random.uniform(0.05, 0.01))

    def _random_actions(self, driver):
        """執行隨機的人為操作"""
        actions = ["scroll", "wait"]  # 移除可能導致問題的 "move" 和 "click" 操作
        action = random.choice(actions)
        
        try:
            if action == "scroll":
                # 獲取頁面高度
                page_height = driver.execute_script("return document.body.scrollHeight")
                viewport_height = driver.execute_script("return window.innerHeight")
                max_scroll = page_height - viewport_height
                
                if max_scroll > 0:
                    scroll_amount = random.randint(100, min(500, max_scroll))
                    self._smooth_scroll(driver, scroll_amount)
            
            elif action == "wait":
                self._simulate_human_delay(1, 3)
                
        except Exception as e:
            logging.warning(f"Random action failed: {str(e)}")

    def _is_captcha_present(self, driver):
        """檢查是否存在驗證碼"""
        captcha_selectors = [
        "#captcha",
        ".captcha",
        "#challenge-form",
        "[class*='captcha']",
        "[id*='captcha']"
    ]
        
        try:
            return any(len(driver.find_elements(By.CSS_SELECTOR, selector)) > 0 
                for selector in captcha_selectors)
        except:
            # 如果選擇器失敗，再使用原來的方法
            return any(indicator in driver.page_source.lower() 
                    for indicator in ["captcha", "verify you are human"])

    def _get_pure_text(self, driver):
        """獲取頁面的純文字內容"""
        try:
            # 使用 body 標籤來獲取所有可見的文字
            body = driver.find_element(By.TAG_NAME, "body")
            #print(body.text)
            return body.text
        except Exception as e:
            logging.warning(f"獲取純文字失敗: {str(e)}")
            return ""
        
    def _print_timer(self):
        """顯示執行時間"""
        if self.start_time:
            elapsed = datetime.now() - self.start_time
            logging.info(f"執行時間: {elapsed.seconds}秒")

    def _process_with_chatgpt(self, text):
        """使用 ChatGPT 處理文本"""
        try:
            if not self.openai_api_key:
                return {"error": "未設置 OpenAI API Key", "raw_text": text}

            client = OpenAI(api_key=self.openai_api_key)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "請總結以下文本的主要內容，並提取關鍵信息："},
                    {"role": "user", "content": text}
                ],
                max_tokens=500
            )
            
            return {
                "summary": response.choices[0].message.content,
                "raw_text": text
            }
        except Exception as e:
            logging.error(f"ChatGPT 處理失敗: {str(e)}")
            return {"error": str(e), "raw_text": text}

    def _scrape_with_retry(self, driver, url):
        """帶重試機制的爬蟲"""
        retry_count = 0
        while retry_count < self.max_retries:
            try:
                driver.get(url)
                
                # 執行3-5次隨機操作
                num_actions = random.randint(3, 5)
                for _ in range(num_actions):
                    self._random_actions(driver)
                    self._print_timer()  # 更新計時器
                
                # 檢查是否有驗證碼
                if self._is_captcha_present(driver):
                    retry_count += 1
                    logging.warning(f"檢測到驗證碼！重試次數: {retry_count}")
                    
                    if retry_count >= self.max_retries:
                        return {
                            "status": "captcha_detected",
                            "message": "驗證碼重試次數超過上限"
                        }
                    
                    # 等待一段時間後重試
                    time.sleep(random.uniform(5, 10))
                    continue
                
                # 獲取並處理文本
                pure_text = self._get_pure_text(driver)
                processed_text = self._process_with_chatgpt(pure_text)
                
                return {
                    "status": "success",
                    "title": driver.title,
                    "html": driver.page_source,
                    "processed_text": processed_text
                }
                
            except Exception as e:
                retry_count += 1
                logging.error(f"爬蟲錯誤 (重試 {retry_count}): {str(e)}")
                if retry_count >= self.max_retries:
                    return {"error": str(e)}, 500
                time.sleep(random.uniform(2, 5))
        
        return {"error": "超過最大重試次數"}, 500

    def _setup_routes(self):
        @self.app.route("/", methods=["GET"])
        def home():
            return "✅ Flask 爬蟲 API 已成功啟動！"

        @self.app.route("/scrape", methods=["POST"])
        def scrape():
            if not self.request_semaphore.acquire(blocking=False):
                return jsonify({"error": "伺服器繁忙，請稍後再試"}), 429

            try:
                data = request.json
                url = data.get("url")
                use_session = data.get("use_session", True)
                headless = data.get("headless", True)  # 默認改為 True

                if not url:
                    return jsonify({"error": "缺少必要的 'url' 參數"}), 400

                logging.info(f"收到爬蟲請求：{url} (headless: {headless})")
                self.start_time = datetime.now()  # 開始計時

                if use_session:
                    self._launch_chrome_session()

                driver = None
                try:
                    driver = self._start_driver(use_session_port=use_session, headless=headless)
                    result = self._scrape_with_retry(driver, url)
                    return jsonify(result)
                    
                except Exception as e:
                    logging.error(f"爬蟲錯誤：{str(e)}")
                    return jsonify({"error": str(e)}), 500
                finally:
                    if driver and not use_session:
                        try:
                            driver.quit()
                            logging.info("已關閉 WebDriver")
                        except Exception as e:
                            logging.warning(f"關閉 WebDriver 發生錯誤：{str(e)}")
                    self.start_time = None  # 重置計時器
            finally:
                self.request_semaphore.release()

    def _is_port_in_use(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return False
            except socket.error:
                return True

    def _is_chrome_session_alive(self) -> bool:
        try:
            r = requests.get("http://127.0.0.1:9222/json/version", timeout=2)
            return r.status_code == 200
        except:
            return False

    def _launch_chrome_session(self):
        with self.chrome_session_lock:
            if self.chrome_session_running and self._is_chrome_session_alive():
                logging.info("Chrome 埠 9222 已在運作中")
                return

            chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
            user_data_dir = r"C:\selenium-chrome"
            port = 9222

            if not self._is_port_in_use(port):
                logging.info("啟動 Chrome 工作階段...")
                try:
                    subprocess.Popen([
                        chrome_path,
                        f"--remote-debugging-port={port}",
                        f"--user-data-dir={user_data_dir}",
                        "--start-maximized"
                    ], creationflags=subprocess.CREATE_NEW_CONSOLE)

                    for _ in range(10):
                        if self._is_chrome_session_alive():
                            self.chrome_session_running = True
                            logging.info("Chrome 工作階段啟動成功")
                            return
                        time.sleep(1)
                    raise Exception("Chrome 啟動失敗")
                except Exception as e:
                    logging.error(f"啟動 Chrome 失敗：{str(e)}")
                    self.chrome_session_running = False
            else:
                logging.info("Chrome 埠已被使用")
                self.chrome_session_running = True

    def _monitor_chrome_session(self):
        while True:
            time.sleep(10)
            with self.chrome_session_lock:
                if self.chrome_session_running and not self._is_chrome_session_alive():
                    logging.warning("Chrome 工作階段已失效，嘗試重啟...")
                    self.chrome_session_running = False
                    try:
                        self._launch_chrome_session()
                    except Exception as e:
                        logging.error(f"Chrome 重啟失敗：{str(e)}")

    def _start_driver(self, use_session_port=False, headless=False):
        chrome_options = Options()

        if use_session_port:
            chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
        
        if headless:
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--window-size=1920,1080")

        # 進階反檢測參數
        chrome_options.add_argument(f"user-agent={random.choice(self.user_agent_pool)}")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-setuid-sandbox")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-popup-blocking")
        chrome_options.add_argument("--disable-save-password-bubble")
        chrome_options.add_argument("--disable-translate")
        chrome_options.add_argument("--ignore-certificate-errors")
        chrome_options.add_argument("--no-default-browser-check")
        chrome_options.add_argument("--no-first-run")
        chrome_options.add_argument("--dns-prefetch-disable")
        chrome_options.add_argument("--disable-features=IsolateOrigins,site-per-process")
        chrome_options.add_argument("--enable-automation=false")
        
        # 使用arguments來禁用自動化提示，而不是experimental_options
        chrome_options.add_argument("--disable-automation")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")

        # 進階偏好設定
        prefs = {
            "profile.default_content_settings.popups": 0,
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_setting_values.images": 1,
            "profile.default_content_setting_values.javascript": 1,
            "profile.managed_default_content_settings.javascript": 1,
            "profile.default_content_setting_values.plugins": 1,
            "profile.default_content_setting_values.geolocation": 2,
            "profile.default_content_setting_values.media_stream": 2,
            "profile.managed_default_content_settings.images": 1,
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
            "profile.managed_default_content_settings.cookies": 1,
            "profile.default_content_setting_values.cookies": 1,
            "profile.managed_default_content_settings.plugins": 1,
            "profile.default_content_settings.state.flash": 0,
            "profile.content_settings.exception_patterns": {},
            "download.directory_upgrade": True,
            "download.prompt_for_download": False,
            "plugins.always_open_pdf_externally": True
        }
        chrome_options.add_experimental_option("prefs", prefs)

        service = Service(ChromeDriverManager().install())
        
        # 使用自定義的 Chrome 類別
        driver = ChromeWithPrefs(service=service, options=chrome_options)
        
        # 注入進階反檢測腳本
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                // 基本 webdriver 檢測
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // 模擬真實瀏覽器特徵
                Object.defineProperty(navigator, 'plugins', {
                    get: () => {
                        return [
                            {
                                0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                                description: "Portable Document Format",
                                filename: "internal-pdf-viewer",
                                length: 1,
                                name: "Chrome PDF Plugin"
                            },
                            {
                                0: {type: "application/pdf", suffixes: "pdf", description: ""},
                                description: "",
                                filename: "mhjfbmdgcfjbbpaeojofohoefgiehjai",
                                length: 1,
                                name: "Chrome PDF Viewer"
                            }
                        ];
                    }
                });
                
                // 模擬語言設定
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en', 'zh-TW']
                });
                
                // 模擬 Chrome 運行時
                window.chrome = {
                    app: {
                        isInstalled: false,
                        InstallState: {
                            DISABLED: 'DISABLED',
                            INSTALLED: 'INSTALLED',
                            NOT_INSTALLED: 'NOT_INSTALLED'
                        },
                        RunningState: {
                            CANNOT_RUN: 'CANNOT_RUN',
                            READY_TO_RUN: 'READY_TO_RUN',
                            RUNNING: 'RUNNING'
                        }
                    },
                    runtime: {
                        OnInstalledReason: {
                            CHROME_UPDATE: 'chrome_update',
                            INSTALL: 'install',
                            SHARED_MODULE_UPDATE: 'shared_module_update',
                            UPDATE: 'update'
                        },
                        OnRestartRequiredReason: {
                            APP_UPDATE: 'app_update',
                            OS_UPDATE: 'os_update',
                            PERIODIC: 'periodic'
                        },
                        PlatformArch: {
                            ARM: 'arm',
                            ARM64: 'arm64',
                            MIPS: 'mips',
                            MIPS64: 'mips64',
                            X86_32: 'x86-32',
                            X86_64: 'x86-64'
                        },
                        PlatformNaclArch: {
                            ARM: 'arm',
                            MIPS: 'mips',
                            MIPS64: 'mips64',
                            X86_32: 'x86-32',
                            X86_64: 'x86-64'
                        },
                        PlatformOs: {
                            ANDROID: 'android',
                            CROS: 'cros',
                            LINUX: 'linux',
                            MAC: 'mac',
                            OPENBSD: 'openbsd',
                            WIN: 'win'
                        },
                        RequestUpdateCheckStatus: {
                            NO_UPDATE: 'no_update',
                            THROTTLED: 'throttled',
                            UPDATE_AVAILABLE: 'update_available'
                        }
                    }
                };
                
                // 模擬硬體特徵
                Object.defineProperty(navigator, 'hardwareConcurrency', {
                    get: () => 8
                });
                Object.defineProperty(navigator, 'deviceMemory', {
                    get: () => 8
                });
                Object.defineProperty(screen, 'colorDepth', {
                    get: () => 24
                });
                
                // 模擬 WebGL
                const getParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {
                    if (parameter === 37445) {
                        return 'Intel Inc.'
                    }
                    if (parameter === 37446) {
                        return 'Intel(R) Iris(TM) Graphics 6100'
                    }
                    return getParameter.apply(this, [parameter]);
                };
                
                // 模擬其他瀏覽器特徵
                Object.defineProperty(navigator, 'platform', {
                    get: () => 'Win32'
                });
                Object.defineProperty(navigator, 'maxTouchPoints', {
                    get: () => 0
                });
                Object.defineProperty(navigator, 'vendor', {
                    get: () => 'Google Inc.'
                });
            """
        })
        
        # 使用 CDP 命令來禁用自動化標記
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            "source": """
                Object.defineProperty(window, 'navigator', {
                    value: new Proxy(navigator, {
                        has: (target, key) => (key === 'webdriver' ? false : key in target),
                        get: (target, key) =>
                            key === 'webdriver' ?
                            false :
                            typeof target[key] === 'function' ?
                            target[key].bind(target) :
                            target[key]
                    })
                });
            """
        })
        
        driver.set_page_load_timeout(15)
        return driver

    def run(self, debug=False, host="0.0.0.0", port=5000):
        # 設置日誌級別
        if not debug:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.StreamHandler(sys.stdout),
                    logging.FileHandler('scraper.log')
                ]
            )
        
        # 使用 threaded=True 來支持多線程
        self.app.run(
            debug=debug,
            host=host,
            port=port,
            threaded=True,
            use_reloader=False  # 禁用重載器以避免在非調試模式下的問題
        )


# 主程式執行點
if __name__ == "__main__":
    app_instance = WebScraperAPI()
    app_instance.run(debug=False)
