#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tsr_calculator.py — 综合股东回报率（Total Shareholder Return）
股息率 + 净回购收益率 = 真实的股东现金回报

v1.0: 基于静态参考数据 + akshare数据源
覆盖：A股个股、港股ETF（通过底层成分股加权估算）
"""

import sys
import io
from typing import Dict, Optional, Tuple

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
except (ValueError, AttributeError, OSError):
    pass

# ── A股已知回购参考（单位：亿元人民币/年，基于公开公告估算） ──
# 数据来源：公司公告、Wind终端。手动维护，季度更新。
A_SHARE_BUYBACK_REF: Dict[str, Dict] = {
    # 多数A股上市公司回购规模较小，此处仅列出有显著回购的
    # '600036': {'annual_buyback_cny_bn': 0, 'note': '招商银行极少回购，以分红为主'},
    # '600900': {'annual_buyback_cny_bn': 0, 'note': '长江电力以分红为主'},
}

# ── 港股通/跨境ETF底层成分股的回购数据 ──
# 数据来源：公司年报/季报回购披露。手动维护，季度更新。
HK_STOCK_BUYBACK_REF: Dict[str, Dict] = {
    '00700': {  # 腾讯控股
        'name': '腾讯控股',
        'annual_buyback_hkd_bn': 120,
        'annual_dividend_hkd_per_share': 3.40,
        'market_cap_hkd_bn': 4200,   # 约4.2万亿港币
        'shares_outstanding_bn': 9.2,
        'note': '2024-2025年回购超1000亿/年，叠加分红+实物分派'
    },
    '09988': {  # 阿里巴巴
        'name': '阿里巴巴',
        'annual_buyback_hkd_bn': 100,
        'annual_dividend_hkd_per_share': 1.00,
        'market_cap_hkd_bn': 2100,
        'shares_outstanding_bn': 19.5,
        'note': '2024-2025年回购超1200亿港币，首次派发年度股息'
    },
    '03690': {  # 美团
        'name': '美团',
        'annual_buyback_hkd_bn': 30,
        'annual_dividend_hkd_per_share': 0,
        'market_cap_hkd_bn': 800,
        'shares_outstanding_bn': 6.2,
        'note': '2024年启动回购计划，无分红'
    },
    '01810': {  # 小米集团
        'name': '小米集团',
        'annual_buyback_hkd_bn': 10,
        'annual_dividend_hkd_per_share': 0,
        'market_cap_hkd_bn': 600,
        'shares_outstanding_bn': 25,
        'note': '回购规模较小，以汽车/手机CAPEX为主'
    },
    '09618': {  # 京东集团
        'name': '京东集团',
        'annual_buyback_hkd_bn': 25,
        'annual_dividend_hkd_per_share': 0.76,
        'market_cap_hkd_bn': 450,
        'shares_outstanding_bn': 3.1,
        'note': '2024年回购30亿美元'
    },
    '09999': {  # 网易
        'name': '网易',
        'annual_buyback_hkd_bn': 20,
        'annual_dividend_hkd_per_share': 4.00,
        'market_cap_hkd_bn': 500,
        'shares_outstanding_bn': 3.2,
        'note': '稳定分红+回购'
    },
    '01024': {  # 快手
        'name': '快手',
        'annual_buyback_hkd_bn': 8,
        'annual_dividend_hkd_per_share': 0,
        'market_cap_hkd_bn': 250,
        'shares_outstanding_bn': 4.4,
        'note': '2024年开始回购，无分红'
    },
    '09888': {  # 百度
        'name': '百度',
        'annual_buyback_hkd_bn': 15,
        'annual_dividend_hkd_per_share': 0,
        'market_cap_hkd_bn': 300,
        'shares_outstanding_bn': 2.8,
        'note': '回购为主，AI投入限制分红'
    },
    '02015': {  # 理想汽车
        'name': '理想汽车',
        'annual_buyback_hkd_bn': 5,
        'annual_dividend_hkd_per_share': 0,
        'market_cap_hkd_bn': 200,
        'shares_outstanding_bn': 2.1,
        'note': '成长阶段，回购/分红极少'
    },
    '09866': {  # 蔚来
        'name': '蔚来',
        'annual_buyback_hkd_bn': 0,
        'annual_dividend_hkd_per_share': 0,
        'market_cap_hkd_bn': 80,
        'shares_outstanding_bn': 2.0,
        'note': '亏损阶段，无回购分红'
    },
    '09868': {  # 小鹏汽车
        'name': '小鹏汽车',
        'annual_buyback_hkd_bn': 0,
        'annual_dividend_hkd_per_share': 0,
        'market_cap_hkd_bn': 70,
        'shares_outstanding_bn': 1.9,
        'note': '亏损阶段，无回购分红'
    },
}

# ── ETF 底层成分股权重映射 ──
# 权重为近似值，基于2025-2026年指数构成估算
ETF_HOLDINGS: Dict[str, list] = {
    '513130': [  # 恒生科技ETF
        {'code': '00700', 'weight': 0.10},   # 腾讯
        {'code': '09988', 'weight': 0.10},   # 阿里
        {'code': '03690', 'weight': 0.08},   # 美团
        {'code': '01810', 'weight': 0.08},   # 小米
        {'code': '09618', 'weight': 0.06},   # 京东
        {'code': '09999', 'weight': 0.05},   # 网易
        {'code': '01024', 'weight': 0.05},   # 快手
        {'code': '09888', 'weight': 0.05},   # 百度
        {'code': '02015', 'weight': 0.03},   # 理想
        {'code': '09866', 'weight': 0.02},   # 蔚来
        {'code': '09868', 'weight': 0.02},   # 小鹏
    ],
    '513050': [  # 中概互联网ETF
        {'code': '00700', 'weight': 0.12},
        {'code': '09988', 'weight': 0.12},
        {'code': '03690', 'weight': 0.10},
        {'code': '09618', 'weight': 0.08},
        {'code': '09999', 'weight': 0.07},
        {'code': '01024', 'weight': 0.06},
        {'code': '09888', 'weight': 0.06},
    ],
}


def get_tsr_a_share(code: str, price: float, dividend_yield: Optional[float]) -> Dict:
    """
    A股个股的TSR计算。
    回购数据稀疏，以股息率为主，加上已知回购收益率。
    
    返回: {
        'tsr': float,            # 综合股东回报率(%)
        'dividend_yield': float,  # 股息率(%)
        'buyback_yield': float,   # 回购收益率(%)
        'source': str,            # 数据来源说明
        'tsr_rating': str,        # 评级
    }
    """
    div_yield = dividend_yield if dividend_yield is not None else 0.0
    buyback_yield = 0.0
    source_parts = []
    
    if div_yield > 0:
        source_parts.append(f'股息率{div_yield:.1f}%')
    else:
        source_parts.append('股息率数据缺失')
    
    # 查A股回购参考
    ref = A_SHARE_BUYBACK_REF.get(code)
    if ref:
        buyback_yield = ref.get('buyback_yield', 0)
        if buyback_yield > 0:
            source_parts.append(f'回购{buyback_yield:.1f}%')
    
    tsr = div_yield + buyback_yield
    
    # 评级
    if tsr >= 7:
        rating = '极具吸引力'
    elif tsr >= 4:
        rating = '有吸引力'
    elif tsr >= 2:
        rating = '一般'
    else:
        rating = '偏低'
    
    return {
        'tsr': round(tsr, 2),
        'dividend_yield': round(div_yield, 2),
        'buyback_yield': round(buyback_yield, 2),
        'source': ' | '.join(source_parts) if source_parts else '无数据',
        'tsr_rating': rating,
    }


def get_tsr_etf(code: str, price: float) -> Dict:
    """
    跨境ETF的TSR计算：通过底层成分股加权估算。
    """
    holdings = ETF_HOLDINGS.get(code, [])
    if not holdings:
        return {
            'tsr': 0,
            'dividend_yield': 0,
            'buyback_yield': 0,
            'source': '无成分股映射数据',
            'tsr_rating': '无数据',
        }
    
    weighted_div = 0.0
    weighted_buyback = 0.0
    covered_weight = 0.0
    detail_parts = []
    
    for h in holdings:
        hk_code = h['code']
        w = h['weight']
        ref = HK_STOCK_BUYBACK_REF.get(hk_code)
        if ref:
            cap = ref['market_cap_hkd_bn']
            buyback = ref['annual_buyback_hkd_bn']
            shares = ref['shares_outstanding_bn']
            dps = ref['annual_dividend_hkd_per_share']
            
            # 回购收益率 = 回购金额/市值
            by = (buyback / cap * 100) if cap > 0 else 0
            # 股息率 = DPS * 股数 / 市值 = DPS / 股价
            # 股价从市值/股数推算
            stock_price = cap / shares  # 港币
            dy = (dps / stock_price * 100) if stock_price > 0 else 0
            
            weighted_div += dy * w
            weighted_buyback += by * w
            covered_weight += w
            detail_parts.append(f"{ref['name']}: D{dy:.1f}%+B{by:.1f}%")
    
    if covered_weight < 0.5:
        # 覆盖不足50%，加警告
        detail_parts.append(f'⚠️ 覆盖率仅{covered_weight*100:.0f}%')
    
    tsr = round(weighted_div + weighted_buyback, 2)
    div_yield = round(weighted_div, 2)
    buyback_yield = round(weighted_buyback, 2)
    
    if tsr >= 5:
        rating = '极具吸引力（含回购）'
    elif tsr >= 3:
        rating = '有吸引力（含回购）'
    elif tsr >= 1.5:
        rating = '一般'
    else:
        rating = '偏低'
    
    return {
        'tsr': tsr,
        'dividend_yield': div_yield,
        'buyback_yield': buyback_yield,
        'source': f'加权({covered_weight*100:.0f}%覆盖): ' + ' | '.join(detail_parts[:5]),
        'tsr_rating': rating,
    }


def calculate(code: str, name: str, is_etf: bool, price: float, dividend_yield: Optional[float]) -> Dict:
    """
    统一入口：根据标类型计算TSR。
    
    参数:
        code: 标的代码
        name: 标的名称
        is_etf: 是否ETF
        price: 当前价格
        dividend_yield: 已获取的股息率（%），可为None
    
    返回: TSR结果字典
    """
    if is_etf and code in ETF_HOLDINGS:
        return get_tsr_etf(code, price)
    else:
        return get_tsr_a_share(code, price, dividend_yield)


def score_tsr(tsr_result: Dict) -> Tuple[float, str]:
    """
    基于TSR评分（用于替代/增强原有的股息率评分）。
    
    返回: (得分, 描述)
    """
    tsr = tsr_result.get('tsr', 0)
    buyback = tsr_result.get('buyback_yield', 0)
    
    s = 0
    parts = []
    
    # TSR总评分（替代裸股息率评分，上限从5提到8）
    if tsr >= 7:
        s += 8
        parts.append(f"TSR={tsr:.1f}% 极具吸引力 +8")
    elif tsr >= 5:
        s += 6
        parts.append(f"TSR={tsr:.1f}% 有吸引力 +6")
    elif tsr >= 3:
        s += 4
        parts.append(f"TSR={tsr:.1f}% 中等 +4")
    elif tsr >= 1.5:
        s += 2
        parts.append(f"TSR={tsr:.1f}% 偏低 +2")
    else:
        parts.append(f"TSR={tsr:.1f}% 极低 +0")
    
    # 回购占比特别标注
    if buyback >= 3:
        parts.append(f"(回购{buyback:.1f}%占主导)")
    elif buyback >= 1:
        parts.append(f"(含回购{buyback:.1f}%)")
    
    return s, ' | '.join(parts)


if __name__ == '__main__':
    # 测试
    print("=== TSR 测试 ===")
    
    # 513130 恒生科技ETF
    result = calculate('513130', '恒生科技ETF', True, 0.64, None)
    print(f"\n513130 恒生科技ETF:")
    print(f"  TSR: {result['tsr']}%")
    print(f"  股息率: {result['dividend_yield']}%")
    print(f"  回购率: {result['buyback_yield']}%")
    print(f"  来源: {result['source']}")
    print(f"  评级: {result['tsr_rating']}")
    s, d = score_tsr(result)
    print(f"  得分: {s} ({d})")
    
    # 600036 招商银行（A股，无回购数据）
    result2 = calculate('600036', '招商银行', False, 37.90, 5.0)
    print(f"\n600036 招商银行:")
    print(f"  TSR: {result2['tsr']}%")
    print(f"  评级: {result2['tsr_rating']}")
