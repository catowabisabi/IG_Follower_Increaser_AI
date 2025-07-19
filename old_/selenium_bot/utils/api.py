import logging
import logging.config
import threading
import socket
import requests
import subprocess
import time
import random
from datetime import datetime
from flask import Flask, request, jsonify
from config.settings import (
    CHROME_PATH,
    CHROME_PORT,
    MAX_RETRIES,
    LOG_CONFIG,
    CHROME_DATA_DIR, # 假設您已在 settings.py 中定義
    CHROME_ARGS      # 假設您已在 settings.py 中定義
)
from .chrome_driver import create_driver
from .human_behavior import random_actions, is_captcha_present
from .text_processor import TextProcessor
from .utils import retry # 這個文件裡沒有 retry，假設它來自 config.settings 裡面的 utils

import os
import psutil
import shutil
import sys
import platform

def print_chrome_version():
    try:
        resp = requests.get(f"http://127.0.0.1:{CHROME_PORT}/json/version", timeout=2)
        if resp.status_code == 200:
            data = resp.json()
            print(f"Chrome version: {data.get('Browser')}")
        else:
            print("無法獲取 Chrome 版本")
    except Exception as e:
        print(f"獲取 Chrome 版本失敗: {e}")


def print_windows_version():
    print(f"OS: {platform.system()} {platform.release()} ({platform.version()})")



def print_python_version():
    print(f"Python version: {sys.version}")

def print_chromedriver_version(driver):
    try:
        version = driver.capabilities['chrome']['chromedriverVersion']
        print(f"ChromeDriver version: {version}")
    except Exception as e:
        print(f"無法獲取 ChromeDriver 版本: {e}")

def print_user_agent(driver):
    try:
        ua = driver.execute_script("return navigator.userAgent")
        print(f"User-Agent: {ua}")
    except Exception as e:
        print(f"無法獲取 User-Agent: {e}")

def print_screen_info(driver):
    try:
        width = driver.execute_script("return screen.width")
        height = driver.execute_script("return screen.height")
        color_depth = driver.execute_script("return screen.colorDepth")
        print(f"Screen: {width}x{height}, Color Depth: {color_depth}")
    except Exception as e:
        print(f"無法獲取螢幕資訊: {e}")

def print_language_timezone(driver):
    try:
        lang = driver.execute_script("return navigator.language")
        tz = driver.execute_script("return Intl.DateTimeFormat().resolvedOptions().timeZone")
        print(f"Language: {lang}, Timezone: {tz}")
    except Exception as e:
        print(f"無法獲取語言/時區: {e}")

def print_webgl_info(driver):
    try:
        vendor = driver.execute_script("""
            var canvas = document.createElement('canvas');
            var gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
            var debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
            return gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL);
        """)
        renderer = driver.execute_script("""
            var canvas = document.createElement('canvas');
            var gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
            var debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
            return gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL);
        """)
        print(f"WebGL Vendor: {vendor}, Renderer: {renderer}")
    except Exception as e:
        print(f"無法獲取 WebGL 資訊: {e}")

def print_webdriver_flag(driver):
    try:
        webdriver_flag = driver.execute_script("return navigator.webdriver")
        print(f"navigator.webdriver: {webdriver_flag}")
    except Exception as e:
        print(f"無法獲取 webdriver 屬性: {e}")

def print_external_ip():
    try:
        ip = requests.get("https://api.ipify.org").text
        print(f"External IP: {ip}")
    except Exception as e:
        print(f"無法獲取外部 IP: {e}")





def print_env_info(driver):
    print_python_version()
    print_windows_version()
    print_chrome_version()
    print_chromedriver_version(driver)
    print_user_agent(driver)
    print_screen_info(driver)
    print_language_timezone(driver)
    print_webgl_info(driver)
    print_webdriver_flag(driver)
    print_external_ip()


class WebScraperAPI:
    def __init__(self):
        self.app = Flask(__name__)
        self._setup_routes()
        self.chrome_session_lock = threading.Lock()
        self.chrome_session_running = False
        self.request_semaphore = threading.Semaphore(3)
        self.start_time = None
        self.max_retries = MAX_RETRIES
        self.text_processor = TextProcessor()
        self.chrome_pid = None
        self.shared_driver = None
        
        self.shared_driver_lock = threading.Lock()
        

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
                headless = data.get("headless", os.getenv('SCRAPER_HEADLESS', 'true').lower() == 'true')

                if not url:
                    return jsonify({"error": "缺少必要的 'url' 參數"}), 400

                logging.info(f"[Scrape] URL: {url} | Headless: {headless}")
                self.start_time = datetime.now()

                if use_session:
                    self._launch_chrome_session()

                driver = None
                try:
                    if use_session:
                        with self.shared_driver_lock:
                            if not self.shared_driver:
                                self.shared_driver = create_driver(use_session_port=True, headless=headless)
                                print_env_info(self.shared_driver)
                            driver = self.shared_driver
                            # 檢查並關閉多餘的標籤頁
                            if len(driver.window_handles) > 5:
                                for handle in driver.window_handles[1:]: # 保留第一個
                                    driver.switch_to.window(handle)
                                    driver.close()
                                driver.switch_to.window(driver.window_handles[0])
                            
                            driver.execute_script("window.open('about:blank', '_blank');")
                            driver.switch_to.window(driver.window_handles[-1])
                    else:
                        driver = create_driver(use_session_port=False, headless=headless)

                    result = self._scrape_with_retry(driver, url)

                    # 如果是會話模式，並且多於一個窗口，關閉當前抓取的新窗口
                    if use_session and len(driver.window_handles) > 1:
                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])
                    return jsonify(result)

                except Exception as e:
                    logging.exception(f"[Scrape Error] URL: {url} | 錯誤: {str(e)}")
                    return jsonify({"error": str(e)}), 500
                finally:
                    if driver and not use_session:
                        try:
                            driver.quit()
                            logging.info("[Driver] 已關閉 WebDriver")
                        except Exception as e:
                            logging.warning(f"[Driver] 關閉發生錯誤：{str(e)}")
                    self.start_time = None
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
            r = requests.get(f"http://127.0.0.1:{CHROME_PORT}/json/version", timeout=2)
            return r.status_code == 200
        except Exception as e:
            logging.debug(f"[Chrome] Remote Debugging 無反應: {str(e)}")
            return False

    def _terminate_chrome_by_pid(self):
        """终止Chrome进程"""
        if self.chrome_pid:
            try:
                if psutil.pid_exists(self.chrome_pid):
                    proc = psutil.Process(self.chrome_pid)
                    # 先尝试优雅关闭
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                        logging.info(f"[Chrome] 已优雅终止 PID={self.chrome_pid}")
                    except psutil.TimeoutExpired:
                        # 强制关闭
                        proc.kill()
                        logging.info(f"[Chrome] 已强制终止 PID={self.chrome_pid}")
                else:
                    logging.info(f"[Chrome] 进程 PID={self.chrome_pid} 已不存在")
            except Exception as e:
                logging.warning(f"[Chrome] 终止进程失败 PID={self.chrome_pid}: {str(e)}")
            finally:
                self.chrome_pid = None

    def _kill_existing_chrome_processes(self):
        """杀死所有现有的Chrome进程"""
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                if proc.info['name'] and 'chrome' in proc.info['name'].lower():
                    cmdline = proc.info['cmdline']
                    # 只殺死使用指定 remote-debugging-port 的 Chrome 進程
                    if cmdline and f'--remote-debugging-port={CHROME_PORT}' in ' '.join(cmdline):
                        logging.info(f"[Chrome] 发现现有Chrome进程 PID={proc.info['pid']}")
                        proc.terminate()
                        try:
                            proc.wait(timeout=3)
                        except psutil.TimeoutExpired:
                            proc.kill()
                        logging.info(f"[Chrome] 已终止现有Chrome进程 PID={proc.info['pid']}")
        except Exception as e:
            logging.warning(f"[Chrome] 清理现有进程时出错: {str(e)}")

    def _launch_chrome_session(self):
        with self.chrome_session_lock:
            if self.chrome_session_running and self._is_chrome_session_alive():
                logging.info(f"[Chrome] 埠 {CHROME_PORT} 已運作")
                return

            # 清理现有的Chrome进程
            self._kill_existing_chrome_processes()
            
            # 等待一下确保进程完全关闭
            time.sleep(2)

            if not self._is_port_in_use(CHROME_PORT):
                logging.info("[Chrome] 啟動中...")
                try:
                    # **重要修改：只在必要時清除用戶數據目錄**
                    # 如果希望保持會話持久性以減少CAPTCHA，不要每次都清除
                    # 如果您遇到會話崩潰或數據污染，再考慮清除
                    # if os.path.exists(CHROME_DATA_DIR):
                    #     try:
                    #         shutil.rmtree(CHROME_DATA_DIR)
                    #         logging.info(f"[Chrome] 清除舊資料夾 {CHROME_DATA_DIR}")
                    #     except Exception as e:
                    #         logging.warning(f"[Chrome] 無法清除 {CHROME_DATA_DIR}: {str(e)}")
                    
                    # 等待文件系統完成删除操作 (如果上面有啟用清除)
                    # time.sleep(1)

                    # 构建Chrome启动命令 - 使用更合理的參數
                    chrome_args = [
                        CHROME_PATH,
                        f"--remote-debugging-port={CHROME_PORT}",
                        f"--user-data-dir={CHROME_DATA_DIR}",
                        "--no-sandbox", # 某些環境需要
                        "--disable-dev-shm-usage", # Docker 環境常用
                        # 新增反偵測參數
                        "--disable-blink-features=AutomationControlled", # 避免被檢測為自動化工具
                        "--disable-web-security", # 允許跨域請求 (謹慎使用)
                        "--no-first-run", # 首次運行不顯示歡迎頁
                        "--no-default-browser-check", # 不檢查是否為預設瀏覽器
                        # 避免過度禁用，移除如 --disable-javascript 等可能觸發 CAPTCHA 的參數
                        # 如果有額外的通用參數，可以從 settings.py 的 CHROME_ARGS 導入
                    ] + CHROME_ARGS 
                    
                    # Windows特定配置
                    if sys.platform.startswith("win"):
                        startupinfo = subprocess.STARTUPINFO()
                        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        startupinfo.wShowWindow = subprocess.SW_HIDE
                        
                        chrome_process = subprocess.Popen(
                            chrome_args,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            startupinfo=startupinfo,
                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                        )
                    else:
                        chrome_process = subprocess.Popen(
                            chrome_args,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            start_new_session=True
                        )

                    self.chrome_pid = chrome_process.pid
                    logging.info(f"[Chrome] 启动进程 PID={self.chrome_pid}")

                    # 等待Chrome完全启动
                    time.sleep(3)

                    # 检查进程是否还在运行
                    if chrome_process.poll() is not None:
                        stdout, stderr = chrome_process.communicate()
                        logging.error(f"[Chrome] 启动失败，进程提早退出")
                        logging.error(f"[Chrome] STDOUT: {stdout.decode('utf-8', errors='ignore')}")
                        logging.error(f"[Chrome] STDERR: {stderr.decode('utf-8', errors='ignore')}")
                        raise Exception("[Chrome] 启动失败，进程提早退出")

                    # 等待Chrome的Remote Debugging接口就绪
                    max_wait_time = 30
                    for i in range(max_wait_time):
                        if self._is_chrome_session_alive():
                            self.chrome_session_running = True
                            logging.info(f"[Chrome] 启动成功，用时 {i+1} 秒")
                            return
                        time.sleep(1)
                        if i % 5 == 0:
                            logging.info(f"[Chrome] 等待中 ({i+1}/{max_wait_time})")

                    # 如果等待超时，获取详细的错误信息
                    if chrome_process.poll() is not None:
                        stdout, stderr = chrome_process.communicate()
                        logging.error(f"[Chrome] STDOUT: {stdout.decode('utf-8', errors='ignore')}")
                        logging.error(f"[Chrome] STDERR: {stderr.decode('utf-8', errors='ignore')}")
                    
                    self._terminate_chrome_by_pid()
                    raise Exception("Chrome 启动超时或Remote Debugging接口无响应")
                    
                except Exception as e:
                    self.chrome_session_running = False
                    logging.error(f"[Chrome] 启动异常: {str(e)}")
                    raise e
            else:
                logging.info("[Chrome] 埠已被佔用，尝试连接现有实例")
                if self._is_chrome_session_alive():
                    self.chrome_session_running = True
                    logging.info("[Chrome] 成功连接到现有Chrome实例")
                else:
                    logging.error("[Chrome] 端口被占用但无法连接")
                    raise Exception("Chrome端口被占用但无法连接")

    def _monitor_chrome_session(self):
        while True:
            time.sleep(10)
            with self.chrome_session_lock:
                if self.chrome_session_running and not self._is_chrome_session_alive():
                    logging.warning("[Chrome] 工作階段失效，重啟中...")
                    self.chrome_session_running = False
                    try:
                        self._launch_chrome_session()
                    except Exception as e:
                        logging.error(f"[Chrome] 重啟失敗: {str(e)}")

    def _print_timer(self):
        if self.start_time:
            elapsed = datetime.now() - self.start_time
            logging.info(f"[Timer] 執行時間: {elapsed.seconds} 秒")

    @retry(max_retries=MAX_RETRIES, delay_range=(2, 5))
    def _scrape_with_retry(self, driver, url):
        driver.get(url)
        for _ in range(random.randint(3, 5)):
            random_actions(driver)
            self._print_timer()

        if is_captcha_present(driver):
            raise Exception("偵測到驗證碼！")

        pure_text = self.text_processor.get_pure_text(driver)
        processed_text = self.text_processor.process_with_chatgpt(pure_text)
        full_text = self.text_processor.process_with_chatgpt_md(pure_text)

        # 安全處理
        if isinstance(processed_text, dict):
            summary = processed_text.get("summary", "")
        elif isinstance(processed_text, str):
            summary = processed_text
        else:
            summary = ""

        if isinstance(full_text, dict):
            markdown = full_text.get("markdown", "")
        elif isinstance(full_text, str):
            markdown = full_text
        else:
            markdown = ""

        return {
            "status": "success",
            "title": driver.title,
            "html": driver.page_source,
            "processed_text": summary,
            "full_text": markdown
        }

    def run(self, debug=False, host="0.0.0.0", port=5000):
        if not debug:
            logging.config.dictConfig(LOG_CONFIG)
        monitor_thread = threading.Thread(target=self._monitor_chrome_session, daemon=True)
        monitor_thread.start()
        self.app.run(debug=debug, host=host, port=port, threaded=True, use_reloader=False)