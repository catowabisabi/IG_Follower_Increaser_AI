from selenium.webdriver.common.by import By
import time
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

class InstagramWebUIController:
    def __init__(self, driver):
        self.driver = driver

    def click_save_login_button(self):
        time.sleep(2)
        try:
            wait = WebDriverWait(self.driver, 10)
            save_login_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, '//button[contains(text(), "儲存資料")]'))
            )
            if save_login_button:
                save_login_button.click()
                print("[Info] Clicked save login button")
            else:
                print("[Info] No save login button found")
        except Exception as e:
            print(f"[Error] Could not click save login button: {e}")

if __name__ == "__main__":
    ic = InstagramWebUIController
    
