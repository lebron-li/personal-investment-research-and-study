#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
159825 ETF 近 14 天技术面指标分析
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime

# 获取 ETF 历史数据
df = ak.fund_etf_hist_em(symbol='159825', period='daily', start_date='20260101', end_date='20260313', adjust='')

# 重命名列
df.columns = ['date', 'open', 'close', 'high', 'low', 'volume', 'amount', 'turnover', 'change_pct', 'change', 'amplitude']

# 转换数据类型
for col in ['open', 'close', 'high', 'low', 'volume', 'amount', 'turnover', 'change_pct', 'change', 'amplitude']:
    df[col] = pd.to_numeric(df[col], errors='coerce')

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
print('                    159825 ETF 近 14 天技术面指标分析')
print('=' * 80)
print(f'分析时间：{datetime.now().strftime("%Y-%m-%d %H:%M")} | 数据区间：{recent["date"].iloc[0]} 至 {recent["date"].iloc[-1]}')
print(f'14 天涨跌幅：{price_change:+.2f}%')
print('')

print('【一、价格与均线系统】')
print('-' * 80)
print(f'当前价格：{recent["close"].iloc[-1]:.3f} 元')
print(f'均线位置：MA5={recent["MA5"].iloc[-1]:.3f} | MA10={recent["MA10"].iloc[-1]:.3f} | MA20={recent["MA20"].iloc[-1]:.3f}')
ma_signal = '多头' if recent['MA5'].iloc[-1] > recent['MA10'].iloc[-1] > recent['MA20'].iloc[-1] else '空头/混乱'
print(f'均线排列：{ma_signal}')
print('')

print('【二、MACD 指标】')
print('-' * 80)
print(f'当前 DIF: {recent["MACD_DIF"].iloc[-1]:.4f} | DEA: {recent["MACD_DEA"].iloc[-1]:.4f} | 柱：{recent["MACD_柱"].iloc[-1]:.4f}')
macd_signal = '金叉多头' if recent['MACD_DIF'].iloc[-1] > recent['MACD_DEA'].iloc[-1] else '死叉空头'
print(f'信号状态：{macd_signal}')
print('')

print('【三、RSI 与 KD 指标】')
print('-' * 80)
print(f'当前 RSI(14): {recent["RSI"].iloc[-1]:.2f} | K: {recent["K"].iloc[-1]:.2f} | D: {recent["D"].iloc[-1]:.2f}')
rsi_state = '超买' if recent['RSI'].iloc[-1] > 70 else ('超卖' if recent['RSI'].iloc[-1] < 30 else '中性')
kd_state = '金叉' if recent['K'].iloc[-1] > recent['D'].iloc[-1] else '死叉'
print(f'RSI 状态：{rsi_state} | KD 状态：{kd_state}')
print('')

print('【四、布林带】')
print('-' * 80)
print(f'当前：上轨={recent["BB_upper"].iloc[-1]:.3f} | 中轨={recent["BB_mid"].iloc[-1]:.3f} | 下轨={recent["BB_lower"].iloc[-1]:.3f}')
price_pos = recent['close'].iloc[-1]
if price_pos > recent['BB_upper'].iloc[-1] * 0.98:
    pos_desc = '接近上轨 (压力)'
elif price_pos < recent['BB_lower'].iloc[-1] * 1.02:
    pos_desc = '接近下轨 (支撑)'
else:
    pos_desc = '通道内'
print(f'价格位置：{pos_desc}')
print('')

print('【五、成交量分析】')
print('-' * 80)
print(f'当日成交量：{recent["volume"].iloc[-1]:.0f}')
print(f'均量线：VOL_MA5={recent["VOL_MA5"].iloc[-1]:.0f} | VOL_MA10={recent["VOL_MA10"].iloc[-1]:.0f}')
vol_ratio = recent['volume'].iloc[-1] / recent['VOL_MA5'].iloc[-1]
vol_desc = '>' if vol_ratio > 1 else '<'
print(f'量比：{vol_ratio:.2f} ({vol_desc}5 日均量)')
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
else:
    signals.append('[OK] RSI 健康')

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
    print(f'支撑位：{recent["MA10"].iloc[-1]:.3f} / 压力位：{recent["BB_upper"].iloc[-1]:.3f}')
elif score >= 50:
    print('建议：震荡市，高抛低吸，不宜追涨杀跌')
    print(f'支撑位：{recent["BB_lower"].iloc[-1]:.3f} / 压力位：{recent["BB_upper"].iloc[-1]:.3f}')
else:
    print('建议：偏空操作，谨慎持仓，注意风险')
    print(f'支撑位：{recent["BB_lower"].iloc[-1]:.3f} / 压力位：{recent["MA10"].iloc[-1]:.3f}')
print('')

print('【八、14 天价格明细】')
print('-' * 80)
print('日期        收盘价    涨跌幅    成交量')
for idx, row in recent.iterrows():
    print(f'{row["date"]}  {row["close"]:7.3f}  {row["change_pct"]:6.2f}%  {row["volume"]:10.0f}')
print('')

print('=' * 80)
print('免责声明：以上分析仅供参考，不构成投资建议。投资有风险，入市需谨慎。')
print('=' * 80)
