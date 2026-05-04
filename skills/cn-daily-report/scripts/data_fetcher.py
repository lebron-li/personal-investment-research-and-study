# -*- coding: utf-8 -*-
"""
数据获取模块（腾讯财经主用版）
- 主要使用腾讯财经接口（速度快且可访问）
- 备用新浪财经（如果腾讯失败）
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import re


def fetch_stock_quote_tencent(code):
    """
    使用腾讯财经接口获取股票/ETF 实时行情数据（主用）
    """
    if code.startswith('6') or code.startswith('5'):
        market = 'sh'
    else:
        market = 'sz'
    
    url = f"http://qt.gtimg.cn/q={market}{code}"
    
    try:
        response = requests.get(url, timeout=5)
        response.encoding = 'gbk'
        content = response.text
        
        match = re.search(r'"(.+)"', content)
        if not match:
            return None
        
        data_str = match.group(1)
        fields = data_str.split('~')
        
        # 腾讯财经字段说明：
        # [0]: 市场代码
        # [1]: 股票名称  
        # [2]: 股票代码
        # [3]: 当前价
        # [4]: 昨收
        # [5]: 开盘
        # [6]: 最高价
        # [7]: 最低价
        # [8]: 买一价
        # [9]: 卖一价
        # [10]: 成交量（股）
        # [11]: 成交额（元）
        
        if len(fields) < 12:
            return None
        
        quote = {
            'code': code,
            'name': fields[1],
            'price': float(fields[3]) if fields[3] else 0,
            'close': float(fields[4]) if fields[4] else 0,  # 昨收
            'open': float(fields[5]) if fields[5] else 0,
            'high': float(fields[6]) if fields[6] else 0,
            'low': float(fields[7]) if fields[7] else 0,
            'volume': float(fields[10]) if fields[10] else 0,
            'amount': float(fields[11]) if fields[11] else 0,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'time': datetime.now().strftime('%H:%M:%S'),
        }
        
        # 计算涨跌幅
        if quote['close'] > 0:
            quote['change_pct'] = (quote['price'] - quote['close']) / quote['close'] * 100
        else:
            quote['change_pct'] = 0
        
        quote['change'] = quote['price'] - quote['close']
        
        if quote['price'] > 0:
            return quote
            
    except Exception as e:
        print(f"腾讯财经获取失败 {code}: {e}")
        return None
    
    return None


def fetch_stock_quote_sina(code):
    """
    使用新浪财经接口获取股票/ETF 实时行情数据（备用）
    """
    if code.startswith('6') or code.startswith('5'):
        market = 'sh'
    else:
        market = 'sz'
    
    url = f"http://hq.sinajs.cn/list={market}{code}"
    
    try:
        response = requests.get(url, timeout=5)
        response.encoding = 'gbk'
        content = response.text
        
        match = re.search(r'"(.+)"', content)
        if not match:
            return None
        
        data_str = match.group(1)
        fields = data_str.split(',')
        
        if len(fields) < 32:
            return None
        
        quote = {
            'code': code,
            'name': fields[0],
            'price': float(fields[3]) if fields[3] else 0,
            'open': float(fields[1]) if fields[1] else 0,
            'high': float(fields[4]) if fields[4] else 0,
            'low': float(fields[5]) if fields[5] else 0,
            'close': float(fields[2]) if fields[2] else 0,
            'volume': float(fields[8]) if fields[8] else 0,
            'amount': float(fields[9]) if fields[9] else 0,
            'bid1': float(fields[11]) if fields[11] else 0,
            'ask1': float(fields[21]) if fields[21] else 0,
            'date': fields[30] if len(fields) > 30 else '',
            'time': fields[31] if len(fields) > 31 else '',
        }
        
        if quote['close'] > 0:
            quote['change_pct'] = (quote['price'] - quote['close']) / quote['close'] * 100
        else:
            quote['change_pct'] = 0
        
        quote['change'] = quote['price'] - quote['close']
        
        if quote['price'] > 0:
            return quote
            
    except Exception as e:
        print(f"新浪财经获取失败 {code}: {e}")
        return None
    
    return None


def fetch_stock_quote(code):
    """
    获取股票/ETF 实时行情数据（腾讯财经主用）
    """
    # 主要用腾讯财经
    quote = fetch_stock_quote_tencent(code)
    if quote:
        print(f"✅ {code} 使用 腾讯财经")
        return quote
    
    # 失败则尝试新浪财经
    quote = fetch_stock_quote_sina(code)
    if quote:
        print(f"✅ {code} 使用 新浪财经")
        return quote
    
    print(f"❌ 所有数据源获取失败 {code}")
    return None


# 其余函数简化...
def fetch_stock_kline(code, period='day', count=100):
    """K线数据暂时返回空，避免影响速度"""
    return pd.DataFrame()


def fetch_north_capital_flow():
    """北向资金暂时返回模拟数据"""
    return {
        'net_inflow': 15.23,
        'status': '流入',
        'amount': 15.23
    }


def fetch_main_force_flow(code):
    """主力资金暂时返回None，避免错误"""
    return None


def fetch_index_quote(index_code):
    return fetch_stock_quote(index_code)


def fetch_sector_index(sector_name):
    sector_codes = {
        '食品饮料': '881124',
        '银行': '881154', 
        '医药': '881107',
        '家电': '881133',
        '电力': '881140',
        '创新药': '881167',
    }
    code = sector_codes.get(sector_name)
    if not code:
        return None
    return fetch_stock_quote(code)


def fetch_financial_calendar(code, days=7):
    return []


def fetch_macro_events(days=7):
    return []


def calculate_volume_ratio(code):
    return 1.0


if __name__ == '__main__':
    print("测试行情获取:")
    quote = fetch_stock_quote('600036')
    if quote:
        print(f"  招商银行：{quote['price']}元，涨跌幅：{quote['change_pct']:.2f}%")
    
    quote = fetch_stock_quote('515170')
    if quote:
        print(f"  食品饮料ETF：{quote['price']}元，涨跌幅：{quote['change_pct']:.2f}%")