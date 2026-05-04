# -*- coding: utf-8 -*-
"""
紧急预警脚本
实时监控突破/跌破关键位置、成交量异常等
"""

import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import read_holdings, is_trading_day
from event_calendar import get_emergency_alerts
from data_fetcher import fetch_stock_quote


def main():
    """主函数"""
    print("=" * 60)
    print("  A 股持仓紧急预警扫描")
    print("=" * 60)
    
    # 检查是否为交易日
    if not is_trading_day():
        print("⚠️  今日非交易日，跳过扫描")
        return []
    
    # 读取持仓
    holdings = read_holdings()
    if not holdings:
        print("❌ 无法读取持仓文件")
        return []
    
    print(f"📦 扫描持仓：{len(holdings)}只")
    
    # 获取预警
    alerts = get_emergency_alerts(holdings)
    
    if not alerts:
        print("\n✅ 无紧急预警")
    else:
        print(f"\n🚨 发现 {len(alerts)} 项预警:\n")
        
        # 按紧急程度排序
        high_urgency = [a for a in alerts if a['urgency'] == '高']
        mid_urgency = [a for a in alerts if a['urgency'] == '中']
        
        if high_urgency:
            print("【高优先级】")
            for alert in high_urgency:
                print(f"  🔴 {alert['name']} ({alert['code']})")
                print(f"     类型：{alert['type']}")
                print(f"     详情：{alert['detail']}")
                print()
        
        if mid_urgency:
            print("【中优先级】")
            for alert in mid_urgency:
                print(f"  🟡 {alert['name']} ({alert['code']})")
                print(f"     类型：{alert['type']}")
                print(f"     详情：{alert['detail']}")
                print()
    
    print("=" * 60)
    
    return alerts


if __name__ == '__main__':
    alerts = main()
