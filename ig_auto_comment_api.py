from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import List
import os
import logging

from controller.ig_controller import IGController

app = FastAPI()

class IGRequest(BaseModel):
    IG_USERNAME: str
    IG_PASSWORD: str
    hashtags: List[str]
    search_keywords: List[str]
    random_reply: List[str]
    court: int = 3
    click_court: int = 3

@app.post("/run_ig")
def run_ig_task(params: IGRequest):
    # 設定環境變數
    os.environ['IG_USERNAME'] = params.IG_USERNAME
    os.environ['IG_PASSWORD'] = params.IG_PASSWORD

    # 動態覆蓋 config 變數（如果你是 import config 進 ig_controller.py 的話）
    import controller.ig_controller as ig_mod
    ig_mod.hashtags = params.hashtags
    ig_mod.search_keywords = params.search_keywords
    ig_mod.random_reply = params.random_reply

    # 執行 IG 流程
    try:
        ig = IGController(ig_user_id=params.IG_USERNAME)
        ig.login()
        ig.search_keywords(court=params.court, click_court=params.click_court)
        ig.close()
        return {"status": "success"}
    except Exception as e:
        logging.error(f"IG 任務失敗: {e}")
        return {"status": "error", "detail": str(e)}