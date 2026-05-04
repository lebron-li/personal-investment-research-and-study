# -*- coding: utf-8 -*-
"""
完整报告测试脚本（忽略交易日检查）
用于验证报告生成功能
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import read_holdings
from report_generator import generate_noon_report, generate_evening_report, save_report

print("=" * 60)
print("  完整报告生成测试")
print("=" * 60)

# 读取持仓
holdings = read_holdings()
print(f"\n持仓：{len(holdings)}只")
for h in holdings:
    print(f"  - {h['name']} ({h['code']})")

# 生成午间报告
print("\n" + "-" * 60)
print("  生成午间快评...")
print("-" * 60)

noon_report = generate_noon_report(holdings)
noon_path = save_report(noon_report, report_type='午间')

print(f"\n✅ 午间报告已保存：{noon_path}")
print(f"   报告长度：{len(noon_report)}字符")

# 生成晚间报告
print("\n" + "-" * 60)
print("  生成晚间复盘...")
print("-" * 60)

evening_report = generate_evening_report(holdings)
evening_path = save_report(evening_report, report_type='晚间')

print(f"\n✅ 晚间报告已保存：{evening_path}")
print(f"   报告长度：{len(evening_report)}字符")

print("\n" + "=" * 60)
print("  测试完成！")
print("=" * 60)
print(f"\n📁 报告位置:")
print(f"   午间：{noon_path}")
print(f"   晚间：{evening_path}")
