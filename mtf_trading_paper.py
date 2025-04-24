import time
import os
import pandas as pd
import threading
from datetime import datetime, timedelta
from datetime import time as dtime
from kiteconnect import KiteConnect
import sys
sys.path.append("E:/")



import kiteSettings

# Authenticate with Kite Connect
api_key = kiteSettings.api_key
access_token = kiteSettings.access_token

EXCEL_FILE = "MTF_Trading.xlsx"
MAX_ACTIVE_TRADES = 5
MONITOR_INTERVAL = 10  # seconds
stocks = [
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK",
    "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BEL", "BHARTIARTL", "BPCL",
    "BRITANNIA", "CIPLA", "COALINDIA", "DRREDDY",
    "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK",
    "HDFCLIFE", "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK",
    "INDUSINDBK", "INFY", "ITC", "JSWSTEEL", "KOTAKBANK",
    "LT", "M&M", "MARUTI", "NESTLEIND", "NTPC",
    "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SBIN", "SHRIRAMFIN",
    "SUNPHARMA", "TATACONSUM", "TATAMOTORS", "TATASTEEL", "TECHM",
    "TITAN", "ULTRACEMCO", "WIPRO"
]

# ------------------------ INITIALIZE ------------------------- #
kite = KiteConnect(api_key=api_key)
kite.set_access_token(access_token)

if not os.path.exists(EXCEL_FILE):
    df = pd.DataFrame(columns=[
        "Date", "Time", "Stock Name", "Buy/Trigger Price", "Active",
        "Sell Price", "P/L", "Sell Date", "Sell Time"
    ])
    df.to_excel(EXCEL_FILE, index=False)

def read_excel():
    return pd.read_excel(EXCEL_FILE)

def write_excel(df):
    df.to_excel(EXCEL_FILE, index=False)

# ------------------------ STRATEGY --------------------------- #
def is_bullish_engulfing(prev, curr):
    return (
        prev['close'] < prev['open'] and
        curr['close'] > curr['open'] and
        curr['open'] < prev['close'] and
        curr['close'] > prev['open']
    )

# --------------------- MONITOR TRADES ------------------------ #
def monitor_trade(stock, buy_price):
    target = buy_price * 1.004
    stop = buy_price * 0.996

    while True:
        try:
            ltp = kite.ltp([f"NSE:{stock}"])[f"NSE:{stock}"]["last_price"]
            df = read_excel()
            index = df[(df["Stock Name"] == stock) & (df["Active"] == "Yes")].index
            if index.empty:
                return  # already marked closed
            index = index[0]

            if ltp >= target:
                df.at[index, "Active"] = "No"
                df.at[index, "Sell Price"] = ltp
                df.at[index, "P/L"] = "+0.4%"
            elif ltp <= stop:
                df.at[index, "Active"] = "No"
                df.at[index, "Sell Price"] = ltp
                df.at[index, "P/L"] = "-0.4%"
            else:
                time.sleep(MONITOR_INTERVAL)
                continue

            df.at[index, "Sell Date"] = datetime.now().strftime("%Y-%m-%d")
            df.at[index, "Sell Time"] = datetime.now().strftime("%H:%M:%S")
            write_excel(df)
            return

        except Exception as e:
            print(f"Monitor error for {stock}: {e}")
            time.sleep(MONITOR_INTERVAL)

# --------------------- CANDLE ANALYSIS ----------------------- #
def fetch_completed_candles(stock):
    try:
        token = kite.ltp([f"NSE:{stock}"])[f"NSE:{stock}"]["instrument_token"]
        from_time = datetime.now().replace(hour=9, minute=15, second=0, microsecond=0)
        to_time = datetime.now()
        candles = kite.historical_data(token, from_time, to_time, "30minute")

        if not candles:
            return pd.DataFrame()
        df = pd.DataFrame(candles)
        if 'date' not in df.columns:
            print(f"Invalid candle data for {stock}: missing 'date'")
            return pd.DataFrame()
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)

        # Drop the last incomplete candle if present
        now = datetime.now()
        df = df[df["date"] < now]

        return df.tail(2)
    except Exception as e:
        print(f"Fetch error for {stock}: {e}")
        return pd.DataFrame()

# ------------------------ MAIN LOOP -------------------------- #
def analyze():
    print("Waiting until 10:15 to start...")
    start_time = datetime.now().replace(hour=10, minute=15, second=0, microsecond=0)
    if datetime.now() < start_time:
        time.sleep((start_time - datetime.now()).total_seconds())

    # Resume monitoring previously active trades
    df = read_excel()
    active_trades = df[df["Active"] == "Yes"]
    for _, row in active_trades.iterrows():
        threading.Thread(
            target=monitor_trade,
            args=(row["Stock Name"], row["Buy/Trigger Price"])
        ).start()
    now_time = datetime.now().time()
    cutoff_time = dtime(15, 15, 0)
    while now_time < cutoff_time:
        
        print(f"\n--- Analyzing at {datetime.now().strftime('%H:%M:%S')} ---")
        df = read_excel()
        active_count = len(df[df["Active"] == "Yes"])

        for stock in stocks:
            if active_count >= MAX_ACTIVE_TRADES:
                print("Max active trades reached.")
                break

            candles = fetch_completed_candles(stock)
            if len(candles) < 2:
                print(f"Not enough candles for {stock}.")
                continue

            prev, curr = candles.iloc[-2], candles.iloc[-1]
            if is_bullish_engulfing(prev, curr):
                buy_price = curr["close"]
                print(f"BUY SIGNAL: {stock} at {buy_price}")
                new_entry = {
                    "Date": datetime.now().strftime("%Y-%m-%d"),
                    "Time": datetime.now().strftime("%H:%M:%S"),
                    "Stock Name": stock,
                    "Buy/Trigger Price": buy_price,
                    "Active": "Yes",
                    "Sell Price": None,
                    "P/L": None,
                    "Sell Date": None,
                    "Sell Time": None
                }
                df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
                write_excel(df)
                threading.Thread(target=monitor_trade, args=(stock, buy_price)).start()
                active_count += 1

        # wait for the next 30-minute boundary (xx:15 or xx:45)
        now = datetime.now()
        now_time = datetime.now().time()
        next_min = 15 if now.minute < 15 else 45 if now.minute < 45 else 75
        next_time = now.replace(minute=next_min % 60, second=5, microsecond=0)
        if next_min >= 60:
            next_time += timedelta(hours=1)
        time.sleep((next_time - now).total_seconds())

if __name__ == "__main__":
    analyze()