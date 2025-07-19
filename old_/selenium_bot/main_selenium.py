"""
主程式入口
啟動爬蟲 API 服務
"""
import sys
import os
import argparse
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging.config
from scraper.api import WebScraperAPI
from config.settings import LOG_CONFIG

def parse_arguments():
    """解析命令行參數"""
    parser = argparse.ArgumentParser(description='爬蟲 API 服務')
    parser.add_argument('--headless', 
                       action='store_true',
                       help='是否使用 headless 模式（無界面模式）')
    parser.add_argument('--debug',
                       action='store_true',
                       help='是否使用調試模式')
    parser.add_argument('--port',
                       type=int,
                       default=5000,
                       help='API 服務端口號')
    parser.add_argument('--host',
                       default='0.0.0.0',
                       help='API 服務主機地址')
    
    return parser.parse_args()

def main():
    """主程式入口點"""
    # 解析命令行參數
    args = parse_arguments()
    
    # 確保必要的目錄存在
    os.makedirs("logs", exist_ok=True)
    os.makedirs("chrome-data", exist_ok=True)
    
    # 配置日誌
    logging.config.dictConfig(LOG_CONFIG)
    
    # 設置環境變數以控制 headless 模式
    os.environ['SCRAPER_HEADLESS'] = str(args.headless).lower()
    
    # 啟動 API 服務
    app = WebScraperAPI()
    app.run(debug=args.debug, host=args.host, port=args.port)

if __name__ == "__main__":
    main() 