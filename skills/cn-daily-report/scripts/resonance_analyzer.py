# -*- coding: utf-8 -*-
"""
共振分析模块
- 板块联动分析
- 大盘共振分析
- 多周期共振（日线 + 周线 +60 分钟）
"""

import pandas as pd
import numpy as np
from data_fetcher import fetch_stock_kline, fetch_index_quote, fetch_sector_index


def calculate_trend(df, period='short'):
    """
    计算趋势方向
    
    参数：
        df: K 线 DataFrame
        period: short/medium/long
    
    返回：
        str: 'up' / 'down' / 'sideways'
    """
    if df.empty or len(df) < 20:
        return 'sideways'
    
    close = df['close']
    
    # 计算均线
    ma5 = close.iloc[-5:].mean()
    ma10 = close.iloc[-10:].mean()
    ma20 = close.iloc[-20:].mean()
    
    current = close.iloc[-1]
    
    # 判断趋势
    if period == 'short':
        if current > ma5 > ma10:
            return 'up'
        elif current < ma5 < ma10:
            return 'down'
        else:
            return 'sideways'
    
    elif period == 'medium':
        if ma5 > ma10 > ma20:
            return 'up'
        elif ma5 < ma10 < ma20:
            return 'down'
        else:
            return 'sideways'
    
    else:  # long
        if current > ma20 and ma20 > ma10:
            return 'up'
        elif current < ma20 and ma20 < ma10:
            return 'down'
        else:
            return 'sideways'


def analyze_multi_period_resonance(code):
    """
    多周期共振分析（日线 + 周线 +60 分钟）
    
    参数：
        code: 股票代码
    
    返回：
        dict: 共振分析结果
    """
    # 获取不同周期的 K 线
    df_day = fetch_stock_kline(code, period='day', count=60)
    df_week = fetch_stock_kline(code, period='week', count=20)
    df_60min = fetch_stock_kline(code, period='minute', count=60)
    
    result = {
        'code': code,
        'day_trend': 'sideways',
        'week_trend': 'sideways',
        'min60_trend': 'sideways',
        'resonance_type': '无共振',
        'resonance_strength': 0,
        'signals': []
    }
    
    if df_day.empty:
        return result
    
    # 分析各周期趋势
    result['day_trend'] = calculate_trend(df_day, 'medium')
    result['week_trend'] = calculate_trend(df_week, 'medium') if not df_week.empty else 'sideways'
    result['min60_trend'] = calculate_trend(df_60min, 'short') if not df_60min.empty else 'sideways'
    
    # 判断共振类型
    trends = [result['day_trend'], result['week_trend'], result['min60_trend']]
    
    up_count = trends.count('up')
    down_count = trends.count('down')
    
    if up_count == 3:
        result['resonance_type'] = '多头共振'
        result['resonance_strength'] = 3
        result['signals'].append('🟢 三周期多头共振 - 强烈看涨信号')
    elif up_count == 2:
        result['resonance_type'] = '偏多共振'
        result['resonance_strength'] = 2
        result['signals'].append('🟡 偏多共振 - 看涨信号较强')
    elif down_count == 3:
        result['resonance_type'] = '空头共振'
        result['resonance_strength'] = 3
        result['signals'].append('🔴 三周期空头共振 - 强烈看跌信号')
    elif down_count == 2:
        result['resonance_type'] = '偏空共振'
        result['resonance_strength'] = 2
        result['signals'].append('🟡 偏空共振 - 看跌信号较强')
    else:
        result['resonance_type'] = '无共振'
        result['resonance_strength'] = 0
        result['signals'].append('⚪ 周期信号不一致 - 观望')
    
    return result


def analyze_sector_correlation(code, sector_name):
    """
    分析个股与所属板块的联动性
    
    参数：
        code: 股票代码
        sector_name: 所属行业名称
    
    返回：
        dict: 板块联动分析结果
    """
    # 获取个股和板块指数的日 K 线
    df_stock = fetch_stock_kline(code, period='day', count=30)
    df_sector = fetch_sector_index(sector_name)
    
    result = {
        'code': code,
        'sector': sector_name,
        'correlation': 0,
        'relative_strength': 'neutral',
        'analysis': ''
    }
    
    if df_stock.empty or not df_sector:
        return result
    
    # 计算涨跌幅
    stock_change = df_stock['close'].pct_change()
    
    # 板块指数涨跌幅（简化处理）
    if isinstance(df_sector, dict):
        sector_change = df_sector.get('change_pct', 0) / 100
    else:
        sector_change = df_sector['close'].pct_change()
    
    # 计算相关性（最近 30 日）
    if len(stock_change) > 5:
        if isinstance(sector_change, (int, float)):
            # 板块只有单个数据，无法计算相关性
            result['correlation'] = 0.5  # 默认中性
        else:
            try:
                corr = stock_change.corr(sector_change)
                result['correlation'] = corr if not pd.isna(corr) else 0.5
            except:
                result['correlation'] = 0.5
    
    # 判断相对强弱
    stock_recent = df_stock['close'].iloc[-5:].pct_change().iloc[-1] if len(df_stock) > 5 else 0
    sector_recent = df_sector.get('change_pct', 0) / 100 if isinstance(df_sector, dict) else 0
    
    if stock_recent > sector_recent + 0.01:
        result['relative_strength'] = 'strong'
        result['analysis'] = f'个股强于板块（个股{stock_recent*100:.1f}% vs 板块{sector_recent*100:.1f}%）'
    elif stock_recent < sector_recent - 0.01:
        result['relative_strength'] = 'weak'
        result['analysis'] = f'个股弱于板块（个股{stock_recent*100:.1f}% vs 板块{sector_recent*100:.1f}%）'
    else:
        result['relative_strength'] = 'neutral'
        result['analysis'] = '个股与板块走势基本同步'
    
    return result


def analyze_market_correlation(code, index_code='000001'):
    """
    分析个股与大盘（上证指数）的相关性
    
    参数：
        code: 股票代码
        index_code: 指数代码（默认上证指数）
    
    返回：
        dict: 大盘共振分析结果
    """
    df_stock = fetch_stock_kline(code, period='day', count=30)
    df_index = fetch_stock_kline(index_code, period='day', count=30)
    
    result = {
        'code': code,
        'index': index_code,
        'correlation': 0,
        'beta': 1.0,
        'analysis': ''
    }
    
    if df_stock.empty or df_index.empty:
        return result
    
    # 计算涨跌幅
    stock_change = df_stock['close'].pct_change()
    index_change = df_index['close'].pct_change()
    
    # 计算相关性
    try:
        corr = stock_change.corr(index_change)
        result['correlation'] = corr if not pd.isna(corr) else 0.5
    except:
        result['correlation'] = 0.5
    
    # 计算 Beta 系数（个股相对大盘的弹性）
    try:
        cov = stock_change.cov(index_change)
        var = index_change.var()
        if var > 0:
            result['beta'] = cov / var
    except:
        result['beta'] = 1.0
    
    # 分析
    if result['correlation'] > 0.7:
        result['analysis'] = f'与大盘高度正相关 (r={result["correlation"]:.2f})，跟随大盘走势'
    elif result['correlation'] > 0.3:
        result['analysis'] = f'与大盘中等相关 (r={result["correlation"]:.2f})'
    elif result['correlation'] > -0.3:
        result['analysis'] = f'与大盘相关性弱 (r={result["correlation"]:.2f})，独立走势'
    else:
        result['analysis'] = f'与大盘负相关 (r={result["correlation"]:.2f})，逆周期'
    
    if result['beta'] > 1.2:
        result['analysis'] += '，弹性大于大盘（进攻型）'
    elif result['beta'] < 0.8:
        result['analysis'] += '，弹性小于大盘（防御型）'
    
    return result


def get_full_resonance_analysis(code, sector_name=None):
    """
    获取完整的共振分析报告
    
    参数：
        code: 股票代码
        sector_name: 所属行业（可选）
    
    返回：
        dict: 完整共振分析
    """
    multi_period = analyze_multi_period_resonance(code)
    market_corr = analyze_market_correlation(code)
    
    sector_corr = None
    if sector_name:
        sector_corr = analyze_sector_correlation(code, sector_name)
    
    # 综合评分
    total_score = 0
    max_score = 10
    
    # 多周期共振评分（0-4 分）
    total_score += multi_period['resonance_strength']
    
    # 大盘相关性评分（0-3 分）
    if abs(market_corr['correlation']) > 0.5:
        total_score += 2
    elif abs(market_corr['correlation']) > 0.3:
        total_score += 1
    
    # 板块联动评分（0-3 分）
    if sector_corr:
        if sector_corr['relative_strength'] == 'strong':
            total_score += 3
        elif sector_corr['relative_strength'] == 'neutral':
            total_score += 1
    
    return {
        'code': code,
        'multi_period': multi_period,
        'market_correlation': market_corr,
        'sector_correlation': sector_corr,
        'total_score': total_score,
        'max_score': max_score,
        'rating': '强' if total_score >= 7 else '中' if total_score >= 4 else '弱'
    }


if __name__ == '__main__':
    # 测试
    print("测试共振分析 (600036):")
    result = get_full_resonance_analysis('600036', '银行')
    
    print(f"  多周期：{result['multi_period']['resonance_type']}")
    print(f"  大盘相关：{result['market_correlation']['analysis']}")
    if result['sector_correlation']:
        print(f"  板块联动：{result['sector_correlation']['analysis']}")
    print(f"  综合评分：{result['total_score']}/{result['max_score']} ({result['rating']})")
