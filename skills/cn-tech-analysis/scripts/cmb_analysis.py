#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
招商银行 (600036) 近 14 天技术面指标分析
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime

# 获取 60 天数据以计算完整指标
df = ak.stock_zh_a_daily(symbol='sh600036', start_date='20260101', end_date='20260313')

# 计算技术指标
close = df['close'].astype(float)
high = df['high'].astype(float)
low = df['low'].astype(float)
volume = df['volume'].astype(float)

# MA
df['MA5'] = close.rolling(5).mean()
df['MA10'] = close.rolling(10).mean()
df['MA20'] = close.rolling(20).mean()

# MACD
ema12 = close.ewm(span=12).mean()
ema26 = close.ewm(span=26).mean()
df['MACD_DIF'] = ema12 - ema26
df['MACD_DEA'] = df['MACD_DIF'].ewm(span=9).mean()
df['MACD_柱'] = 2 * (df['MACD_DIF'] - df['MACD_DEA'])

# RSI (14 日)
delta = close.diff()
gain = delta.where(delta > 0, 0).rolling(14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
rs = gain / loss
df['RSI'] = 100 - (100 / (1 + rs))

# KD (9 日)
low9 = low.rolling(9).min()
high9 = high.rolling(9).max()
rsv = 100 * (close - low9) / (high9 - low9)
df['K'] = rsv.ewm(com=2).mean()
df['D'] = df['K'].ewm(com=2).mean()

# 布林带 (20 日)
ma20 = close.rolling(20).mean()
std20 = close.rolling(20).std()
df['BB_upper'] = ma20 + 2 * std20
df['BB_mid'] = ma20
df['BB_lower'] = ma20 - 2 * std20

# 成交量均线
df['VOL_MA5'] = volume.rolling(5).mean()
df['VOL_MA10'] = volume.rolling(10).mean()

# 取最近 14 天
recent = df.tail(14).copy()

# 计算变化
price_change = (recent['close'].iloc[-1] - recent['close'].iloc[0]) / recent['close'].iloc[0] * 100

print('=' * 80)
print('                    招商银行 (600036) 近 14 天技术面指标分析')
print('=' * 80)
print(f'分析时间：{datetime.now().strftime("%Y-%m-%d %H:%M")} | 数据区间：{recent["date"].iloc[0]} 至 {recent["date"].iloc[-1]}')
print(f'14 天涨跌幅：{price_change:+.2f}%')
print('')

print('【一、价格与均线系统】')
print('-' * 80)
print(f'当前价格：{recent["close"].iloc[-1]:.2f} 元')
print(f'均线位置：MA5={recent["MA5"].iloc[-1]:.2f} | MA10={recent["MA10"].iloc[-1]:.2f} | MA20={recent["MA20"].iloc[-1]:.2f}')
print(f'均线排列：{"多头" if recent["MA5"].iloc[-1] > recent["MA10"].iloc[-1] > recent["MA20"].iloc[-1] else "空头/混乱"}')
print('')
print('日期        收盘价    MA5     MA10    MA20    位置关系')
for idx, row in recent.iterrows():
    pos = '站上' if row['close'] > row['MA20'] else '跌破'
    print(f'{row["date"]}  {row["close"]:6.2f}  {row["MA5"]:6.2f}  {row["MA10"]:6.2f}  {row["MA20"]:6.2f}  {pos}')
print('')

print('【二、MACD 指标】')
print('-' * 80)
print(f'当前 DIF: {recent["MACD_DIF"].iloc[-1]:.4f} | DEA: {recent["MACD_DEA"].iloc[-1]:.4f} | 柱：{recent["MACD_柱"].iloc[-1]:.4f}')
print(f'信号状态：{"金叉多头" if recent["MACD_DIF"].iloc[-1] > recent["MACD_DEA"].iloc[-1] else "死叉空头"}')
print('')
print('日期        DIF       DEA       柱状图    信号')
for idx, row in recent.iterrows():
    signal = '金叉' if row['MACD_DIF'] > row['MACD_DEA'] else '死叉'
    print(f'{row["date"]}  {row["MACD_DIF"]:8.4f}  {row["MACD_DEA"]:8.4f}  {row["MACD_柱"]:8.4f}  {signal}')
print('')

print('【三、RSI 与 KD 指标】')
print('-' * 80)
print(f'当前 RSI(14): {recent["RSI"].iloc[-1]:.2f} | K: {recent["K"].iloc[-1]:.2f} | D: {recent["D"].iloc[-1]:.2f}')
rsi_state = '超买' if recent['RSI'].iloc[-1] > 70 else ('超卖' if recent['RSI'].iloc[-1] < 30 else '中性')
kd_state = '金叉' if recent['K'].iloc[-1] > recent['D'].iloc[-1] else '死叉'
print(f'RSI 状态：{rsi_state} | KD 状态：{kd_state}')
print('')
print('日期        RSI       K         D         信号')
for idx, row in recent.iterrows():
    rsi_sig = '超买' if row['RSI'] > 70 else ('超卖' if row['RSI'] < 30 else '中性')
    kd_sig = '金叉' if row['K'] > row['D'] else '死叉'
    print(f'{row["date"]}  {row["RSI"]:7.2f}  {row["K"]:7.2f}  {row["D"]:7.2f}  RSI:{rsi_sig} KD:{kd_sig}')
print('')

print('【四、布林带】')
print('-' * 80)
print(f'当前：上轨={recent["BB_upper"].iloc[-1]:.2f} | 中轨={recent["BB_mid"].iloc[-1]:.2f} | 下轨={recent["BB_lower"].iloc[-1]:.2f}')
print(f'价格位置：{"接近上轨" if recent["close"].iloc[-1] > recent["BB_upper"].iloc[-1] * 0.98 else ("接近下轨" if recent["close"].iloc[-1] < recent["BB_lower"].iloc[-1] * 1.02 else "中轨附近")}')
print('')
print('日期        上轨      中轨      下轨      收盘价    位置')
for idx, row in recent.iterrows():
    if row['close'] > row['BB_upper'] * 0.98:
        pos = '上轨压力'
    elif row['close'] < row['BB_lower'] * 1.02:
        pos = '下轨支撑'
    else:
        pos = '通道内'
    print(f'{row["date"]}  {row["BB_upper"]:6.2f}  {row["BB_mid"]:6.2f}  {row["BB_lower"]:6.2f}  {row["close"]:6.2f}  {pos}')
print('')

print('【五、成交量分析】')
print('-' * 80)
print(f'当日成交量：{recent["volume"].iloc[-1]:.0f}')
print(f'均量线：VOL_MA5={recent["VOL_MA5"].iloc[-1]:.0f} | VOL_MA10={recent["VOL_MA10"].iloc[-1]:.0f}')
vol_ratio = recent['volume'].iloc[-1] / recent['VOL_MA5'].iloc[-1]
print(f'量比：{vol_ratio:.2f} ({">" if vol_ratio > 1 else "<"}5 日均量)')
print('')

print('【六、综合技术判断】')
print('-' * 80)

# 综合评分
score = 50
signals = []

# 均线
if recent['MA5'].iloc[-1] > recent['MA10'].iloc[-1] > recent['MA20'].iloc[-1]:
    score += 15
    signals.append('[OK] 均线多头排列')
else:
    signals.append('[WARN] 均线排列一般')

# MACD
if recent['MACD_DIF'].iloc[-1] > recent['MACD_DEA'].iloc[-1]:
    score += 15
    signals.append('[OK] MACD 金叉多头')
else:
    signals.append('[ERR] MACD 死叉空头')

# RSI
if 40 < recent['RSI'].iloc[-1] < 60:
    score += 10
    signals.append('[OK] RSI 中性健康')
elif recent['RSI'].iloc[-1] > 70:
    signals.append('[WARN] RSI 超买警惕回调')
elif recent['RSI'].iloc[-1] < 30:
    signals.append('[WARN] RSI 超卖可能反弹')

# KD
if recent['K'].iloc[-1] > recent['D'].iloc[-1]:
    score += 10
    signals.append('[OK] KD 金叉')
else:
    signals.append('[ERR] KD 死叉')

# 布林带
if recent['close'].iloc[-1] > recent['BB_mid'].iloc[-1]:
    score += 10
    signals.append('[OK] 价格站上中轨')
else:
    signals.append('[WARN] 价格跌破中轨')

print(f'综合评分：{score}/100')
print('')
for s in signals:
    print(f'  {s}')
print('')

print('【七、操作建议】')
print('-' * 80)
if score >= 70:
    print('建议：偏多操作，可持股或逢低加仓')
    print('支撑位：{:.2f} / 压力位：{:.2f}'.format(recent['MA10'].iloc[-1], recent['BB_upper'].iloc[-1]))
elif score >= 50:
    print('建议：震荡市，高抛低吸，不宜追涨杀跌')
    print('支撑位：{:.2f} / 压力位：{:.2f}'.format(recent['BB_lower'].iloc[-1], recent['BB_upper'].iloc[-1]))
else:
    print('建议：偏空操作，谨慎持仓，注意风险')
    print('支撑位：{:.2f} / 压力位：{:.2f}'.format(recent['BB_lower'].iloc[-1], recent['MA10'].iloc[-1]))
print('')
print('=' * 80)
print('免责声明：以上分析仅供参考，不构成投资建议。投资有风险，入市需谨慎。')
print('=' * 80)
