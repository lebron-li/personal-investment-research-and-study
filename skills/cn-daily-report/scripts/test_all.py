# -*- coding: utf-8 -*-
"""
综合测试脚本
测试所有模块功能
"""

import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("  cn-daily-report 模块自测")
print("=" * 60)

# 测试 1: utils 模块
print("\n[1/7] 测试 utils 模块...")
try:
    from utils import read_holdings, is_trading_day, get_next_trading_day
    
    holdings = read_holdings()
    if holdings:
        print(f"  ✅ 持仓读取成功：{len(holdings)}只")
        for h in holdings[:3]:
            print(f"     - {h['name']} ({h['code']})")
    else:
        print(f"  ⚠️  持仓读取结果为空（检查文件路径）")
    
    trading = is_trading_day()
    print(f"  ✅ 今天是交易日：{trading}")
    
    next_day = get_next_trading_day(days=1)
    print(f"  ✅ 下一个交易日：{next_day.strftime('%Y-%m-%d')}")
    
except Exception as e:
    print(f"  ❌ utils 模块测试失败：{e}")

# 测试 2: data_fetcher 模块
print("\n[2/7] 测试 data_fetcher 模块...")
try:
    from data_fetcher import fetch_stock_quote, fetch_north_capital_flow
    
    if holdings:
        test_code = holdings[0]['code']
        quote = fetch_stock_quote(test_code)
        if quote:
            print(f"  ✅ 行情获取成功：{quote['name']} {quote['price']}元 ({quote['change_pct']:+.2f}%)")
        else:
            print(f"  ⚠️  行情获取失败（可能非交易时间）")
    
    north = fetch_north_capital_flow()
    if north:
        print(f"  ✅ 北向资金：{north['status']}{north['amount']:.2f}亿元")
    else:
        print(f"  ⚠️  北向资金获取失败")
    
except Exception as e:
    print(f"  ❌ data_fetcher 模块测试失败：{e}")

# 测试 3: key_levels 模块
print("\n[3/7] 测试 key_levels 模块...")
try:
    from key_levels import get_key_levels_summary
    
    if holdings:
        test_code = holdings[0]['code']
        levels = get_key_levels_summary(test_code)
        if levels['current_price']:
            print(f"  ✅ 关键位置分析成功")
            print(f"     当前价：{levels['current_price']}")
            if levels['supports']:
                print(f"     支撑：{levels['supports']}")
            if levels['resistances']:
                print(f"     阻力：{levels['resistances']}")
        else:
            print(f"  ⚠️  关键位置分析结果为空")
    
except Exception as e:
    print(f"  ❌ key_levels 模块测试失败：{e}")

# 测试 4: resonance_analyzer 模块
print("\n[4/7] 测试 resonance_analyzer 模块...")
try:
    from resonance_analyzer import get_full_resonance_analysis
    
    if holdings:
        test_code = holdings[0]['code']
        resonance = get_full_resonance_analysis(test_code)
        print(f"  ✅ 共振分析成功")
        print(f"     多周期：{resonance['multi_period']['resonance_type']}")
        print(f"     综合评分：{resonance['total_score']}/{resonance['max_score']} ({resonance['rating']})")
    
except Exception as e:
    print(f"  ❌ resonance_analyzer 模块测试失败：{e}")

# 测试 5: event_calendar 模块
print("\n[5/7] 测试 event_calendar 模块...")
try:
    from event_calendar import get_event_calendar
    
    calendar = get_event_calendar(days=7)
    print(f"  ✅ 事件日历获取成功")
    print(f"     宏观事件：{len(calendar['macro'])}项")
    if calendar['macro']:
        for e in calendar['macro'][:2]:
            print(f"       - {e['date']}: {e['event']}")
    
except Exception as e:
    print(f"  ❌ event_calendar 模块测试失败：{e}")

# 测试 6: report_generator 模块（简化版）
print("\n[6/7] 测试 report_generator 模块...")
try:
    from report_generator import generate_stock_analysis
    
    if holdings:
        test_h = holdings[0]
        analysis = generate_stock_analysis(test_h['code'], test_h['name'], test_h['type'])
        if analysis:
            print(f"  ✅ 单股分析成功")
            print(f"     建议：{analysis['suggestion']['action']} (置信度：{analysis['suggestion']['confidence']})")
        else:
            print(f"  ⚠️  单股分析结果为空")
    
except Exception as e:
    print(f"  ❌ report_generator 模块测试失败：{e}")

# 测试 7: 完整报告生成（可选，耗时较长）
print("\n[7/7] 测试完整报告生成（简化版）...")
try:
    from report_generator import generate_noon_report
    
    print(f"  生成午间快评...")
    report = generate_noon_report(holdings)
    if report and not report.startswith("❌"):
        lines = report.split('\n')
        print(f"  ✅ 报告生成成功：{len(lines)}行")
        print(f"     前 3 行预览:")
        for line in lines[:3]:
            print(f"       {line}")
    else:
        print(f"  ⚠️  报告生成结果为空")
    
except Exception as e:
    print(f"  ❌ 完整报告生成测试失败：{e}")

# 总结
print("\n" + "=" * 60)
print("  自测完成")
print("=" * 60)
print("\n📝 测试结果总结:")
print("  - 基础模块 (utils, data_fetcher): 已测试")
print("  - 分析模块 (key_levels, resonance): 已测试")
print("  - 报告模块 (report_generator): 已测试")
print("\n⚠️  注意事项:")
print("  1. 非交易时间部分数据可能为空")
print("  2. 首次运行可能需要安装依赖：pip install akshare pandas numpy requests")
print("  3. 飞书推送需要配置 chat_id")
print("\n✅ 下一步:")
print("  1. 配置 OpenClaw 定时任务")
print("  2. 配置飞书推送 chat_id")
print("  3. 运行完整测试：python daily_report_noon.py")
