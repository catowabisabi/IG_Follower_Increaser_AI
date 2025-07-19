current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))  # 如果是兩層就加 '..', '..'
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import time
import os
import logging
import os
import sys
from ig.class_cdp import CDPChromeClient




def main():
    logging.info("--- 啟動 Instagram 自動化腳本 ---")
    cdp_client = CDPChromeClient(ws_url="ws://localhost:9222/devtools/page/B26E2C5BFC98B0A0B62C7A436014D0A3")
    try:
        result = cdp_client.click_button_by_texts(['保存信息', '儲存資料'])
        result = cdp_client.click_element_by_aria_label(['首页'])
        result = cdp_client.click_element_by_aria_label(['搜索'])
        result = cdp_client.type_into_element_by_aria_label('搜索输入', 'AI 美女')
        time.sleep(2)
        result = cdp_client.click_element_by_aria_label(['关键词'])
        result = cdp_client.click_all_images_one_by_one()


    except Exception as e:
        logging.error(f"主流程中發生意外錯誤: {e}", exc_info=True)
    #finally:
  
    
        #logging.info("--- 腳本結束。正在關閉連接（等10秒） ---")
        #time.sleep(10)
        #cdp_client.close()


if __name__ == "__main__":
    main()
