#!/usr/bin/env python3
"""
unified_backtest.py: Unified polling backtester for UT-Bot with Alpaca REST.

- Fetches 1m, 5m, and 15m bars.
- Computes UT-ATR trailing stops, EMA200, RSI14.
- Detects 15m entry signals (CALL/PUT) via stop crossover.
- Exits via 5m RSI or hybrid logic, with 1m stop-loss fallback.
- Calculates P&L using REF_DELTA/REF_PROFIT_PCT.
"""
import os
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import pytz
from dotenv import load_dotenv

import pandas as pd
import ta
import alpaca_trade_api as tradeapi

# —————— CONFIG ——————
REF_DELTA        = 0.4
REF_PROFIT_PCT   = 25.0
RSI_EXIT_THRESH  = 6.0
STOP_LOSS_PCT    = 0.005
BANKROLL_START   = 10000
CONTRACT_SIZE    = 1000

ATR_PERIOD       = 10
EMA_PERIOD       = 200
RSI_PERIOD       = 14
TIME_SWITCH      = timedelta(minutes=45)

# —————— INIT & SIGS ——————
def ut_bot_init(df, atr_period, ema_period, rsi_period):
    src = df['Close']
    df['ATR']    = ta.volatility.average_true_range(df['High'], df['Low'], src, window=atr_period)
    df['nLoss']  = df['ATR']
    # trailing stops
    stops = pd.Series(index=df.index, dtype=float)
    for i in range(len(df)):
        prev_stop = stops.iat[i-1] if i>0 else src.iat[0]
        if src.iat[i] > prev_stop and src.shift(1).iat[i] > prev_stop:
            stops.iat[i] = max(prev_stop, src.iat[i] - df['nLoss'].iat[i])
        elif src.iat[i] < prev_stop and src.shift(1).iat[i] < prev_stop:
            stops.iat[i] = min(prev_stop, src.iat[i] + df['nLoss'].iat[i])
        else:
            stops.iat[i] = src.iat[i] - df['nLoss'].iat[i] if src.iat[i]>prev_stop else src.iat[i] + df['nLoss'].iat[i]
    df['UT_ATRTrailingStop'] = stops
    df['EMA200'] = src.ewm(span=ema_period, adjust=False).mean()
    df['RSI']    = ta.momentum.rsi(src, window=rsi_period)
    return df

# detect 15m entries
def detect_15m_entries(df15, window_start, window_end):
    signals = []
    for i in range(1, len(df15)):
        prev_close = df15['Close'].iat[i-1]
        this_close = df15['Close'].iat[i]
        prev_stop  = df15['UT_ATRTrailingStop'].iat[i-1]
        this_stop  = df15['UT_ATRTrailingStop'].iat[i]
        if window_start <= df15.index[i] <= window_end:
            if (this_close>this_stop and prev_close<=prev_stop) or (this_close<this_stop and prev_close>=prev_stop):
                signals.append({
                    'timestamp': df15.index[i],
                    'signal': 'BUY' if this_close>this_stop else 'SELL',
                    'open': df15['Open'].iat[i],
                    'rsi': df15['RSI'].iat[i]
                })
    return signals

# —————— BACKTEST ——————
if __name__=='__main__':
    load_dotenv()
    api = tradeapi.REST(os.getenv('ALPACA_API_KEY'), os.getenv('ALPACA_API_SECRET'),
                       os.getenv('ALPACA_BASE_URL','https://paper-api.alpaca.markets'), api_version='v2')
    symbol = 'SPY'
    tz_ny  = pytz.timezone('America/New_York')
    end_dt = datetime(2025,6,27,23,59,59, tzinfo=pytz.utc)
    start_dt = end_dt - relativedelta(days=12)
    start_iso = start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    end_iso   = end_dt.strftime('%Y-%m-%dT%H:%M:%SZ')

    # fetch & init
    def fetch_df(granularity):
        df = api.get_bars(symbol, granularity, start=start_iso, end=end_iso).df
        df.index = pd.to_datetime(df.index, utc=True).tz_convert(tz_ny)
        df = df.rename(columns=str.capitalize)
        return ut_bot_init(df, ATR_PERIOD, EMA_PERIOD, RSI_PERIOD)

    df15 = fetch_df('15Min')
    df5  = fetch_df('5Min')
    df1  = fetch_df('1Min')

    # window filter
    window_start = tz_ny.localize(datetime(2025,5,26))
    window_end   = tz_ny.localize(datetime(2025,6,27,23,59,59))

    # 15m entries
    entries = detect_15m_entries(df15, window_start, window_end)

    bankroll, total_deltas, total_pct, total_dollars = BANKROLL_START, [], [], []

    for ev in entries:
        t15, typ = ev['timestamp'], ev['signal']
        tag = 'CALL' if typ=='BUY' else 'PUT'
        entry_prc = ev['open']
        entry_rsi = ev['rsi']
        print(f"[15m] ▶ ENTRY {tag:4s} @ {t15} | Price: {entry_prc:.2f}")

        # 5m exit
        prior5 = df5[df5.index<t15]
        prev_rsi = prior5['RSI'].iat[-1] if not prior5.empty else entry_rsi
        exit_time5 = exit_prc5 = None
        for idx5, row5 in df5[df5.index>t15].iterrows():
            if idx5>window_end: break
            age = idx5 - t15
            price5, stop5, curr_rsi = row5['Close'], row5['UT_ATRTrailingStop'], row5['RSI']
            if age<=TIME_SWITCH:
                cond = (prev_rsi-curr_rsi)>=RSI_EXIT_THRESH if typ=='BUY' else (curr_rsi-prev_rsi)>=RSI_EXIT_THRESH
                label='RSI'
            else:
                tb = price5<=stop5 if typ=='BUY' else price5>=stop5
                rb = (prev_rsi-curr_rsi)>=RSI_EXIT_THRESH if typ=='BUY' else (curr_rsi-prev_rsi)>=RSI_EXIT_THRESH
                cond, label = (tb and rb), 'HYBRID'
            print(f"[ 5m] {idx5} | Age:{int(age.total_seconds()/60)}m  Price:{price5:.2f} Stop:{stop5:.2f} RSIΔ:{(prev_rsi-curr_rsi) if typ=='BUY' else (curr_rsi-prev_rsi):.2f} → Exit?{cond} ({label})")
            if cond:
                exit_time5, exit_prc5 = idx5, price5
                break
            prev_rsi = curr_rsi

        # 1m fallback
        exit_time1 = exit_prc1 = None
        if exit_time5 is None:
            for idx1, row1 in df1[df1.index>t15].iterrows():
                if idx1>window_end: break
                p1=row1['Close']
                sl = p1*(1-STOP_LOSS_PCT) if typ=='BUY' else p1*(1+STOP_LOSS_PCT)
                cond = p1<=sl if typ=='BUY' else p1>=sl
                if cond:
                    exit_time1, exit_prc1 = idx1, p1
                    print(f"[EXIT-STOP] @ {idx1} | Price:{p1:.2f}")
                    break

        # choose exit
        if exit_time5 and (not exit_time1 or exit_time5<=exit_time1):
            exit_idx, exit_prc, exit_type = exit_time5, exit_prc5, label
        elif exit_time1:
            exit_idx, exit_prc, exit_type = exit_time1, exit_prc1, 'STOP_LOSS'
        else:
            exit_idx, exit_prc, exit_type = None, None, None

        # P&L
        if exit_idx:
            delta = (exit_prc-entry_prc) if typ=='BUY' else (entry_prc-exit_prc)
            pct   = delta/REF_DELTA*REF_PROFIT_PCT
            dollars=CONTRACT_SIZE*pct/100
            bankroll+=dollars
            total_deltas.append(delta)
            total_pct.append(pct)
            total_dollars.append(dollars)
            print(f"[EXIT-{exit_type}] @ {exit_idx} | Price:{exit_prc:.2f} ▶ Δ:{delta:.2f} ({pct:.1f}%) ▶ ${dollars:.2f}\n")
        else:
            print("[EXIT] @ <none> ▶ Δ:0.00 (0.0%) ▶ $0.00\n")

    print("▶▶ Profit & Loss Summary:")
    print(f" Trades: {len(total_dollars)}   "
          f"Total Δ:{sum(total_deltas):.2f}   "
          f"Total %:{sum(total_pct):.1f}%   "
          f"Total $:{sum(total_dollars):.2f}   "
          f"Bankroll:${bankroll:.2f}")