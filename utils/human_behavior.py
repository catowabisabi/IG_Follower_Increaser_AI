"""
人機行為模擬模組
模擬真實用戶的行為模式
"""

import random
import time
import logging
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

def simulate_human_delay(min_sec=0.5, max_sec=1):
    """模擬人為延遲"""
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)
    return delay

def bezier_curve(start, end, control, t):
    """生成貝茲曲線上的點，實現平滑的滑鼠移動"""
    x = int((1 - t) * (1 - t) * start[0] + 2 * (1 - t) * t * control[0] + t * t * end[0])
    y = int((1 - t) * (1 - t) * start[1] + 2 * (1 - t) * t * control[1] + t * t * end[1])
    return (x, y)

def natural_mouse_movement(driver, element=None, end_x=None, end_y=None):
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
            next_x, next_y = bezier_curve((start_x, start_y), (end_x, end_y), (control_x, control_y), t)
            
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

def smooth_scroll(driver, scroll_amount):
    """實現平滑滾動"""
    steps = 10
    for i in range(steps):
        step = scroll_amount / steps
        driver.execute_script(f"window.scrollBy(0, {step});")
        time.sleep(random.uniform(0.05, 0.01))

def random_actions(driver):
    """執行隨機的人為操作"""
    actions = ["scroll", "wait"]
    action = random.choice(actions)
    
    try:
        if action == "scroll":
            # 獲取頁面高度
            page_height = driver.execute_script("return document.body.scrollHeight")
            viewport_height = driver.execute_script("return window.innerHeight")
            max_scroll = page_height - viewport_height
            
            if max_scroll > 0:
                scroll_amount = random.randint(100, min(500, max_scroll))
                smooth_scroll(driver, scroll_amount)
        
        elif action == "wait":
            simulate_human_delay(1, 3)
            
    except Exception as e:
        logging.warning(f"Random action failed: {str(e)}")

def is_captcha_present(driver):
    """檢查是否存在驗證碼，並打印出現的 selector 或關鍵字"""
    captcha_selectors = [
        "#captcha",
        ".captcha-image",
        "#challenge-form",
        "input[name='captcha']",
        "img[src*='captcha']"
    ]
    try:
        for selector in captcha_selectors:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            visible_elements = [el for el in elements if el.is_displayed()]
            if len(visible_elements) > 0:
                print(f"[CAPTCHA] 命中 selector: {selector}，可見元素數量: {len(visible_elements)}")
                return True
    except Exception as e:
        print(f"[CAPTCHA] selector 查找失敗: {e}")
    
    # 關鍵字判斷
    page_source = driver.page_source.lower()
    for indicator in ["verify you are human", "驗證你是人類" "請輸入驗證碼", "please enter the characters"]:
        if indicator in page_source:
            print(f"[CAPTCHA] 命中關鍵字: {indicator}")
            return True
    return False