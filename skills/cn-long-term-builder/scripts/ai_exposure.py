#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai_exposure.py — AI叙事风险暴露度评估

核心理念：
  AI催化是双刃剑——上涨时推高估值，下跌时放大跌幅。
  对"互联网科技"行业标的，量化其在全球AI泡沫中的风险暴露程度，
  并给出风险折扣系数。

v1.0: 基于标的代码/名称的静态映射 + ETF成分股加权
"""

import sys
import io
from typing import Dict, Tuple

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
except (ValueError, AttributeError, OSError):
    pass
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace') if hasattr(sys.stderr, 'buffer') else sys.stderr

# ── 个股AI暴露度分类 ──
# 高暴露: AI收入占比 >30%利润，或AI是核心增长叙事且直接依赖AI CAPEX
# 中暴露: AI是增长叙事但非利润主力，或作为AI消费者而非卖铲人
# 低暴露: AI仅为降本工具或辅助，对利润无直接影响
# 无暴露: 业务与AI无关

AI_EXPOSURE_MAP: Dict[str, Dict] = {
    # ── 高暴露 ──
    '09888': {'name': '百度', 'level': 'high', 'discount': 0.85, 'reason': 'AI原生（文心大模型），AI收入占比上升但商业化路径模糊'},
    '00981': {'name': '中芯国际', 'level': 'high', 'discount': 0.85, 'reason': 'AI芯片制造核心环节，但受制程限制'},
    '00020': {'name': '商汤科技', 'level': 'high', 'discount': 0.80, 'reason': '纯AI公司，收入高度依赖AI CAPEX周期'},
    
    # ── 中暴露 ──
    '00700': {'name': '腾讯控股', 'level': 'medium', 'discount': 0.90, 'reason': 'AI云消费者+混元大模型，AI是成本项非收入项'},
    '09988': {'name': '阿里巴巴', 'level': 'medium', 'discount': 0.88, 'reason': '阿里云是中国最大AI训练云，但面临制裁/价格战/政企客户付费弱'},
    '01810': {'name': '小米集团', 'level': 'medium', 'discount': 0.92, 'reason': '端侧AI+智能汽车，AI是产品功能非直接收入'},
    '01024': {'name': '快手', 'level': 'medium', 'discount': 0.92, 'reason': 'AI推荐算法+AIGC，但收入来自广告/电商'},
    '01347': {'name': '华虹半导体', 'level': 'medium', 'discount': 0.90, 'reason': '半导体代工，间接受益AI但产能有限'},
    
    # ── 低暴露 ──
    '03690': {'name': '美团', 'level': 'low', 'discount': 0.95, 'reason': 'AI仅为配送/推荐效率工具，本地生活刚需'},
    '09618': {'name': '京东集团', 'level': 'low', 'discount': 0.97, 'reason': 'AI供应链优化，电商物流是核心'},
    '09999': {'name': '网易', 'level': 'low', 'discount': 0.97, 'reason': 'AI辅助游戏内容，游戏收入为主'},
    '02015': {'name': '理想汽车', 'level': 'low', 'discount': 0.95, 'reason': 'AI自动驾驶，但主要定价在汽车销量'},
    '09866': {'name': '蔚来', 'level': 'low', 'discount': 0.95, 'reason': 'AI自动驾驶，亏损阶段估值不高'},
    '09868': {'name': '小鹏汽车', 'level': 'low', 'discount': 0.95, 'reason': 'AI自动驾驶，亏损阶段估值不高'},
    
    # ── 无暴露（不在映射表中的都视为无暴露） ──
}


# ── ETF成分股AI暴露度（与tsr_calculator共用同一套成分股映射） ──
ETF_AI_HOLDINGS: Dict[str, list] = {
    '513130': [  # 恒生科技ETF
        {'code': '00700', 'weight': 0.10},
        {'code': '09988', 'weight': 0.10},
        {'code': '03690', 'weight': 0.08},
        {'code': '01810', 'weight': 0.08},
        {'code': '09618', 'weight': 0.06},
        {'code': '09999', 'weight': 0.05},
        {'code': '01024', 'weight': 0.05},
        {'code': '09888', 'weight': 0.05},
        {'code': '02015', 'weight': 0.03},
        {'code': '09866', 'weight': 0.02},
        {'code': '09868', 'weight': 0.02},
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


def get_exposure_stock(code: str, name: str, industry: str) -> Dict:
    """
    个股/单标的的AI暴露度检测。
    """
    # 非科技行业的标的
    non_tech_industries = ['银行', '电力', '食品饮料', '白酒', '医药生物', '生猪养殖', '房地产']
    if industry in non_tech_industries:
        return {
            'level': 'none',
            'discount': 1.0,
            'reason': f'{industry}行业与AI无直接关联',
            'affected_constituents': [],
        }
    
    # 查映射表
    ref = AI_EXPOSURE_MAP.get(code)
    if ref:
        return {
            'level': ref['level'],
            'discount': ref['discount'],
            'reason': ref['reason'],
            'affected_constituents': [ref['name']],
        }
    
    # 未知科技标的：默认为中暴露（保守假设）
    return {
        'level': 'medium',
        'discount': 0.92,
        'reason': f'未在映射表中，默认中等暴露（保守假设）',
        'affected_constituents': [],
    }


def get_exposure_etf(code: str) -> Dict:
    """
    ETF的AI暴露度：通过底层成分股加权计算。
    """
    holdings = ETF_AI_HOLDINGS.get(code, [])
    if not holdings:
        return {
            'level': 'unknown',
            'discount': 1.0,
            'reason': '无成分股映射数据，不做风险折扣',
            'affected_constituents': [],
        }
    
    weighted_discount = 0.0
    affected = []
    level_counts = {'high': 0, 'medium': 0, 'low': 0, 'none': 0}
    
    for h in holdings:
        hk_code = h['code']
        w = h['weight']
        ref = AI_EXPOSURE_MAP.get(hk_code, {})
        level = ref.get('level', 'none')
        disc = ref.get('discount', 1.0)
        
        weighted_discount += disc * w
        level_counts[level] = level_counts.get(level, 0) + w
        
        if level in ('high', 'medium'):
            affected.append(f"{ref.get('name', hk_code)}({level})")
    
    # 综合暴露等级
    if level_counts.get('high', 0) > 0.20:
        composite_level = 'high'
        reason = f'高AI暴露成分占比{level_counts["high"]*100:.0f}%，受AI泡沫破裂影响显著'
    elif level_counts.get('high', 0) + level_counts.get('medium', 0) > 0.40:
        composite_level = 'medium'
        reason = f'中高AI暴露成分合计{(level_counts["high"]+level_counts["medium"])*100:.0f}%，存在明显AI叙事风险'
    elif level_counts.get('medium', 0) > 0.20:
        composite_level = 'medium-low'
        reason = f'中等AI暴露成分{level_counts["medium"]*100:.0f}%，AI风险可控'
    else:
        composite_level = 'low'
        reason = f'AI暴露度较低，AI泡沫影响有限'
    
    return {
        'level': composite_level,
        'discount': round(weighted_discount, 4),
        'reason': reason,
        'affected_constituents': affected[:5],  # 最多显示5个
    }


def detect(code: str, name: str, industry: str, is_etf: bool) -> Dict:
    """
    统一入口：检测标的的AI叙事风险暴露度。
    
    参数:
        code: 标的代码
        name: 标的名称
        industry: 行业分类
        is_etf: 是否ETF
    
    返回: {
        'level': 'high'|'medium'|'low'|'none',
        'discount': 风险折扣系数 (0.80-1.00),
        'reason': 说明文本,
        'affected_constituents': 受影响成分股列表,
    }
    """
    if is_etf and code in ETF_AI_HOLDINGS:
        return get_exposure_etf(code)
    else:
        return get_exposure_stock(code, name, industry)


def apply_discount(total_score: float, exposure: Dict, is_tech: bool) -> Tuple[float, str]:
    """
    将AI风险折扣应用到总评分上。
    
    返回: (调整后得分, 调整说明)
    """
    level = exposure.get('level', 'none')
    discount = exposure.get('discount', 1.0)
    
    if level == 'none' or not is_tech:
        return total_score, ''
    
    adjusted = round(total_score * discount)
    delta = adjusted - total_score
    
    if abs(delta) < 1:
        return total_score, ''  # 调整太小，不显示
    
    level_cn = {'high': '🔴 高AI暴露', 'medium': '🟡 中AI暴露', 'medium-low': '🟡 中低AI暴露', 'low': '🟢 低AI暴露'}.get(level, level)
    note = f"{level_cn} ×{discount:.2f} → AI风险折扣 {delta:+.0f}分"
    
    return adjusted, note


if __name__ == '__main__':
    # 测试
    print("=== AI暴露度测试 ===\n")
    
    for code, name, is_etf, ind in [
        ('513130', '恒生科技ETF', True, '互联网科技'),
        ('600036', '招商银行', False, '银行'),
        ('513050', '中概互联网ETF', True, '互联网科技'),
    ]:
        result = detect(code, name, ind, is_etf)
        print(f"{name} ({code}):")
        print(f"  等级: {result['level']}")
        print(f"  折扣: {result['discount']}")
        print(f"  原因: {result['reason']}")
        print(f"  受影响: {result['affected_constituents']}")
        adjusted, note = apply_discount(70, result, ind == '互联网科技')
        if note:
            print(f"  评分调整: {note}")
        print()
