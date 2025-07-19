"""
配置文件
包含所有的設置和配置項
"""

import os
import sys
from pathlib import Path
import logging.handlers # 導入此模塊用於日誌配置
import os
from dotenv import load_dotenv
load_dotenv(override=True)

# 基礎路徑設置
BASE_DIR = Path(__file__).resolve().parent.parent
CHROME_DATA_DIR = BASE_DIR / "chrome-data"
CHROME_LOGIN_DATA_DIR = BASE_DIR / "chrome-login-data"
LOGS_DIR = BASE_DIR / "logs"

# 確保必要的目錄存在
CHROME_DATA_DIR.mkdir(exist_ok=True)
CHROME_LOGIN_DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# Chrome 設置
def get_chrome_path():
    """自動檢測Chrome瀏覽器路徑"""
    possible_paths = [
        # 用戶自定義路徑 (高優先級)
        os.getenv('CHROME_PATH'),
        # Windows 常見路徑
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        # 用戶安裝路徑
        os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
        # macOS 路徑
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        # Linux 路徑
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium-browser",
        # Edge 作為備選 (僅在找不到Chrome時考慮)
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    
    for path in possible_paths:
        if path and Path(path).exists():
            return str(Path(path))
    
    # 如果都找不到，返回操作系統默認路徑（需要用戶手動確認或安裝）
    if sys.platform.startswith("win"):
        return r"C:\Program Files\Google\Chrome\Application\chrome.exe" # 依然提供一個默認值
    elif sys.platform.startswith("darwin"):
        return "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    else:
        return "/usr/bin/google-chrome"

CHROME_PATH = get_chrome_path()
CHROME_PORT = 9222
MAX_RETRIES = 3
PAGE_LOAD_TIMEOUT = 30  # 增加超時時間

# Chrome 啟動參數：**精簡化，移除可能觸發 CAPTCHA 的參數，並移除 conflict 的參數**
# 這些是比較安全且常見的反偵測參數
CHROME_ARGS = [
    "--no-sandbox", # 某些環境（如Docker）需要
    "--disable-dev-shm-usage", # 在某些Linux環境下防止內存不足問題
    # "--disable-gpu", # 雖然之前建議保留，但若引起問題可移除。在無頭模式下可能不需要。
    "--disable-software-rasterizer", 
    "--disable-extensions", # 禁用擴展
    "--disable-plugins", # 禁用插件
    "--disable-default-apps", # 禁用默認應用程序
    "--no-first-run", # 首次運行不顯示歡迎頁
    "--no-default-browser-check", # 不檢查是否為預設瀏覽器
    "--disable-infobars", # 禁用信息欄
    "--disable-notifications", # 禁用通知
    "--disable-popup-blocking", # 禁用彈出窗口阻止
    "--disable-save-password-bubble", # 禁用保存密碼提示
    "--disable-translate", # 禁用翻譯提示
    "--ignore-certificate-errors", # 忽略證書錯誤 (謹慎使用)
    "--dns-prefetch-disable", # 禁用DNS預取
    "--disable-features=IsolateOrigins,site-per-process", # 減少一些進程隔離，可能提高兼容性

    # 重要的反偵測參數，這些是直接禁用自動化標記的
    "--disable-automation", # 新增：禁用自動化提示橫幅 (舊版參數，但仍有作用)
    "--enable-automation", # 與上面衝突，確保不要同時使用，這裡移除
    "--disable-blink-features=AutomationControlled", # 核心參數：隱藏 navigator.webdriver
]

# API 設置
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# User Agent 池
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.5672.92 Mobile Safari/537.36",
]

# 重試設置
RETRY_DELAYS = (2, 5)  # 重試延遲範圍(秒)
RETRY_EXCEPTIONS = (
    Exception,
    # 可以添加更具體的異常類型，例如 selenium.common.exceptions.WebDriverException
)

# 請求設置
REQUEST_TIMEOUT = 30  # 請求超時時間(秒)
MAX_CONCURRENT_REQUESTS = 3  # 最大併發請求數

# 日誌設置
LOG_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s - %(levelname)s - %(message)s'
        },
        'detailed': {
            'format': '[%(asctime)s] %(levelname)s in %(module)s:%(lineno)d - %(message)s'
        },
        'simple': {
            'format': '%(levelname)s - %(message)s'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
            'stream': 'ext://sys.stdout',
            'level': 'INFO' # 在開發環境可以設置為 DEBUG
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'detailed',
            'filename': str(LOGS_DIR / 'scraper.log'),
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'encoding': 'utf-8',
            'level': 'INFO' # 在生產環境設置為 INFO 或 WARNING
        },
        'error_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'detailed',
            'filename': str(LOGS_DIR / 'scraper_error.log'),
            'maxBytes': 10485760,  # 10MB
            'backupCount': 3,
            'encoding': 'utf-8',
            'level': 'ERROR'
        }
    },
    'loggers': {
        '': { # root logger
            'handlers': ['console', 'file', 'error_file'],
            'level': 'INFO', # 整體級別設為 INFO
            'propagate': False
        },
        # 抑制第三方庫的日誌，避免日誌過於龐大
        'urllib3': {
            'level': 'WARNING',
            'handlers': ['console'],
            'propagate': False
        },
        'selenium': {
            'level': 'WARNING',
            'handlers': ['console'],
            'propagate': False
        },
        'requests': {
            'level': 'WARNING',
            'handlers': ['console'],
            'propagate': False
        }
    }
}

# 開發/調試設置
DEBUG_MODE = os.getenv('DEBUG_MODE', 'false').lower() == 'true'
HEADLESS_MODE = os.getenv('SCRAPER_HEADLESS', 'true').lower() == 'true'

# 性能監控設置
ENABLE_PERFORMANCE_MONITORING = True
PERFORMANCE_LOG_INTERVAL = 30  # 秒

# 驗證函數
def validate_settings():
    """驗證設置是否正確"""
    issues = []
    
    # 檢查Chrome路徑
    if not Path(CHROME_PATH).exists():
        issues.append(f"Chrome路徑不存在: {CHROME_PATH}")
    
    # 檢查端口
    if not (1024 <= CHROME_PORT <= 65535):
        issues.append(f"Chrome端口無效: {CHROME_PORT}")
    
    # 檢查API密鑰
    if not OPENAI_API_KEY:
        issues.append("未設置 OPENAI_API_KEY 環境變量")
    
    # 檢查目錄權限
    try:
        test_file = LOGS_DIR / "test.tmp"
        test_file.touch()
        test_file.unlink()
    except Exception as e:
        issues.append(f"日誌目錄無寫入權限或創建測試文件失敗: {e}")
    
    return issues

# 配置摘要函數
def print_config_summary():
    """打印配置摘要"""
    print("=" * 60)
    print("🔧 爬蟲配置摘要")
    print("=" * 60)
    print(f"Chrome路徑: {CHROME_PATH}")
    print(f"Chrome路徑存在: {'✅' if Path(CHROME_PATH).exists() else '❌'}")
    print(f"Chrome端口: {CHROME_PORT}")
    print(f"頁面加載超時: {PAGE_LOAD_TIMEOUT}秒")
    print(f"最大重試次數: {MAX_RETRIES}")
    print(f"最大併發請求: {MAX_CONCURRENT_REQUESTS}")
    print(f"調試模式: {'✅' if DEBUG_MODE else '❌'}")
    print(f"無頭模式: {'✅' if HEADLESS_MODE else '❌'}")
    print(f"OpenAI API: {'✅' if OPENAI_API_KEY else '❌'}")
    print(f"日誌目錄: {LOGS_DIR}")
    print(f"Chrome數據目錄: {CHROME_DATA_DIR}")
    print(f"Chrome登錄數據目錄: {CHROME_LOGIN_DATA_DIR}")
    print("=" * 60)
    
    # 檢查配置問題
    issues = validate_settings()
    if issues:
        print("⚠️  配置問題:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("✅ 所有配置檢查通過")
    print("=" * 60)

# 如果直接運行此文件，則打印配置摘要
if __name__ == "__main__":
    print_config_summary()