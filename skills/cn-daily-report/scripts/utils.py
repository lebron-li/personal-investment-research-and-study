# -*- coding: utf-8 -*-
"""
工具函数模块
- 交易日判断
- 持仓文件读取
- 日期格式化
"""

import os
import re
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup


def read_holdings(file_path=r"C:\agent\03-portfolio-tools\my-holdings.txt"):
    """
    读取持仓文件，返回股票代码/ETF 代码列表
    
    文件格式示例：
    1、食品饮料 ETF 515170
    2、美的集团 000333
    
    返回：[{'name': '食品饮料 ETF', 'code': '515170', 'type': 'ETF'}, ...]
    """
    holdings = []
    
    if not os.path.exists(file_path):
        print(f"警告：持仓文件不存在：{file_path}")
        return holdings
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 正则匹配：名称 + 代码
    # 匹配模式：数字 + 顿号/点 + 名称 + 空格 + 6 位代码
    pattern = r'\d+[、\.]\s*(.+?)\s+(\d{6})'
    matches = re.findall(pattern, content)
    
    for name, code in matches:
        # 判断是股票还是 ETF
        if 'ETF' in name or code.startswith('5') or code.startswith('15'):
            asset_type = 'ETF'
        elif code.startswith('6'):
            asset_type = 'SH_STOCK'  # 沪市股票
        elif code.startswith('0') or code.startswith('3'):
            asset_type = 'SZ_STOCK'  # 深市股票
        else:
            asset_type = 'STOCK'
        
        holdings.append({
            'name': name.strip(),
            'code': code,
            'type': asset_type
        })
    
    return holdings


def is_trading_day(date=None):
    """
    判断给定日期是否为 A 股交易日
    
    参数：
        date: datetime 对象，默认为今天
    
    返回：
        bool: True=交易日，False=休市
    """
    if date is None:
        date = datetime.now()
    
    # 周末判断
    if date.weekday() >= 5:  # 5=周六，6=周日
        return False
    
    # 获取中国法定节假日
    holidays = get_china_holidays(date.year)
    
    date_str = date.strftime('%Y-%m-%d')
    if date_str in holidays:
        return False
    
    return True


def get_china_holidays(year):
    """
    获取中国 A 股休市日期（简化版，需要每年更新）
    
    实际生产中应该从官方 API 获取
    这里提供 2024-2026 年的主要节假日
    """
    holidays = {
        2024: [
            '2024-01-01',  # 元旦
            '2024-02-10', '2024-02-11', '2024-02-12', '2024-02-13', '2024-02-14', '2024-02-15', '2024-02-16', '2024-02-17',  # 春节
            '2024-04-04', '2024-04-05', '2024-04-06',  # 清明
            '2024-05-01', '2024-05-02', '2024-05-03', '2024-05-04', '2024-05-05',  # 劳动节
            '2024-06-10',  # 端午
            '2024-09-17',  # 中秋
            '2024-10-01', '2024-10-02', '2024-10-03', '2024-10-04', '2024-10-05', '2024-10-06', '2024-10-07',  # 国庆
        ],
        2025: [
            '2025-01-01',  # 元旦
            '2025-01-28', '2025-01-29', '2025-01-30', '2025-01-31', '2025-02-01', '2025-02-02', '2025-02-03', '2025-02-04',  # 春节
            '2025-04-04', '2025-04-05', '2025-04-06',  # 清明
            '2025-05-01', '2025-05-02', '2025-05-03', '2025-05-04', '2025-05-05',  # 劳动节
            '2025-05-31', '2025-06-01', '2025-06-02',  # 端午
            '2025-10-01', '2025-10-02', '2025-10-03', '2025-10-04', '2025-10-05', '2025-10-06', '2025-10-07', '2025-10-08',  # 国庆 + 中秋
        ],
        2026: [
            '2026-01-01', '2026-01-02', '2026-01-03',  # 元旦
            '2026-02-17', '2026-02-18', '2026-02-19', '2026-02-20', '2026-02-21', '2026-02-22', '2026-02-23', '2026-02-24',  # 春节
            '2026-04-05', '2026-04-06', '2026-04-07',  # 清明
            '2026-05-01', '2026-05-02', '2026-05-03', '2026-05-04', '2026-05-05',  # 劳动节
            '2026-06-19', '2026-06-20', '2026-06-21',  # 端午
            '2026-09-25', '2026-09-26', '2026-09-27',  # 中秋
            '2026-10-01', '2026-10-02', '2026-10-03', '2026-10-04', '2026-10-05', '2026-10-06', '2026-10-07', '2026-10-08',  # 国庆
        ]
    }
    
    return holidays.get(year, [])


def get_next_trading_day(date=None, days=1):
    """
    获取指定日期之后的下一个交易日
    
    参数：
        date: 起始日期
        days: 往后多少天
    
    返回：
        datetime: 下一个交易日
    """
    if date is None:
        date = datetime.now()
    
    current = date
    count = 0
    
    while count < days:
        current += timedelta(days=1)
        if is_trading_day(current):
            count += 1
    
    return current


def format_date(date, format_str='%Y-%m-%d'):
    """格式化日期"""
    if date is None:
        date = datetime.now()
    return date.strftime(format_str)


def format_time(date, format_str='%H:%M'):
    """格式化时间"""
    if date is None:
        date = datetime.now()
    return date.strftime(format_str)


def get_report_filename(report_type='午间', date=None):
    """
    生成报告文件名
    
    参数：
        report_type: '午间' 或 '晚间'
        date: 日期
    
    返回：
        str: 文件名
    """
    if date is None:
        date = datetime.now()
    
    date_str = format_date(date, '%Y-%m-%d')
    return f"持仓日报_{date_str}_{report_type}.md"


def get_report_filepath(report_type='午间', date=None):
    """
    生成报告完整路径
    
    返回：
        str: 完整文件路径
    """
    filename = get_report_filename(report_type, date)
    return f"C:\\Users\\李正材\\Desktop\\持仓日报\\{filename}"


if __name__ == '__main__':
    # 测试
    print("测试持仓读取:")
    holdings = read_holdings()
    for h in holdings:
        print(f"  {h['name']} ({h['code']}) - {h['type']}")
    
    print(f"\n今天是交易日吗？{is_trading_day()}")
    print(f"下一个交易日：{get_next_trading_day(days=1)}")
