import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))  # 如果是兩層就加 '..', '..'
if project_root not in sys.path:
    sys.path.insert(0, project_root)


import logging
import time
from ig.class_cdp import CDPChromeClient


from press_sequence import follow_sequence, img_info_page_sequence

def main():
    logging.info("--- 啟動 Instagram 自動化腳本 ---")
    cdp_client = CDPChromeClient(ws_url="ws://localhost:9222/devtools/page/B26E2C5BFC98B0A0B62C7A436014D0A3")
    try:
        
        cdp_client.press_button_sequence(follow_sequence, delay=2.5)
        cdp_client.press_button_sequence(img_info_page_sequence, delay=2.5)

        username = cdp_client.get_bk_components_heading()
        if username:
            logging.info(f"已 follow 用戶: {username[0]['text']}")
            result = cdp_client.click_button_by_texts(['关闭'])

        #cdp_client.close_img()
        #cdp_client.scroll_down()  # 滾動一下
        #cdp_client.scroll_down_loop(times=10, interval=1.5)  # 連續滾動 10 次


      

      
    except Exception as e:
        logging.error(f"主流程中發生意外錯誤: {e}", exc_info=True)



if __name__ == "__main__":
    main()