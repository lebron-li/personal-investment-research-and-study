# -*- coding: utf-8 -*-
"""
午间快评脚本
每个交易日 11:35 执行
"""

import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from report_generator import generate_noon_report, save_report
from utils import is_trading_day, read_holdings
from event_calendar import get_emergency_alerts


def main():
    """主函数"""
    print("=" * 60)
    print("  A 股持仓午间快评")
    print("=" * 60)
    
    # 检查是否为交易日
    if not is_trading_day():
        print("⚠️  今日非交易日，跳过分析")
        return None
    
    # 读取持仓
    holdings = read_holdings()
    if not holdings:
        print("❌ 无法读取持仓文件")
        return None
    
    print(f"📦 持仓数量：{len(holdings)}只")
    for h in holdings:
        print(f"   - {h['name']} ({h['code']})")
    
    # 生成报告
    print("\n📝 生成报告中...")
    report = generate_noon_report(holdings)
    
    if report.startswith("❌"):
        print(f"❌ 报告生成失败：{report}")
        return None
    
    # 保存报告
    filepath = save_report(report, report_type='午间')
    print(f"✅ 报告已保存：{filepath}")
    
    # 检查紧急预警
    print("\n🚨 检查紧急预警...")
    alerts = get_emergency_alerts(holdings)
    if alerts:
        print(f"⚠️  发现 {len(alerts)} 项预警:")
        for alert in alerts:
            print(f"   - {alert['name']}: {alert['detail']}")
    else:
        print("✅ 无紧急预警")
    
    print("\n" + "=" * 60)
    print("  午间快评完成")
    print("=" * 60)
    
    return {
        'report': report,
        'filepath': filepath,
        'alerts': alerts
    }


if __name__ == '__main__':
    result = main()
