# -*- coding: utf-8 -*-
import requests
import pandas as pd
from bs4 import BeautifulSoup
from io import StringIO
import os

# 你的 LINE Messaging API Channel Access Token
CHANNEL_ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN")

# 接收訊息的使用者或群組 ID
LINE_USER_ID = os.environ.get("LINE_USER_ID")  # 可以是自己的 userId 或群組Id

def fetch_histock():
    url = "https://histock.tw/stock/public.aspx"
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers)
    resp.encoding = 'utf-8'

    soup = BeautifulSoup(resp.text, "lxml")

    # 找到包含「申購中」的 table
    tables = soup.find_all("table")
    target_table = None
    for table in tables:
        if "申購中" in table.get_text():
            target_table = table
            break

    if target_table is None:
        print("找不到包含申購中資料的 table")
        return pd.DataFrame()

    df = pd.read_html(StringIO(str(target_table)))[0]
    df.columns = df.columns.str.strip()

    # 過濾備註為申購中
    if "備註" not in df.columns:
        print("表格中沒有備註欄位")
        return pd.DataFrame()
    df = df[df["備註"].str.strip().str.contains("申購中", na=False)].copy()

    # 安全轉換欄位
    for col in ["報酬率(%)", "獲利"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace("%", "", regex=False).str.replace("--", "", regex=False).str.strip()
            df[col] = pd.to_numeric(df[col], errors="coerce")
        else:
            print(f"表格缺少欄位: {col}")
            return pd.DataFrame()


    return df

def filter_target(df):
    return df[(df["報酬率(%)"] > 20) | (df["獲利"] > 10000)]

def send_line_message(user_id, message):
    if not CHANNEL_ACCESS_TOKEN:
        print("CHANNEL_ACCESS_TOKEN 未設定，無法發送 LINE 訊息")
        return
    if not user_id:
        print("LINE_USER_ID 未設定，無法發送 LINE 訊息")
        return

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "to": user_id,
        "messages": [{"type": "text", "text": message}]
    }
    resp = requests.post(url, headers=headers, json=data)
    if resp.status_code != 200:
        print(f"LINE 訊息發送失敗: {resp.status_code} {resp.text}")

def process():
    df = fetch_histock()
    if df.empty:
        print("沒有抓到任何資料")
        return

    df_target = filter_target(df)
    if df_target.empty:
        print("今日沒有符合條件的股票")
        return

    # 單行字串格式
    msg_items = [
        f"{row['股票代號 名稱']}(投報率:{row['報酬率(%)']}% 獲利:{row['獲利']}元)"
        for _, row in df_target.iterrows()
    ]
    msg = "📢 今日符合條件申購標的：\n" + "、".join(msg_items)

    print(msg)
    send_line_message(LINE_USER_ID, msg)

if __name__ == "__main__":
    print("=== 執行最新 main.py ===")
    process()

