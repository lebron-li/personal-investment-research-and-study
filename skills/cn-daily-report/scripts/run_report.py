# -*- coding: utf-8 -*-
"""
OpenClaw 集成脚本
可通过 OpenClaw 直接调用
"""

import sys
import os
import json

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import read_holdings, is_trading_day
from report_generator import generate_noon_report, generate_evening_report, save_report
from event_calendar import get_emergency_alerts
from feishu_push import send_noon_report, send_evening_report, send_emergency_alert


def run_noon_report():
    """执行午间快评"""
    result = {
        'success': False,
        'report': '',
        'filepath': '',
        'alerts': [],
        'message': ''
    }
    
    # 检查交易日
    if not is_trading_day():
        result['message'] = '今日非交易日，跳过分析'
        return result
    
    # 读取持仓
    holdings = read_holdings()
    if not holdings:
        result['message'] = '无法读取持仓文件'
        return result
    
    # 生成报告
    try:
        report = generate_noon_report(holdings)
        if report.startswith('❌'):
            result['message'] = report
            return result
        
        # 保存报告
        filepath = save_report(report, report_type='午间')
        
        # 检查预警
        alerts = get_emergency_alerts(holdings)
        
        result['success'] = True
        result['report'] = report
        result['filepath'] = filepath
        result['alerts'] = alerts
        result['message'] = f'午间快评已生成：{filepath}'
        
        # 飞书推送
        try:
            push_result = send_noon_report(report, filepath)
            result['feishu'] = push_result
        except Exception as e:
            result['feishu'] = {'success': False, 'message': str(e)}
        
    except Exception as e:
        result['message'] = f'报告生成失败：{str(e)}'
    
    return result


def run_evening_report():
    """执行晚间复盘"""
    result = {
        'success': False,
        'report': '',
        'filepath': '',
        'alerts': [],
        'message': ''
    }
    
    # 检查交易日
    if not is_trading_day():
        result['message'] = '今日非交易日，跳过分析'
        return result
    
    # 读取持仓
    holdings = read_holdings()
    if not holdings:
        result['message'] = '无法读取持仓文件'
        return result
    
    # 生成报告
    try:
        report = generate_evening_report(holdings)
        if report.startswith('❌'):
            result['message'] = report
            return result
        
        # 保存报告
        filepath = save_report(report, report_type='晚间')
        
        # 检查预警
        alerts = get_emergency_alerts(holdings)
        
        result['success'] = True
        result['report'] = report
        result['filepath'] = filepath
        result['alerts'] = alerts
        result['message'] = f'晚间复盘已生成：{filepath}'
        
        # 飞书推送
        try:
            push_result = send_evening_report(report, filepath)
            result['feishu'] = push_result
        except Exception as e:
            result['feishu'] = {'success': False, 'message': str(e)}
        
    except Exception as e:
        result['message'] = f'报告生成失败：{str(e)}'
    
    return result


def check_emergency():
    """检查紧急预警"""
    result = {
        'success': False,
        'alerts': [],
        'message': ''
    }
    
    # 检查交易日
    if not is_trading_day():
        result['message'] = '今日非交易日，跳过扫描'
        return result
    
    # 读取持仓
    holdings = read_holdings()
    if not holdings:
        result['message'] = '无法读取持仓文件'
        return result
    
    try:
        alerts = get_emergency_alerts(holdings)
        result['success'] = True
        result['alerts'] = alerts
        result['message'] = f'发现 {len(alerts)} 项预警' if alerts else '无紧急预警'
        
        # 飞书推送（仅在有预警时）
        if alerts:
            try:
                push_result = send_emergency_alert(alerts)
                result['feishu'] = push_result
            except Exception as e:
                result['feishu'] = {'success': False, 'message': str(e)}
        
    except Exception as e:
        result['message'] = f'预警检查失败：{str(e)}'
    
    return result


if __name__ == '__main__':
    # 命令行参数：noon / evening / emergency
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'noon':
            result = run_noon_report()
        elif command == 'evening':
            result = run_evening_report()
        elif command == 'emergency':
            result = check_emergency()
        else:
            result = {'success': False, 'message': f'未知命令：{command}'}
    else:
        # 默认执行午间报告
        result = run_noon_report()
    
    # 输出 JSON 结果
    print(json.dumps(result, ensure_ascii=False, indent=2))
