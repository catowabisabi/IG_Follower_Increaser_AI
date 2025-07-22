# Instagram 追蹤者增長工具 | Instagram Follower Growth Tool

## 功能簡介 | Features

### 繁體中文：
這是一個自動化的 Instagram 互動工具，主要功能包括：
- 🔍 自動瀏覽指定主題標籤
- ➕ 自動關注目標用戶
- ❤️ 自動點讚貼文
- 💬 自動留言互動
- 🤖 使用 GPT-4 智能回覆評論
- 📊 追蹤互動歷史記錄
- 🔄 避免重複關注同一用戶

### English:
This is an automated Instagram engagement tool with the following features:
- 🔍 Automated hashtag exploration
- ➕ Automated user following
- ❤️ Automated post liking
- 💬 Automated commenting
- 🤖 GPT-4 powered intelligent comment replies
- 📊 Interaction history tracking
- 🔄 Duplicate follow prevention

## 使用說明 | Usage Instructions

### 繁體中文：

1. 環境設置：
   - 安裝 Python 3.x
   - 安裝 Chrome 瀏覽器
   - 下載對應版本的 ChromeDriver

2. 安裝依賴：
   ```bash
   pip install -r requirements.txt
   ```

3. 配置環境變數：
   創建 `.env` 檔案並填入以下資訊：
   ```
   USERNAME=你的Instagram用戶名
   PASSWORD=你的Instagram密碼
   CHROMEDRIVER_PATH=ChromeDriver的路徑
   OPENAI_API_KEY=你的OpenAI API金鑰
   ```

4. 配置互動設置：
   在 `config.py` 中設置：
   - 要追蹤的主題標籤列表
   - 自動留言內容列表

5. 運行程式：
   ```bash
   python -m uvicorn ig_auto_comment_api:app --reload
   ```

### English:

1. Environment Setup:
   - Install Python 3.x
   - Install Chrome browser
   - Download matching ChromeDriver version

2. Install Dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure Environment Variables:
   Create a `.env` file with the following information:
   ```
   USERNAME=Your Instagram username
   PASSWORD=Your Instagram password
   CHROMEDRIVER_PATH=Path to ChromeDriver
   OPENAI_API_KEY=Your OpenAI API key
   ```

4. Configure Interaction Settings:
   In `config.py`, set up:
   - List of hashtags to follow
   - List of automatic comments

5. Run the Program:
   ```bash
   python run.py
   ```

## 注意事項 | Important Notes

### 繁體中文：
- ⚠️ 請謹慎使用自動化工具，避免違反 Instagram 使用條款
- 🕒 建議設置適當的時間間隔，避免操作過於頻繁
- 🔐 請妥善保管您的帳號密碼和 API 金鑰
- 📝 定期檢查互動記錄，確保運作正常

### English:
- ⚠️ Use automation tools responsibly to avoid violating Instagram's terms of service
- 🕒 Set appropriate time intervals to avoid too frequent operations
- 🔐 Keep your credentials and API keys secure
- 📝 Regularly check interaction logs to ensure proper operation

## 系統需求 | System Requirements

### 繁體中文：
- Python 3.x
- Chrome 瀏覽器
- ChromeDriver
- 穩定的網路連接
- OpenAI API 金鑰（用於 GPT-4 功能）

### English:
- Python 3.x
- Chrome Browser
- ChromeDriver
- Stable Internet Connection
- OpenAI API Key (for GPT-4 functionality)
