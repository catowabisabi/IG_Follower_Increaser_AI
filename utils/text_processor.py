"""
文本處理模組
處理爬取的文本，包括 OpenAI 整合
"""

import logging
from openai import OpenAI
from selenium.webdriver.common.by import By
from config.settings import OPENAI_API_KEY

class TextProcessor:
    def __init__(self):
        """初始化文本處理器"""
        self.openai_api_key = OPENAI_API_KEY
        if not self.openai_api_key:
            logging.warning("未設置 OPENAI_API_KEY 環境變數")

    def get_pure_text(self, driver):
        """獲取頁面的純文字內容"""
        try:
            # 使用 body 標籤來獲取所有可見的文字
            body = driver.find_element(By.TAG_NAME, "body")
            return body.text
        except Exception as e:
            logging.warning(f"獲取純文字失敗: {str(e)}")
            return ""

    def process_with_chatgpt(self, text):
        """使用 ChatGPT 處理文本並返回摘要"""
        try:
            if not self.openai_api_key:
                logging.error("未設置 OpenAI API Key")
                return {"error": "未設置 OpenAI API Key"}

            if not text:
                logging.error("輸入文本為空")
                return {"error": "輸入文本為空"}

            client = OpenAI(api_key=self.openai_api_key)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "請總結以下文本的主要內容，並提取關鍵信息："},
                    {"role": "user", "content": text}
                ],
                max_tokens=500
            )
            
            if not response.choices:
                logging.error("OpenAI API 未返回有效回應")
                return {"error": "API 未返回有效回應"}
            
            content = response.choices[0].message.content
            if not content:
                logging.error("API 返回的內容為空")
                return {"error": "API 返回的內容為空"}
            
            return {
                "summary": content,
                "status": "success"
            }
        except Exception as e:
            logging.error(f"ChatGPT 處理失敗: {str(e)}")
            return {"error": str(e)}

    def process_with_chatgpt_md(self, text):
        """使用 ChatGPT 處理文本並返回 Markdown 格式的詳細分析"""
        try:
            if not self.openai_api_key:
                logging.error("未設置 OpenAI API Key")
                return {"error": "未設置 OpenAI API Key"}

            if not text:
                logging.error("輸入文本為空")
                return {"error": "輸入文本為空"}

            client = OpenAI(api_key=self.openai_api_key)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": """請對以下工作職位進行詳細分析，並以 Markdown 格式輸出，包含以下部分：
                    
# 職位分析報告

## 基本信息
- 職位名稱
- 公司名稱
- 工作地點
- 薪資範圍（如有）
- 工作類型（全職/兼職/合同）

## 職責描述
- 主要職責
- 次要職責
- 特殊要求

## 要求條件
- 教育背景
- 工作經驗
- 技能要求
- 語言要求

## 福利待遇
- 薪資福利
- 其他福利

## 公司信息
- 公司簡介
- 公司規模（如有）
- 公司文化（如有）

## 其他信息
- 工作時間
- 遠程工作選項
- 特殊說明

## 關鍵字
- 技能關鍵字
- 行業關鍵字
                    """},
                    {"role": "user", "content": text}
                ],
                max_tokens=1000
            )
            
            if not response.choices:
                logging.error("OpenAI API 未返回有效回應")
                return {"error": "API 未返回有效回應"}
            
            content = response.choices[0].message.content
            if not content:
                logging.error("API 返回的內容為空")
                return {"error": "API 返回的內容為空"}
            
            return {
                "markdown": content,
                "status": "success"
            }
        except Exception as e:
            logging.error(f"ChatGPT Markdown 處理失敗: {str(e)}")
            return {"error": str(e)} 