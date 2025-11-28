# -*- coding: utf-8 -*-
import requests
import pandas as pd
from io import StringIO
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 環境變數
LINE_TOKEN = os.environ.get("LINE_TOKEN")
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER")

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

def fetch_histock():
    url = "https://histock.tw/stock/public.aspx"
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers)
    resp.encoding = 'utf-8'
    html = StringIO(resp.text)
    tables = pd.read_html(html)
    df = tables[0]
    df = df[df["備註"].str.contains("申購中", na=False)]
    df["報酬率(%)"] = df["報酬率(%)"].str.replace("%", "", regex=False).astype(float)
    df["獲利"] = df["獲利"].astype(float)
    return df

def filter_target(df):
    return df[(df["報酬率(%)"] > 20) | (df["獲利"] > 10000)]

def send_line(msg):
    url = "https://notify-api.line.me/api/notify"
    headers = {"Authorization": "Bearer " + LINE_TOKEN}
    data = {"message": msg}
    requests.post(url, headers=headers, data=data)

def send_email(subject, body):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()
    server.login(EMAIL_SENDER, EMAIL_PASSWORD)
    server.send_message(msg)
    server.quit()

def process():
    baseline_file = "baseline.csv"
    prev_df = pd.read_csv(baseline_file) if os.path.exists(baseline_file) else None
    df = fetch_histock()
    df_target = filter_target(df)
    df_target.to_csv(baseline_file, index=False)

    if prev_df is None:
        print("首次執行，建立 baseline，不發送通知。")
        return

    merged = pd.merge(df_target, prev_df, how="outer", indicator=True)
    new_items = merged[merged["_merge"] == "left_only"]

    if len(new_items) == 0:
        print("今日無新增高報酬標的")
        return

    msg = "📢 新增符合條件申購標的：\n"
    for _, row in new_items.iterrows():
        msg += f"{row['股票代號 名稱']} | 承銷價 {row['承銷價']} | 報酬率 {row['報酬率(%)']}% | 獲利 {row['獲利']}\n"

    print(msg)
    send_line(msg)
    send_email("新增高報酬申購標的通知", msg)

if __name__ == "__main__":
    process()
