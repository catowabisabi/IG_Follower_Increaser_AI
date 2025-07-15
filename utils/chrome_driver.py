"""
Chrome 驅動模組
處理所有與 Chrome 瀏覽器相關的功能
"""

import logging
import random
import json
import os
import tempfile
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from config.settings import (
    CHROME_PATH,
    USER_AGENTS,
    CHROME_PORT,
    PAGE_LOAD_TIMEOUT,
    CHROME_ARGS, # 導入 CHROME_ARGS
    CHROME_DATA_DIR # 導入持久化的數據目錄
)

# 日誌配置（通常在 main.py 或 api.py 中完成，這裡僅確保其存在，避免未初始化錯誤）
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# 重新定義 ChromeWithPrefs，使其更簡潔，主要用於確保 prefs 的正確寫入
# 但在連接到現有實例時，Selenium 不應修改 prefs
class ChromeWithPrefs(webdriver.Chrome):
    """自定義 Chrome 類別，用於在非連接模式下寫入 preferences 文件"""
    def __init__(self, *args, **kwargs):
        options = kwargs.get('options')
        if options and "prefs" in options._experimental_options:
            self._handle_prefs(options) # 處理 prefs
        super().__init__(*args, **kwargs)

    def _handle_prefs(self, options):
        """處理 Chrome preferences，將其寫入用戶資料目錄下的 Preferences 文件"""
        prefs = options._experimental_options["prefs"]
        
        # 獲取 user-data-dir 參數
        user_data_arg = next((arg for arg in options._arguments if "--user-data-dir=" in arg), None)
        if user_data_arg:
            user_data_dir = Path(user_data_arg.split("=", 1)[1])
        else:
            # 如果沒有明確設置 user-data-dir，那麼 Selenium 會使用默認的臨時目錄。
            # 這裡我們嘗試使用 BASE_DIR / "selenium_tmp_profile" 或類似的，但這會很複雜
            # 最好的方式是確保在 add_argument 時就設置好
            logging.warning("No explicit --user-data-dir found in options. Preferences might be written to a temporary default profile.")
            # 為了避免複雜性，我們假定如果沒有設置，Selenium 會處理它，
            # 並且我們在 create_chrome_options 中已經確保了臨時目錄的設置。
            # 因此，這裡直接返回，讓 Selenium 處理 prefs（如果它能的話）。
            # 或者，更明確地，我們可以強制使用一個臨時目錄來寫入這個 prefs。
            user_data_dir = Path(tempfile.mkdtemp(prefix="selenium_temp_prefs_"))
            options.add_argument(f"--user-data-dir={user_data_dir}")
            logging.debug(f"Forced temporary user data dir for preferences: {user_data_dir}")


        default_dir = user_data_dir / "Default"
        default_dir.mkdir(parents=True, exist_ok=True)
        
        def convert_dot_keys(prefs_dict):
            result = {}
            for key, value in prefs_dict.items():
                parts = key.split('.')
                target = result
                for part in parts[:-1]:
                    target = target.setdefault(part, {})
                target[parts[-1]] = value
            return result
        
        prefs_file = default_dir / "Preferences"
        converted_prefs = convert_dot_keys(prefs)
        try:
            with open(prefs_file, 'w', encoding='utf-8') as f:
                json.dump(converted_prefs, f, indent=4)
            logging.info(f"成功寫入 Chrome Preferences 到: {prefs_file}")
        except Exception as e:
            logging.error(f"寫入 Chrome Preferences 失敗: {e}. 可能用戶資料目錄無寫入權限或路徑錯誤。")
        
        del options._experimental_options["prefs"] # 清除防止父類重複處理

def create_chrome_options(headless=False):
    """創建 Chrome 選項，不包括 debuggerAddress 和 user-data-dir"""
    chrome_options = Options()

    # 設置 User-Agent
    chrome_options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")

    if headless:
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-gpu") # 在無頭模式下，通常啟用此項

    # 添加 settings.py 中定義的通用 Chrome 參數
    for arg in CHROME_ARGS:
        # 避免重複添加已經手動處理的參數，例如 --headless
        # 這些參數也不應該包含 user-data-dir 或 debuggerAddress
        if not any(keyword in arg for keyword in ["--headless", "--user-data-dir", "--remote-debugging-port"]):
            chrome_options.add_argument(arg)

    # 進階偏好設定 (會在 ChromeWithPrefs 中寫入文件)
    prefs = {
        "profile.default_content_settings.popups": 0,
        "profile.default_content_setting_values.notifications": 2, # 禁用通知
        "profile.default_content_setting_values.images": 1, # 允許圖片
        "profile.default_content_setting_values.javascript": 1, # 允許 JavaScript
        "profile.managed_default_content_settings.javascript": 1, # 確保 JS 啟用
        "profile.default_content_setting_values.plugins": 1, 
        "profile.default_content_setting_values.geolocation": 2, # 禁用地理位置請求
        "profile.default_content_setting_values.media_stream": 2, # 禁用媒體流請求
        "profile.managed_default_content_settings.images": 1,
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "profile.managed_default_content_settings.cookies": 1, # 允許 cookies
        "profile.default_content_setting_values.cookies": 1, # 允許 cookies
        "profile.managed_default_content_settings.plugins": 1,
        "profile.default_content_settings.state.flash": 0, # 禁用 Flash
        "profile.content_settings.exception_patterns": {},
        "download.directory_upgrade": True,
        "download.prompt_for_download": False,
        "plugins.always_open_pdf_externally": True
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    return chrome_options

def create_driver(use_session_port=False, headless=False):
    """創建並配置 Chrome WebDriver"""
    
    service = Service(ChromeDriverManager().install())
    
    if use_session_port:
        # 連接到現有的 Chrome 實例
        chrome_options = Options()
        chrome_options.add_experimental_option("debuggerAddress", f"127.0.0.1:{CHROME_PORT}")
        # 在連接到現有實例時，不應再設置其他的 Chrome 選項，
        # 因為這些選項在 Chrome 啟動時就已確定。
        # 也不需要設置 user-data-dir 或處理 prefs，因為這些已經是運行中實例的狀態。
        logging.info(f"連接到現有 Chrome 實例 (port {CHROME_PORT})")
        driver = webdriver.Chrome(service=service, options=chrome_options)
    else:
        # 啟動一個新的 Chrome 實例
        chrome_options = create_chrome_options(headless)
        # 對於新的實例，我們需要為它分配一個用戶資料目錄
        # 由於我們沒有在 settings 中直接給出 `--user-data-dir`，
        # Selenium 默認會創建一個臨時目錄，這對於每次獨立的驅動會話是合理的。
        # 如果需要持久化非共享模式下的數據，則需要更複雜的目錄管理邏輯。
        # 此處繼續使用自動創建的臨時目錄。
        logging.info("創建新的 Chrome 實例")
        driver = ChromeWithPrefs(service=service, options=chrome_options) # 使用自定義的類

    # 注入反檢測腳本，對於兩種模式都應該執行
    inject_evasion_scripts(driver)
    
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
    logging.info(f"WebDriver 已成功啟動，頁面加載超時設置為 {PAGE_LOAD_TIMEOUT} 秒")
    return driver

def inject_evasion_scripts(driver):
    """注入反檢測腳本"""
    # 基本的 webdriver 檢測規避
    # 這段腳本應在每次頁面加載前運行
    script = """
        // 基本 webdriver 檢測
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        
        // 模擬真實瀏覽器特徵 (Plugins)
        Object.defineProperty(navigator, 'plugins', {
            get: () => {
                const plugins = [
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
                        filename: "mhjfbmdgcfjbbpaeojofohoefgiehjai", // 這是Chrome PDF Viewer的ID
                        length: 1,
                        name: "Chrome PDF Viewer"
                    }
                ];
                plugins.item = (index) => plugins[index] || null;
                plugins.namedItem = (name) => plugins.find(p => p.name === name) || null;
                return plugins;
            }
        });
        
        // 模擬語言設定
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en', 'zh-TW', 'zh'] // 添加 zh，更常用
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
            },
            // 添加一些更完整的 Chrome 對象模擬，例如 `webstore`
            webstore: {
                // 通常是一個空對象或包含一些方法
            },
            csi: function() { /* ... */ }, // 模擬 csi 方法
            loadTimes: function() { /* ... */ } // 
        };
        
        // 模擬硬體特徵
        Object.defineProperty(navigator, 'hardwareConcurrency', {
            get: () => navigator.hardwareConcurrency || 8 // 提供一個默認值，或使用真實值
        });
        Object.defineProperty(navigator, 'deviceMemory', {
            get: () => navigator.deviceMemory || 8 // 提供一個默認值，或使用真實值
        });
        Object.defineProperty(screen, 'colorDepth', {
            get: () => screen.colorDepth || 24
        });
        
        // 模擬 WebGL (更複雜的指紋) - 這些值應該更接近真實環境
        // 這裡的值可以根據你希望模擬的顯卡來調整
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            // UNMASKED_VENDOR_WEBGL
            if (parameter === 37445) { 
                return 'Google Inc.'; // 或 'NVIDIA Corporation', 'Intel Inc.'
            }
            // UNMASKED_RENDERER_WEBGL
            if (parameter === 37446) {
                return 'ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (LLVM 15.0.3)), SwiftShader)'; 
                // 或 'NVIDIA GeForce RTX 3080', 'Intel(R) UHD Graphics 630'
            }
            return getParameter.apply(this, [parameter]);
        };
        
        // 模擬其他瀏覽器特徵
        Object.defineProperty(navigator, 'platform', {
            get: () => 'Win32' // 或 'MacIntel', 'Linux x86_64'
        });
        Object.defineProperty(navigator, 'maxTouchPoints', {
            get: () => 0 // 桌面瀏覽器通常為 0
        });
        Object.defineProperty(navigator, 'vendor', {
            get: () => 'Google Inc.'
        });

        // 欺騙 getClientRects 和 getBoundingClientRect，這是某些指紋庫使用的
        const originalGetClientRects = Element.prototype.getClientRects;
        Element.prototype.getClientRects = function() {
            const rects = originalGetClientRects.apply(this, arguments);
            // 可以根據需要對 rects 進行隨機化或修改
            return rects;
        };

        const originalGetBoundingClientRect = Element.prototype.getBoundingClientRect;
        Element.prototype.getBoundingClientRect = function() {
            const rect = originalGetBoundingClientRect.apply(this, arguments);
            // 可以根據需要對 rect 進行隨機化或修改
            return rect;
        };

        // 避免 toString 函數被識別為自動化工具 (此部分可能導致問題，暫時保留，若再次報錯則移除)
        // 這段代碼嘗試代理瀏覽器的內部函數，某些 ChromeDriver 版本可能不允許。
        // 但由於您的錯誤是 'excludeSwitches'，這個問題應該不是直接由它引起。
        ['', 'get', 'set'].forEach(method => {
            const descriptor = Object.getOwnPropertyDescriptor(WebGLRenderingContext.prototype, method + 'Parameter');
            if (descriptor && descriptor.value) {
                Object.defineProperty(WebGLRenderingContext.prototype, method + 'Parameter', {
                    'value': new Proxy(descriptor.value, {
                        apply: function(target, thisArg, args) {
                            return Reflect.apply(target, thisArg, args);
                        }
                    })
                });
            }
        });
    """
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": script})
    logging.info("反偵測腳本已注入。")