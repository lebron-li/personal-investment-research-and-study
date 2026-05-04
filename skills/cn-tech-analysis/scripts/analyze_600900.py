#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import akshare as ak
import pandas as pd
import numpy as np

# 获取长江电力数据
df = ak.stock_zh_a_daily(symbol='sh600900', start_date='20251201', end_date='20260322')

print('=== 长江电力 (600900) 最新数据 ===')
print(f'数据长度：{len(df)} 行')
print(f'最新日期：{df.iloc[-1]["date"]}')
print(f'最新收盘价：{df.iloc[-1]["close"]:.2f} 元')
print(f'今日开盘：{df.iloc[-1]["open"]:.2f} 元')
print(f'今日最高：{df.iloc[-1]["high"]:.2f} 元')
print(f'今日最低：{df.iloc[-1]["low"]:.2f} 元')
print(f'成交量：{df.iloc[-1]["volume"]:,.0f} 手')
print(f'成交额：{df.iloc[-1]["amount"]/1e8:.2f} 亿元')

# 计算均线
close = df['close'].astype(float)
ma5 = close.rolling(5).mean().iloc[-1]
ma10 = close.rolling(10).mean().iloc[-1]
ma20 = close.rolling(20).mean().iloc[-1]
ma60 = close.rolling(60).mean().iloc[-1]

print(f'\n=== 均线 ===')
print(f'MA5: {ma5:.2f}')
print(f'MA10: {ma10:.2f}')
print(f'MA20: {ma20:.2f}')
print(f'MA60: {ma60:.2f}')

# 计算 MACD
exp1 = close.ewm(span=12, adjust=False).mean()
exp2 = close.ewm(span=26, adjust=False).mean()
dif = exp1 - exp2
dea = dif.ewm(span=9, adjust=False).mean()
macd_bar = (dif - dea) * 2

print(f'\n=== MACD ===')
print(f'DIF: {dif.iloc[-1]:.4f}')
print(f'DEA: {dea.iloc[-1]:.4f}')
print(f'MACD 柱：{macd_bar.iloc[-1]:.4f}')

# 计算 RSI
delta = close.diff()
gain = (delta.where(delta > 0, 0)).rolling(14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
rs = gain / loss
rsi = 100 - (100 / (1 + rs))

print(f'\n=== RSI ===')
print(f'RSI(14): {rsi.iloc[-1]:.1f}')

# 计算 KD
low14 = df['low'].astype(float).rolling(14).min()
high14 = df['high'].astype(float).rolling(14).max()
rsv = (close - low14) / (high14 - low14) * 100
k = rsv.ewm(span=3, adjust=False).mean()
d = k.ewm(span=3, adjust=False).mean()

print(f'\n=== KD ===')
print(f'K: {k.iloc[-1]:.1f}')
print(f'D: {d.iloc[-1]:.1f}')

# 计算布林带
ma20_series = close.rolling(20).mean()
std20 = close.rolling(20).std()
upper = ma20_series + 2 * std20
lower = ma20_series - 2 * std20

print(f'\n=== 布林带 ===')
print(f'上轨：{upper.iloc[-1]:.2f}')
print(f'中轨：{ma20_series.iloc[-1]:.2f}')
print(f'下轨：{lower.iloc[-1]:.2f}')

# 60 日高低点
high60 = df['high'].astype(float).rolling(60).max().iloc[-1]
low60 = df['low'].astype(float).rolling(60).min().iloc[-1]

print(f'\n=== 60 日区间 ===')
print(f'60 日最高：{high60:.2f}')
print(f'60 日最低：{low60:.2f}')

# 涨跌幅
change_pct = ((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100)
print(f'\n=== 今日涨跌 ===')
print(f'涨跌幅：{change_pct:.2f}%')

# 均线位置判断
price = close.iloc[-1]
print(f'\n=== 均线位置 ===')
print(f'站上 MA5: {"是" if price > ma5 else "否"}')
print(f'站上 MA10: {"是" if price > ma10 else "否"}')
print(f'站上 MA20: {"是" if price > ma20 else "否"}')
print(f'站上 MA60: {"是" if price > ma60 else "否"}')

# MACD 金叉死叉判断
print(f'\n=== MACD 信号 ===')
print(f'MACD 多头：{"是" if dif.iloc[-1] > dea.iloc[-1] else "否"}')
if dif.iloc[-1] > dea.iloc[-1] and dif.iloc[-2] <= dea.iloc[-2]:
    print('MACD 金叉：是 (今日发生)')
elif dif.iloc[-1] < dea.iloc[-1] and dif.iloc[-2] >= dea.iloc[-2]:
    print('MACD 死叉：是 (今日发生)')
else:
    print('MACD 金叉/死叉：无')

# KD 金叉死叉判断
print(f'\n=== KD 信号 ===')
print(f'KD 金叉：{"是" if k.iloc[-1] > d.iloc[-1] and k.iloc[-2] <= d.iloc[-2] else "否"}')
print(f'KD 死叉：{"是" if k.iloc[-1] < d.iloc[-1] and k.iloc[-2] >= d.iloc[-2] else "否"}')

# RSI 超买超卖
print(f'\n=== RSI 状态 ===')
rsi_val = rsi.iloc[-1]
if rsi_val > 70:
    print('RSI 超买 (>70)')
elif rsi_val < 30:
    print('RSI 超卖 (<30)')
else:
    print('RSI 中性 (30-70)')
