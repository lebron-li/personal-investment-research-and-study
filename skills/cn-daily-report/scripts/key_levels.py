# -*- coding: utf-8 -*-
"""
关键位置分析模块
- 支撑位/阻力位识别
- 前高/前低扫描
- 缺口检测
- 突破/跌破预警
"""

import pandas as pd
import numpy as np
from data_fetcher import fetch_stock_kline


def find_support_resistance(code, lookback_days=60):
    """
    识别支撑位和阻力位
    
    方法：
    - 支撑位：近期低点、均线、前期平台
    - 阻力位：近期高点、均线、前期平台
    
    参数：
        code: 股票代码
        lookback_days: 回看天数
    
    返回：
        dict: 支撑位和阻力位列表
    """
    df = fetch_stock_kline(code, period='day', count=lookback_days)
    
    if df.empty:
        return {'supports': [], 'resistances': []}
    
    current_price = df.iloc[-1]['close']
    
    # 方法 1：寻找局部高低点
    supports = []
    resistances = []
    
    # 寻找局部低点（支撑）
    for i in range(5, len(df) - 5):
        window = df['low'].iloc[i-5:i+6]
        if df['low'].iloc[i] == window.min():
            supports.append(df['low'].iloc[i])
    
    # 寻找局部高点（阻力）
    for i in range(5, len(df) - 5):
        window = df['high'].iloc[i-5:i+6]
        if df['high'].iloc[i] == window.max():
            resistances.append(df['high'].iloc[i])
    
    # 方法 2：添加均线作为动态支撑/阻力
    df['ma20'] = df['close'].rolling(20).mean()
    df['ma60'] = df['close'].rolling(60).mean()
    
    if len(df) >= 60:
        ma20 = df.iloc[-1]['ma20']
        ma60 = df.iloc[-1]['ma60']
        
        if ma20 < current_price:
            supports.append(ma20)
        else:
            resistances.append(ma20)
        
        if ma60 < current_price:
            supports.append(ma60)
        else:
            resistances.append(ma60)
    
    # 去重并排序
    supports = sorted(list(set([round(s, 2) for s in supports])))
    resistances = sorted(list(set([round(r, 2) for r in resistances])))
    
    # 筛选：支撑位 < 当前价，阻力位 > 当前价
    supports = [s for s in supports if s < current_price]
    resistances = [r for r in resistances if r > current_price]
    
    # 取最近的 3 个
    supports = supports[-3:] if len(supports) > 3 else supports
    resistances = resistances[:3] if len(resistances) > 3 else resistances
    
    return {
        'supports': supports,
        'resistances': resistances,
        'current_price': current_price
    }


def find_recent_high_low(code, lookback_days=60):
    """
    寻找近期最高价和最低价
    
    参数：
        code: 股票代码
        lookback_days: 回看天数
    
    返回：
        dict: 前高和前低
    """
    df = fetch_stock_kline(code, period='day', count=lookback_days)
    
    if df.empty:
        return {'high': None, 'low': None, 'high_date': None, 'low_date': None}
    
    # 排除今日（因为今日还没结束）
    df_past = df.iloc[:-1]
    
    if df_past.empty:
        return {'high': None, 'low': None, 'high_date': None, 'low_date': None}
    
    high_idx = df_past['high'].idxmax()
    low_idx = df_past['low'].idxmin()
    
    return {
        'high': df_past.loc[high_idx, 'high'],
        'low': df_past.loc[low_idx, 'low'],
        'high_date': df_past.loc[high_idx, 'date'].strftime('%Y-%m-%d'),
        'low_date': df_past.loc[low_idx, 'low'].strftime('%Y-%m-%d')
    }


def find_gaps(code, lookback_days=60):
    """
    检测缺口（跳空高开/低开）
    
    缺口定义：
    - 向上缺口：今日最低价 > 昨日最高价
    - 向下缺口：今日最高价 < 昨日最低价
    
    参数：
        code: 股票代码
        lookback_days: 回看天数
    
    返回：
        list: 缺口列表
    """
    df = fetch_stock_kline(code, period='day', count=lookback_days)
    
    if df.empty or len(df) < 2:
        return []
    
    gaps = []
    
    for i in range(1, len(df)):
        prev = df.iloc[i-1]
        curr = df.iloc[i]
        
        # 向上缺口
        if curr['low'] > prev['high']:
            gap_size = (curr['low'] - prev['high']) / prev['close'] * 100
            gaps.append({
                'type': '向上缺口',
                'date': curr['date'].strftime('%Y-%m-%d'),
                'top': curr['low'],
                'bottom': prev['high'],
                'size': gap_size,
                'status': '未回补' if curr['close'] > prev['high'] else '已回补'
            })
        
        # 向下缺口
        elif curr['high'] < prev['low']:
            gap_size = (prev['low'] - curr['high']) / prev['close'] * 100
            gaps.append({
                'type': '向下缺口',
                'date': curr['date'].strftime('%Y-%m-%d'),
                'top': prev['low'],
                'bottom': curr['high'],
                'size': gap_size,
                'status': '未回补' if curr['close'] < prev['low'] else '已回补'
            })
    
    # 只返回未回补的缺口
    unfilled_gaps = [g for g in gaps if g['status'] == '未回补']
    
    return unfilled_gaps[-3:]  # 最近 3 个


def check_breakout(code, threshold=0.03):
    """
    检查是否突破关键位置
    
    参数：
        code: 股票代码
        threshold: 突破阈值（默认 3%）
    
    返回：
        dict: 突破状态
    """
    levels = find_support_resistance(code)
    high_low = find_recent_high_low(code)
    
    if not levels['supports'] and not levels['resistances']:
        return {'status': '无关键位置', 'details': []}
    
    current_price = levels['current_price']
    alerts = []
    
    # 检查阻力位突破
    for r in levels['resistances']:
        if current_price > r:
            breakout_pct = (current_price - r) / r * 100
            if breakout_pct > threshold * 100:
                alerts.append({
                    'type': '突破阻力',
                    'level': r,
                    'current': current_price,
                    'breakout_pct': breakout_pct
                })
    
    # 检查支撑位跌破
    for s in levels['supports']:
        if current_price < s:
            breakdown_pct = (s - current_price) / s * 100
            if breakdown_pct > threshold * 100:
                alerts.append({
                    'type': '跌破支撑',
                    'level': s,
                    'current': current_price,
                    'breakdown_pct': breakdown_pct
                })
    
    # 检查前高/前低突破
    if high_low['high']:
        if current_price > high_low['high']:
            alerts.append({
                'type': '突破前高',
                'level': high_low['high'],
                'high_date': high_low['high_date']
            })
    
    if high_low['low']:
        if current_price < high_low['low']:
            alerts.append({
                'type': '跌破前低',
                'level': high_low['low'],
                'low_date': high_low['low_date']
            })
    
    return {
        'status': '预警' if alerts else '正常',
        'alerts': alerts
    }


def get_key_levels_summary(code):
    """
    获取关键位置汇总
    
    参数：
        code: 股票代码
    
    返回：
        dict: 关键位置汇总
    """
    levels = find_support_resistance(code)
    high_low = find_recent_high_low(code)
    gaps = find_gaps(code)
    breakout = check_breakout(code)
    
    return {
        'code': code,
        'current_price': levels.get('current_price'),
        'supports': levels.get('supports', []),
        'resistances': levels.get('resistances', []),
        'recent_high': high_low.get('high'),
        'recent_low': high_low.get('low'),
        'gaps': gaps,
        'breakout_status': breakout.get('status'),
        'alerts': breakout.get('alerts', [])
    }


if __name__ == '__main__':
    # 测试
    print("测试关键位置分析 (600036):")
    summary = get_key_levels_summary('600036')
    
    print(f"  当前价：{summary['current_price']}")
    print(f"  支撑位：{summary['supports']}")
    print(f"  阻力位：{summary['resistances']}")
    print(f"  前高：{summary['recent_high']}")
    print(f"  前低：{summary['recent_low']}")
    print(f"  缺口：{len(summary['gaps'])}个")
    print(f"  突破状态：{summary['breakout_status']}")
    if summary['alerts']:
        print(f"  预警：{summary['alerts']}")
