# example.py
import os
from dotenv import load_dotenv

# 加載 .env 文件
load_dotenv()

# 獲取環境變數
username = os.getenv("IG_USERNAME")
password = os.getenv("IG_PASSWORD")

# 打印結果 (不要在正式環境中打印密碼，這裡只是測試用)
print(f"Instagram Username: {username}")
print(f"Instagram Password: {password}")