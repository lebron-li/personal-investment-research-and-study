# -*- coding: utf-8 -*-
"""
报告生成模块
- 午间快评报告
- 晚间复盘报告
- Markdown 格式输出
"""

from datetime import datetime
from data_fetcher import (
    fetch_stock_quote, fetch_north_capital_flow, 
    fetch_main_force_flow, calculate_volume_ratio
)
from key_levels import get_key_levels_summary
from resonance_analyzer import get_full_resonance_analysis
from event_calendar import get_event_calendar
from utils import read_holdings, get_report_filepath, format_date


def generate_stock_analysis(code, name, asset_type):
    """
    生成单只股票/ETF 的分析
    
    返回：
        dict: 分析结果
    """
    # 基础行情
    quote = fetch_stock_quote(code)
    
    # 非交易时间使用占位数据
    if not quote:
        quote = {
            'code': code,
            'name': name,
            'price': 0,
            'change_pct': 0,
            'change': 0,
            'volume': 0,
            'amount': 0
        }
    
    # 关键位置
    key_levels = get_key_levels_summary(code)
    
    # 共振分析
    # 简化版：ETF 不分析板块联动
    sector = None
    if asset_type not in ['ETF']:
        sector_map = {
            '000333': '家电',
            '600036': '银行',
            '600900': '电力',
        }
        sector = sector_map.get(code)
    
    resonance = get_full_resonance_analysis(code, sector)
    
    # 资金面
    main_force = fetch_main_force_flow(code)
    volume_ratio = calculate_volume_ratio(code)
    
    # 操作建议生成
    suggestion = generate_suggestion(quote, key_levels, resonance, volume_ratio)
    
    return {
        'code': code,
        'name': name,
        'type': asset_type,
        'quote': quote,
        'key_levels': key_levels,
        'resonance': resonance,
        'fund_flow': {
            'main_force': main_force,
            'volume_ratio': volume_ratio
        },
        'suggestion': suggestion
    }


def generate_suggestion(quote, key_levels, resonance, volume_ratio):
    """
    生成操作建议
    
    返回：
        dict: 操作建议
    """
    current_price = quote['price']
    change_pct = quote['change_pct']
    
    # 评分系统
    score = 50  # 基础分
    
    signals = []
    
    # 涨跌幅评分
    if change_pct > 3:
        score += 10
        signals.append('✅ 大涨 (>3%)')
    elif change_pct > 1:
        score += 5
        signals.append('✅ 上涨')
    elif change_pct < -3:
        score -= 10
        signals.append('❌ 大跌 (>3%)')
    elif change_pct < -1:
        score -= 5
        signals.append('❌ 下跌')
    
    # 共振评分
    if resonance['multi_period']['resonance_type'] == '多头共振':
        score += 15
        signals.append('✅ 多头共振')
    elif resonance['multi_period']['resonance_type'] == '空头共振':
        score -= 15
        signals.append('❌ 空头共振')
    
    # 成交量评分
    if volume_ratio > 2:
        score += 5
        signals.append(f'✅ 放量 (量比{volume_ratio:.1f})')
    elif volume_ratio < 0.5:
        score -= 5
        signals.append(f'❌ 缩量 (量比{volume_ratio:.1f})')
    
    # 关键位置评分
    if key_levels['alerts']:
        for alert in key_levels['alerts']:
            if '突破' in alert['type']:
                score += 10
                signals.append(f"✅ {alert['type']}")
            elif '跌破' in alert['type']:
                score -= 10
                signals.append(f"❌ {alert['type']}")
    
    # 确定建议
    if score >= 70:
        action = '加仓/持有'
        confidence = '高'
    elif score >= 60:
        action = '持有'
        confidence = '中高'
    elif score >= 40:
        action = '观望'
        confidence = '中'
    elif score >= 30:
        action = '减仓'
        confidence = '中低'
    else:
        action = '卖出/回避'
        confidence = '低'
    
    return {
        'score': score,
        'action': action,
        'confidence': confidence,
        'signals': signals
    }


def generate_noon_report(holdings=None):
    """
    生成午间快评报告
    
    参数：
        holdings: 持仓列表（可选，不传则自动读取）
    
    返回：
        str: Markdown 格式报告
    """
    if holdings is None:
        holdings = read_holdings()
    
    if not holdings:
        return "❌ 无法读取持仓文件"
    
    # 获取北向资金
    north = fetch_north_capital_flow()
    
    # 分析每只持仓
    analyses = []
    for h in holdings:
        analysis = generate_stock_analysis(h['code'], h['name'], h['type'])
        if analysis:
            analyses.append(analysis)
    
    # 生成报告
    report = []
    report.append("# 📊 持仓午间快评")
    report.append(f"\n**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report.append(f"**持仓数量**: {len(analyses)}只\n")
    
    # 资金面概览
    report.append("## 💰 资金面概览\n")
    if north:
        status_icon = '🟢' if north['net_inflow'] > 0 else '🔴'
        report.append(f"- {status_icon} 北向资金：{north['status']}{north['amount']:.2f}亿元")
    else:
        report.append("- ⚪ 北向资金：数据暂缺")
    report.append("")
    
    # 30 秒快读
    report.append("## ⚡ 30 秒快读\n")
    
    total_change = sum(a['quote']['change_pct'] for a in analyses)
    avg_change = total_change / len(analyses) if analyses else 0
    
    up_count = sum(1 for a in analyses if a['quote']['change_pct'] > 0)
    down_count = len(analyses) - up_count
    
    report.append(f"- 持仓涨跌：{up_count}涨 {down_count}跌，平均涨跌幅：{avg_change:+.2f}%")
    
    # 最佳/最差
    if analyses:
        best = max(analyses, key=lambda x: x['quote']['change_pct'])
        worst = min(analyses, key=lambda x: x['quote']['change_pct'])
        report.append(f"- 表现最佳：{best['name']} ({best['quote']['change_pct']:+.2f}%)")
        report.append(f"- 表现最差：{worst['name']} ({worst['quote']['change_pct']:+.2f}%)")
    report.append("")
    
    # 下午操作建议
    report.append("## 📋 下午操作建议\n")
    report.append("| 代码 | 名称 | 当前价 | 涨跌 | 建议 | 置信度 |")
    report.append("|------|------|--------|------|------|--------|")
    
    for a in analyses:
        quote = a['quote']
        sugg = a['suggestion']
        icon = '🟢' if sugg['score'] >= 60 else '🟡' if sugg['score'] >= 40 else '🔴'
        report.append(
            f"| {a['code']} | {a['name']} | {quote['price']:.2f} | {quote['change_pct']:+.2f}% | "
            f"{icon} {sugg['action']} | {sugg['confidence']} |"
        )
    report.append("")
    
    # 重点关注
    report.append("## 🔍 下午重点关注\n")
    
    # 找出可能有异动的
    focus_list = [a for a in analyses if abs(a['quote']['change_pct']) > 2 or a['fund_flow']['volume_ratio'] > 2]
    
    if focus_list:
        for a in focus_list:
            report.append(f"- **{a['name']}**: {a['suggestion']['signals']}")
    else:
        report.append("- 暂无特别需要关注的标的")
    report.append("")
    
    # 风险提示
    report.append("## ⚠️ 风险提示\n")
    report.append("- 午间数据仅供参考，下午走势可能变化")
    report.append("- 请结合晚间复盘做最终决策")
    report.append("\n---")
    report.append("*报告生成时间：" + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + "*")
    
    return '\n'.join(report)


def generate_evening_report(holdings=None):
    """
    生成晚间复盘报告
    
    参数：
        holdings: 持仓列表（可选）
    
    返回：
        str: Markdown 格式报告
    """
    if holdings is None:
        holdings = read_holdings()
    
    if not holdings:
        return "❌ 无法读取持仓文件"
    
    # 获取北向资金
    north = fetch_north_capital_flow()
    
    # 获取事件日历
    events = get_event_calendar()
    
    # 分析每只持仓
    analyses = []
    for h in holdings:
        analysis = generate_stock_analysis(h['code'], h['name'], h['type'])
        if analysis:
            analyses.append(analysis)
    
    # 生成报告
    report = []
    report.append("# 📊 持仓晚间复盘")
    report.append(f"\n**时间**: {datetime.now().strftime('%Y-%m-%d')}")
    report.append(f"**持仓数量**: {len(analyses)}只\n")
    
    # 市场概览
    report.append("## 🌍 市场环境\n")
    if north:
        status_icon = '🟢' if north['net_inflow'] > 0 else '🔴'
        report.append(f"- {status_icon} 北向资金：{north['status']}{north['amount']:.2f}亿元")
    
    if events['macro']:
        report.append(f"- 📅 近期宏观事件：{len(events['macro'])}项")
        for e in events['macro'][:3]:
            report.append(f"  - {e['date']}: {e['event']} ({e['importance']})")
    report.append("")
    
    # 持仓详细分析
    report.append("## 📈 持仓详细分析\n")
    
    for a in analyses:
        report.append(f"### {a['name']} ({a['code']})\n")
        
        quote = a['quote']
        report.append(f"**行情**: {quote['price']:.2f}元 ({quote['change_pct']:+.2f}%) | 成交：{quote['volume']/10000:.0f}万手\n")
        
        # 关键位置
        kl = a['key_levels']
        report.append("**关键位置**:")
        if kl['supports']:
            report.append(f"- 支撑：{kl['supports']}")
        if kl['resistances']:
            report.append(f"- 阻力：{kl['resistances']}")
        if kl['alerts']:
            report.append(f"- ⚠️ 预警：{[alert['type'] for alert in kl['alerts']]}")
        report.append("")
        
        # 共振分析
        res = a['resonance']
        report.append("**共振分析**:")
        report.append(f"- 多周期：{res['multi_period']['resonance_type']}")
        report.append(f"- 大盘相关：{res['market_correlation']['analysis']}")
        report.append(f"- 综合评分：{res['total_score']}/{res['max_score']} ({res['rating']})")
        report.append("")
        
        # 资金面
        ff = a['fund_flow']
        report.append("**资金面**:")
        if ff['main_force']:
            report.append(f"- 主力：{ff['main_force']['status']}{ff['main_force']['amount']:.0f}万元")
        report.append(f"- 量比：{ff['volume_ratio']:.2f}")
        report.append("")
        
        # 操作建议
        sugg = a['suggestion']
        report.append(f"**明日策略**: 🎯 {sugg['action']} (置信度：{sugg['confidence']})")
        if sugg['signals']:
            report.append(f"**信号**: {' | '.join(sugg['signals'])}")
        report.append("\n---\n")
    
    # 持仓总结
    report.append("## 📋 持仓总结\n")
    
    # 排名
    sorted_analyses = sorted(analyses, key=lambda x: x['suggestion']['score'], reverse=True)
    
    report.append("**技术面排名**:")
    for i, a in enumerate(sorted_analyses, 1):
        icon = '🟢' if a['suggestion']['score'] >= 60 else '🟡' if a['suggestion']['score'] >= 40 else '🔴'
        report.append(f"{i}. {icon} {a['name']}: {a['suggestion']['score']}分 - {a['suggestion']['action']}")
    report.append("")
    
    # 分类汇总
    buy_list = [a for a in analyses if a['suggestion']['score'] >= 60]
    hold_list = [a for a in analyses if 40 <= a['suggestion']['score'] < 60]
    sell_list = [a for a in analyses if a['suggestion']['score'] < 40]
    
    if buy_list:
        report.append(f"**可加仓** ({len(buy_list)}只): {', '.join([a['name'] for a in buy_list])}")
    if hold_list:
        report.append(f"**持有观望** ({len(hold_list)}只): {', '.join([a['name'] for a in hold_list])}")
    if sell_list:
        report.append(f"**注意风险** ({len(sell_list)}只): {', '.join([a['name'] for a in sell_list])}")
    report.append("")
    
    # 明日策略
    report.append("## 🎯 明日整体策略\n")
    avg_score = sum(a['suggestion']['score'] for a in analyses) / len(analyses) if analyses else 50
    
    if avg_score >= 60:
        report.append(f"🟢 **积极** (平均分{avg_score:.1f}): 可适当加仓，重点关注技术面强势股")
    elif avg_score >= 40:
        report.append(f"🟡 **稳健** (平均分{avg_score:.1f}): 维持现有仓位，高抛低吸")
    else:
        report.append(f"🔴 **防御** (平均分{avg_score:.1f}): 降低仓位，控制风险")
    report.append("")
    
    # 风险提示
    report.append("## ⚠️ 风险提示\n")
    report.append("- 以上分析仅供参考，不构成投资建议")
    report.append("- 请结合自身风险承受能力决策")
    report.append("- 市场有风险，投资需谨慎")
    report.append("\n---")
    report.append("*报告生成时间：" + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + "*")
    
    return '\n'.join(report)


def save_report(content, report_type='午间'):
    """
    保存报告到本地文件
    
    参数：
        content: 报告内容
        report_type: 午间/晚间
    
    返回：
        str: 文件路径
    """
    filepath = get_report_filepath(report_type)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return filepath


if __name__ == '__main__':
    # 测试
    print("生成午间报告...")
    noon_report = generate_noon_report()
    print(noon_report[:500])
    print("\n...\n")
    
    print("生成晚间报告...")
    evening_report = generate_evening_report()
    print(evening_report[:500])
    print("\n...")
