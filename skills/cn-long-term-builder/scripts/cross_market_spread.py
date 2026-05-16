#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cross_market_spread.py — 跨市场估值比价模块

对于港股/跨境ETF标的，横向比较 vs 纳斯达克100、韩国KOSDAQ等全球科技指数，
提供"极端比价效应"的量化锚点。

v1.0: 基于静态参考数据 + 可选web抓取（夜间可能不可用）
"""

import sys
import io
from typing import Dict, Optional, Tuple

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
except (ValueError, AttributeError, OSError):
    pass

# ── 全球科技指数静态估值参考（手动维护，月度更新） ──
# PE数据来源：Bloomberg/Wind终端
GLOBAL_TECH_VALUATION: Dict[str, Dict] = {
    'NASDAQ100': {
        'name': '纳斯达克100',
        'pe': 30.5,
        'pe_5y_avg': 27.0,
        'pe_5y_high': 38.0,
        'pe_5y_low': 20.0,
        'pb': 8.5,
        'note': 'AI泡沫推高估值，隐含AI CAPEX高增长预期',
    },
    'KOSDAQ': {
        'name': '韩国KOSDAQ',
        'pe': 25.0,
        'pe_5y_avg': 22.0,
        'note': 'SK Hynix等半导体权重高，AI硬件周期驱动',
    },
    'HSTECH': {
        'name': '恒生科技',
        'pe': 15.2,
        'pe_5y_avg': 35.0,
        'pe_5y_high': 60.0,
        'pe_5y_low': 10.0,
        'pb': 1.8,
        'note': '消费互联网为主，AI暴露度中等',
    },
    'CSI_300': {
        'name': '沪深300',
        'pe': 12.0,
        'pe_5y_avg': 13.5,
        'note': '大金融/消费为主，科技权重低',
    },
}

# ── ETF与对应全球基准指数的映射 ──
ETF_BENCHMARK_MAP: Dict[str, list] = {
    '513130': ['NASDAQ100', 'KOSDAQ'],  # 恒生科技 vs 全球科技
    '513050': ['NASDAQ100'],             # 中概互联 vs 纳斯达克
}


def get_global_pe(index_key: str) -> Optional[Dict]:
    """
    获取全球基准指数的估值数据。
    优先尝试实时抓取（web），失败则使用静态参考。
    """
    ref = GLOBAL_TECH_VALUATION.get(index_key)
    if not ref:
        return None
    
    # 尝试实时获取（占位：后续可接入aiohttp抓取ETF.com/Yahoo Finance）
    # 当前使用静态参考
    return ref


def calc_spread(local_pe: Optional[float], benchmark_indexes: list) -> Dict:
    """
    计算本地标的 vs 全球基准的估值价差。
    
    参数:
        local_pe: 本地标的PE（可为None，则用静态参考）
        benchmark_indexes: 要对比的全球指数列表
    
    返回: {
        'spreads': {index_key: (本地PE, 基准PE, 折溢价%)},
        'summary': 总结文本,
        'signal': 'bullish'|'neutral'|'bearish',
    }
    """
    spreads = {}
    local = local_pe
    
    # 如果没有本地PE，用HSTECH静态参考
    if local is None:
        hstech_ref = GLOBAL_TECH_VALUATION.get('HSTECH', {})
        local = hstech_ref.get('pe')
    
    if local is None:
        return {'spreads': {}, 'summary': '估值数据不足，无法进行跨市场比价', 'signal': 'neutral'}
    
    for idx_key in benchmark_indexes:
        bench = get_global_pe(idx_key)
        if bench and bench.get('pe'):
            bench_pe = bench['pe']
            diff_pct = round((local - bench_pe) / bench_pe * 100, 1)
            spreads[idx_key] = {
                'local_pe': local,
                'bench_pe': bench_pe,
                'bench_name': bench['name'],
                'diff_pct': diff_pct,
            }
    
    if not spreads:
        return {'spreads': {}, 'summary': '无法获取全球基准指数估值数据', 'signal': 'neutral'}
    
    # 生成总结
    parts = []
    signal_score = 0
    
    for idx_key, s in spreads.items():
        diff = s['diff_pct']
        if diff < -30:
            parts.append(f"vs {s['bench_name']} (PE {s['bench_pe']:.1f}x): 折价 {abs(diff):.0f}% 🟢 显著低估")
            signal_score += 2
        elif diff < -15:
            parts.append(f"vs {s['bench_name']} (PE {s['bench_pe']:.1f}x): 折价 {abs(diff):.0f}% 🟡 偏低")
            signal_score += 1
        elif diff < 0:
            parts.append(f"vs {s['bench_name']} (PE {s['bench_pe']:.1f}x): 折价 {abs(diff):.0f}%")
        else:
            parts.append(f"vs {s['bench_name']} (PE {s['bench_pe']:.1f}x): 溢价 +{diff:.0f}%")
    
    if signal_score >= 3:
        signal = 'bullish'
        summary = '跨市场估值优势显著，极端比价效应有利于国际资金轮动'
    elif signal_score >= 1:
        signal = 'neutral'
        summary = '有一定估值优势，但幅度不够极端'
    else:
        signal = 'bearish'
        summary = '相对全球基准无明显估值优势'
    
    parts.append(f'→ {summary}')
    
    return {
        'spreads': spreads,
        'summary': '\n  '.join(parts),
        'signal': signal,
    }


def should_show_cross_market(code: str, is_etf: bool, industry: str) -> bool:
    """
    判断是否需要在报告中显示跨市场比价。
    仅对港股/跨境科技ETF显示。
    """
    if code in ETF_BENCHMARK_MAP:
        return True
    if industry == '互联网科技':
        return True
    return False


def get_comparison(code: str, is_etf: bool, industry: str, local_pe: Optional[float]) -> Optional[Dict]:
    """
    统一入口。
    
    返回: 比价结果dict，或None（不需要显示）
    """
    if not should_show_cross_market(code, is_etf, industry):
        return None
    
    benchmarks = ETF_BENCHMARK_MAP.get(code, ['NASDAQ100'])
    return calc_spread(local_pe, benchmarks)


def format_cross_market(result: Optional[Dict]) -> str:
    """
    格式化跨市场比价为报告行。
    """
    if not result or not result.get('spreads'):
        return ''
    
    return f"  \u2192 {result['summary']}"


if __name__ == '__main__':
    # 测试
    print("=== 跨市场比价测试 ===\n")
    
    for code, is_etf, ind, pe in [
        ('513130', True, '互联网科技', None),
        ('600036', False, '银行', 6.3),
    ]:
        result = get_comparison(code, is_etf, ind, pe)
        print(f"{code} ({ind}):")
        if result:
            print(f"  {result['summary']}")
            print(f"  信号: {result['signal']}")
        else:
            print(f"  不适用跨市场比价")
        print()
