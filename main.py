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

    # 用單行字串表示股票資訊
    msg_items = []
    for _, row in new_items.iterrows():
        msg_items.append(f"{row['股票代號 名稱']}(投報率:{row['報酬率(%)']}% 獲利:{row['獲利']}元)")

    msg = "📢 新增符合條件申購標的：\n" + "、".join(msg_items)

    print(msg)
    send_line(msg)
    send_email("新增高報酬申購標的通知", msg)
