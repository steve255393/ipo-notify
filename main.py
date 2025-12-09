# -*- coding: utf-8 -*-
import requests
import pandas as pd
from bs4 import BeautifulSoup
from io import StringIO
import yfinance as yf
import os
import time

# LINE Messaging API Channel Access Token
CHANNEL_ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN")
LINE_USER_ID = os.environ.get("LINE_USER_ID")


# -----------------------------------------------
# 🔍 抓取 Histock 「申購中」資料（延長 timeout + 重試）
# -----------------------------------------------
def fetch_histock():
    url = "https://histock.tw/stock/public.aspx"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=headers, timeout=15)  # 延長 timeout
            resp.encoding = 'utf-8'
            break
        except requests.exceptions.RequestException as e:
            print(f"Histock 嘗試 {attempt+1} 失敗: {e}")
            time.sleep(2)
    else:
        print("Histock 請求失敗，略過申購資料")
        return pd.DataFrame()
    
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


# -----------------------------------------------
# 🔍 過濾條件
# -----------------------------------------------
def filter_target(df):
    return df[(df["報酬率(%)"] > 20) | (df["獲利"] > 10000)]


# -----------------------------------------------
# 📈 批次抓取美股行情（TSLA/NVDA/AAPL/MSFT）
# -----------------------------------------------
def get_stocks_batch(symbols):
    try:
        # 批次抓取，auto_adjust=False 避免警告
        data = yf.download(symbols, period="2d", auto_adjust=False)["Close"]
    except Exception as e:
        print(f"yfinance 批次抓取失敗: {e}")
        return [f"{sym} 無法取得行情資料" for sym in symbols]

    results = []
    for sym in symbols:
        today = data[sym].iloc[-1]
        yesterday = data[sym].iloc[-2]
        diff = today - yesterday
        diff_percent = diff / yesterday * 100
        arrow = "🔺" if diff > 0 else "🔻"
        results.append(f"{sym} {arrow} {diff:+.2f} ({diff_percent:+.2f}%)  {today:.2f}")
    return results


# -----------------------------------------------
# 📤 LINE 推播
# -----------------------------------------------
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


# -----------------------------------------------
# 🎯 主流程
# -----------------------------------------------
def process():
    # ---------- ① 抓取 申購中 ----------
    df = fetch_histock()
    msg1 = "📢 今日符合條件申購標的：\n(無)"  # 預設無

    if not df.empty:
        df_target = filter_target(df)
        if not df_target.empty:
            msg_items = [
                f"{row['股票代號 名稱']}(投報率:{row['報酬率(%)']}% 獲利:{row['獲利']}元)"
                for _, row in df_target.iterrows()
            ]
            msg1 = "📢 今日符合條件申購標的：\n" + "、".join(msg_items)

    print(msg1)

    # ---------- ② 批次抓取四檔美股行情 ----------
    symbols = ["TSLA", "NVDA", "AAPL", "MSFT"]
    stock_lines = get_stocks_batch(symbols)
    msg2 = "📈 美股行情：\n" + "\n".join(stock_lines)

    print(msg2)

    # ---------- ③ 整合推播 ----------
    final_msg = msg1 + "\n\n" + msg2
    send_line_message(LINE_USER_ID, final_msg)


# -----------------------------------------------
# 🚀 主程式入口
# -----------------------------------------------
if __name__ == "__main__":
    print("=== 執行最新 main.py ===")
    process()
