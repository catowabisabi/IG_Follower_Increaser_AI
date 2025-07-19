
import os
import datetime
import logging

# --- 設定 ---
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(asctime)s - %(message)s', datefmt='%H:%M:%S')

# --- 主要類別 ---

class HtmlSaver:
    @staticmethod
    def save_html_to_file(html_content):
        if not html_content:
            logging.warning("HTML 內容為空，跳過保存。")
            return
            
        output_dir = 'output'
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'instagram_page_{timestamp}.html'
        filepath = os.path.join(output_dir, filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            logging.info(f"HTML 已成功保存至: {filepath}")
        except IOError as e:
            logging.error(f"保存 HTML 文件失敗: {e}")
