# -*- coding: utf-8 -*-
"""
事件日历和紧急预警模块
"""

from datetime import datetime, timedelta
from data_fetcher import fetch_stock_quote


def get_event_calendar():
    """
    获取事件日历（财报、宏观数据等）
    """
    return {
        'financial': [],
        'macro': []
    }


def get_emergency_alerts(holdings):
    """
    获取紧急预警
    """
    alerts = []
    
    for holding in holdings:
        code = holding['code']
        name = holding['name']
        
        # 获取当前价格
        quote = fetch_stock_quote(code)
        if not quote:
            continue
            
        current_price = quote['price']
        change_pct = quote['change_pct']
        
        # 大涨大跌预警
        if change_pct > 7:
            alerts.append({
                'code': code,
                'name': name,
                'type': '大涨',
                'detail': f'单日大涨 {change_pct:.2f}%'
            })
        elif change_pct < -7:
            alerts.append({
                'code': code,
                'name': name,
                'type': '大跌',
                'detail': f'单日大跌 {abs(change_pct):.2f}%'
            })
            
        # 成交量异常预警（简化版）
        # 这里暂时不实现，避免依赖其他模块
        
    return alerts