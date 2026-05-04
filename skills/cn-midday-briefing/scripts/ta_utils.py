#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
技术指标计算工具模块 — 从 cn-tech-analysis 提取复用
供 cn-midday-briefing 和 cn-tech-analysis 共用
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple


def calculate_ta_indicators(df: pd.DataFrame) -> Dict:
    """从日K线 DataFrame 计算全部技术指标"""
    if len(df) < 20:
        return None

    close = df['close'].astype(float)
    high = df['high'].astype(float)
    low = df['low'].astype(float)
    volume = df['volume'].astype(float)

    data = {
        'price': close.iloc[-1],
        'change_pct': ((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100) if len(close) > 1 else 0,
        'ma5': close.rolling(5).mean().iloc[-1],
        'ma10': close.rolling(10).mean().iloc[-1],
        'ma20': close.rolling(20).mean().iloc[-1],
        'ma60': close.rolling(60).mean().iloc[-1] if len(close) >= 60 else close.rolling(20).mean().iloc[-1],
        'high60': high.rolling(60).max().iloc[-1] if len(high) >= 60 else high.max(),
        'low60': low.rolling(60).min().iloc[-1] if len(low) >= 60 else low.min(),
    }

    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_dif = ema12 - ema26
    macd_dea = macd_dif.ewm(span=9, adjust=False).mean()
    macd_hist = 2 * (macd_dif - macd_dea)
    data['macd_dif'] = macd_dif.iloc[-1]
    data['macd_dea'] = macd_dea.iloc[-1]
    data['macd_hist'] = macd_hist.iloc[-1]

    # RSI
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    data['rsi14'] = (100 - (100 / (1 + rs))).iloc[-1]

    # KD
    low_9 = low.rolling(9).min()
    high_9 = high.rolling(9).max()
    rsv = (close - low_9) / (high_9 - low_9) * 100
    k = rsv.ewm(com=2, adjust=False).mean()
    d = k.ewm(com=2, adjust=False).mean()
    data['kd_k'] = k.iloc[-1]
    data['kd_d'] = d.iloc[-1]

    # 布林带
    ma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    data['boll_upper'] = (ma20 + 2 * std20).iloc[-1]
    data['boll_mid'] = ma20.iloc[-1]
    data['boll_lower'] = (ma20 - 2 * std20).iloc[-1]

    # ADX/DI
    period = 14
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0)
    minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0)

    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = pd.Series(tr).rolling(period).mean()

    plus_di = pd.Series(plus_dm).rolling(period).mean() / atr * 100
    minus_di = pd.Series(minus_dm).rolling(period).mean() / atr * 100
    dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100
    adx = dx.rolling(period).mean()

    data['adx'] = adx.iloc[-1]
    data['di_plus'] = plus_di.iloc[-1]
    data['di_minus'] = minus_di.iloc[-1]
    data['atr'] = atr.iloc[-1]

    # OBV
    obv = (np.sign(close.diff()) * volume).fillna(0).cumsum()
    data['obv_change5'] = ((obv.iloc[-1] - obv.iloc[-5]) / obv.iloc[-5] * 100) if len(obv) > 5 else 0

    return data


def calculate_score(data: Dict, morning_momentum: Optional[Dict] = None) -> Tuple[int, str, float, List[str]]:
    """计算综合评分和置信度"""
    score = 50
    signals = []

    has_price = data.get('price', 0) > 0
    if not has_price:
        return 1, '数据不足', 20, ['❌ 数据获取失败']

    # 均线
    if data['price'] > data['ma5'] > 0:
        score += 5
        signals.append('✅ 站上 MA5')
    else:
        score -= 5
        signals.append('❌ 跌破 MA5')

    if data['price'] > data['ma10'] > 0:
        score += 5
        signals.append('✅ 站上 MA10')
    else:
        score -= 5

    if data['price'] > data['ma20'] > 0:
        score += 5
        signals.append('✅ 站上 MA20')
    else:
        score -= 5

    # MACD
    if data['macd_hist'] > 0:
        score += 10
        signals.append('✅ MACD 多头')
    else:
        score -= 10
        signals.append('❌ MACD 空头')
    if data['macd_dif'] > data['macd_dea']:
        score += 5
        signals.append('✅ MACD 金叉')
    else:
        score -= 5

    # RSI
    if 50 <= data['rsi14'] <= 70:
        score += 5
        signals.append('✅ RSI 中性偏多')
    elif data['rsi14'] > 70:
        score -= 5
        signals.append('❌ RSI 超买')
    elif data['rsi14'] < 30:
        score += 10
        signals.append('✅ RSI 超卖')

    # KD
    if data['kd_k'] > data['kd_d']:
        score += 8
        signals.append('✅ KD 金叉')
    else:
        score -= 8
        signals.append('❌ KD 死叉')

    # ADX
    if data.get('adx', 0) > 0:
        if data['adx'] < 25:
            signals.append('⚠️ 震荡市 (ADX<25)')
            score = int(score * 0.9)
        else:
            signals.append('✅ 趋势市 (ADX>25)')

    # === 上午动量修正（可选） ===
    if morning_momentum is not None:
        chg_pct = morning_momentum.get('chg_pct', 0)
        vol_ratio = morning_momentum.get('vol_ratio', 1.0)

        # 急涨急跌修正（优先判断，振幅>2%）
        if chg_pct > 2:
            score += 10
            signals.append('⚡ 上午振幅较大')
        elif chg_pct < -2:
            score -= 10
            signals.append('⚡ 上午振幅较大')

        # 放量上涨
        if chg_pct > 0.5 and vol_ratio > 1.3:
            score += 15
            signals.append('🔥 上午放量上涨')
        # 温和放量上涨
        elif chg_pct > 0 and vol_ratio > 1.1:
            score += 8
            signals.append('📈 上午温和放量')

        # 放量下跌
        if chg_pct < -1.0 and vol_ratio > 1.3:
            score -= 15
            signals.append('⚠️ 上午放量下跌')

        # 缩量上涨
        if chg_pct > 0.5 and vol_ratio < 0.8:
            score -= 5
            signals.append('⚠️ 缩量上涨力度存疑')

    score = max(0, min(100, score))

    if score >= 85:
        rating, conf = '强烈看多', 85 + (score - 85) * 0.4
    elif score >= 70:
        rating, conf = '偏多', 70 + (score - 70) * 0.6
    elif score >= 55:
        rating, conf = '中性', 50 + (score - 55)
    elif score >= 40:
        rating, conf = '偏空', 35 + (score - 40) * 0.6
    else:
        rating, conf = '强烈看空', 15 + score * 0.5

    return score, rating, conf, signals


def get_top_signals(signals: List[str], max_count: int = 5) -> List[str]:
    """提取最重要的信号（精简版，用于午间快报）"""
    # 优先保留非 ⚠️ 的信号，但最多 max_count 条
    important = [s for s in signals if not s.startswith('⚠️')]
    warnings = [s for s in signals if s.startswith('⚠️')]
    result = important[:max_count]
    if len(result) < max_count and warnings:
        result.extend(warnings[:max_count - len(result)])
    return result
