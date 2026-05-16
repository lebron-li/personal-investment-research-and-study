#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
value_trap_detector.py — 价值陷阱质量过滤器
嵌入 cn-long-term-builder 的前置质量检查模块。
核心理念：低PE/PB不等于便宜——先排除"因为基本面恶化所以便宜"的标的后，再谈估值温度。

覆盖维度：
  1. ROE趋势（银行/周期股必查）        — 判断便宜是否源于盈利能力崩溃
  2. NIM/净息差趋势（银行专用）          — 银行ROE下滑的第一驱动力
  3. 拨备安全性（银行专用）              — 拨备覆盖率是银行"隐藏利润"
  4. 不良认定严格度（银行专用）          — 逾期/不良比 > 150% → 红牌
  5. 盈利质量（非金融股）                — 经营现金流/净利润持续 < 0.5
  6. 分红可靠性                           — 分红中断或下降 → 减分
  7. 商誉风险                             — 商誉/净资产 > 30%

输出：
  quality_coefficient: 0.0-1.0 的质量系数，乘在估值分上
  quality_score: 0-20 的独立质量得分
  findings: 发现的问题列表
  metric_details: 各维度详细数据
"""
import sys, io, json, time
from typing import Dict, List, Tuple, Optional
from datetime import datetime

# Only wrap stdout when run directly, not when imported
if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ── 银行股专用质量规则 ──────────────────────────────────────────
BANK_QUALITY_RULES = {
    'roe_decline': {
        'name': 'ROE趋势',
        'desc': '近3年ROE年化下滑幅度(银行ROE哪怕1pp也很珍贵)',
        'threshold_warn': 1.0,    # 年化下滑>1pp → 警告
        'threshold_red': 2.0,     # 年化下滑>2pp → 红灯
        'coefficient_warn': 0.80,
        'coefficient_red': 0.65,
        'weight': 5,  # 在20分质量分中的权重
    },
    'nim_decline': {
        'name': '净息差趋势',
        'desc': '近4季度NIM累计压缩幅度(bp)',
        'threshold_warn': 10,     # 累计>10bp → 警告
        'threshold_red': 15,      # 累计>15bp → 红灯
        'coefficient_warn': 0.80,
        'coefficient_red': 0.65,
        'weight': 5,
    },
    'provision_safety': {
        'name': '拨备安全性',
        'desc': '拨备覆盖率是否充足且稳定',
        'threshold_warn': 250,    # <250% → 警告
        'threshold_red': 200,     # <200% → 红灯
        'coefficient_warn': 0.85,
        'coefficient_red': 0.75,
        'weight': 4,
    },
    'npl_recognition': {
        'name': '不良认定严格度',
        'desc': '逾期贷款/不良贷款比例',
        'threshold_warn': 130,    # >130% → 警告
        'threshold_red': 150,     # >150% → 红灯
        'coefficient_warn': 0.85,
        'coefficient_red': 0.75,
        'weight': 3,
    },
    'capital_adequacy': {
        'name': '资本充足率',
        'desc': '核心一级资本充足率(CET1)',
        'threshold_warn': 9.0,    # <9% → 警告
        'threshold_red': 8.0,     # <8% → 红灯
        'coefficient_warn': 0.85,
        'coefficient_red': 0.80,
        'weight': 3,
    },
}

# ── 通用质量规则（非银行股）──────────────────────────────────────
GENERAL_QUALITY_RULES = {
    'cash_flow_quality': {
        'name': '盈利质量',
        'desc': '经营现金流/净利润（近2年）',
        'threshold_warn': 0.7,    # <0.7 → 警告
        'threshold_red': 0.5,     # <0.5 → 红灯
        'coefficient_warn': 0.80,
        'coefficient_red': 0.60,
        'weight': 6,
    },
    'dividend_reliability': {
        'name': '分红可靠性',
        'desc': '近3年是否有分红中断或下降',
        'threshold_warn': 1,      # 任一年下降 → 警告
        'threshold_red': 1,       # 中断 → 红灯
        'coefficient_warn': 0.85,
        'coefficient_red': 0.65,
        'weight': 5,
    },
    'goodwill_risk': {
        'name': '商誉风险',
        'desc': '商誉/净资产比例',
        'threshold_warn': 20,     # >20% → 警告
        'threshold_red': 30,      # >30% → 红灯
        'coefficient_warn': 0.85,
        'coefficient_red': 0.70,
        'weight': 5,
    },
    'roe_quality': {
        'name': 'ROE趋势(通用)',
        'desc': '近3年ROE年化下滑幅度',
        'threshold_warn': 3.0,
        'threshold_red': 5.0,
        'coefficient_warn': 0.80,
        'coefficient_red': 0.65,
        'weight': 4,
    },
}

# 银行股代码列表（可扩展）
BANK_CODES = {'600036', '601166', '600000', '601818', '000001', '002142', '601009',
              '601229', '600015', '601169', '601398', '601939', '601288', '601328',
              '600919', '600926', '601838', '601997', '600016', '601128', '601577',
              '002839', '002948', '601860', '601187', '601528', '601658', '601077',
              '600908', '002807', '600928', '601963', '600036', '601166'}


def _is_bank(code: str) -> bool:
    """判断是否为银行股"""
    return code in BANK_CODES


def fetch_bank_quality_data(code: str) -> Dict:
    """
    从东方财富API获取银行质量数据：NIM、NPL、拨备覆盖率、资本充足率、ROE、逾期贷款等。
    返回最近5个报告期的核心指标。
    """
    import requests as req
    result = {
        'success': False,
        'reports': [],
    }
    
    try:
        s = req.Session()
        s.trust_env = False
        
        # 银行股F10财务主要指标API
        url = 'https://datacenter.eastmoney.com/securities/api/data/v1/get'
        params = {
            'reportName': 'RPT_F10_FINANCE_MAINFINADATA',
            'columns': 'REPORT_DATE,ROEJQ,ROEKCJQ,TOTALOPERATEREVETZ,PARENTNETPROFITTZ,'
                       'EPSJB,BPS,ZCFZL,NONPERLOAN,BLDKBBL,NEWCAPITALADER,HXYJBCZL,'
                       'NET_INTEREST_SPREAD,NET_INTEREST_MARGIN,LOAN_PROVISION_RATIO,'
                       'REVENUE_RATIO,NON_PERFORMING_LOAN,OVERDUE_LOANS,'
                       'TOTAL_ASSETS_PK,TOTAL_EQUITY_PK,TOTALOPERATEREVE',
            'filter': f'(SECURITY_CODE="{code}")',
            'pageNumber': 1,
            'pageSize': 10,
            'sortTypes': -1,
            'sortColumns': 'REPORT_DATE',
            'source': 'WEB',
            'client': 'WEB',
        }
        
        r = s.get(url, params=params, timeout=15)
        if r.status_code == 200:
            data = r.json()
            if data.get('success') and data['result'] and data['result']['data']:
                reports = data['result']['data']
                result['success'] = True
                
                # 提取关键指标——处理单位转换和缺失值
                for report in reports:
                    rp = {
                        'report_date': report.get('REPORT_DATE', ''),
                        'roe_weighted': float(report.get('ROEJQ', 0)),
                        'nim': float(report.get('NET_INTEREST_MARGIN', 0)),
                        'nis': float(report.get('NET_INTEREST_SPREAD', 0)),
                        'npl_ratio': float(report.get('NONPERLOAN', 0)),
                        'provision_coverage': float(report.get('BLDKBBL', 0)),
                        'loan_provision_ratio': float(report.get('LOAN_PROVISION_RATIO', 0)),
                        'cet1': float(report.get('HXYJBCZL', 0)),
                        'car': float(report.get('NEWCAPITALADER', 0)),
                        'non_performing_loan': float(report.get('NON_PERFORMING_LOAN', 0)),
                        'overdue_loans': float(report.get('OVERDUE_LOANS', 0)) if report.get('OVERDUE_LOANS') else None,
                        'bps': float(report.get('BPS', 0)),
                        'total_assets': float(report.get('TOTAL_ASSETS_PK', 0)),
                        'total_equity': float(report.get('TOTAL_EQUITY_PK', 0)),
                        'revenue': float(report.get('TOTALOPERATEREVE', 0)),
                        'revenue_ratio': float(report.get('REVENUE_RATIO', 0)),
                        'profit_growth': float(report.get('PARENTNETPROFITTZ', 0)),
                    }
                    result['reports'].append(rp)
    except Exception as e:
        result['error'] = str(e)
    
    return result


def fetch_general_quality_data(code: str) -> Dict:
    """
    获取非银行股的通用质量数据：经营现金流、商誉、分红记录。
    目前使用新浪财务指标 + akshare分红接口。
    """
    import requests as req
    result = {
        'success': False,
        'ocf_ratio': None,         # 经营现金流/净利润
        'goodwill_ratio': None,    # 商誉/净资产
        'dividend_years': [],      # 近3年分红记录
    }
    
    try:
        s = req.Session()
        s.trust_env = False
        
        # 新浪财务指标（利润表+现金流量表摘要）
        url = f'https://money.finance.sina.com.cn/corp/go.php/vFD_FinancialGuideLine/stockid/{code}/ctrl/2025/displaytype/4.phtml'
        r = s.get(url, timeout=10)
        # 新浪返回GBK编码——简易提取
        if r.status_code == 200:
            raw = r.text
            # 简单文本搜索：每股经营性现金流和每股收益
            import re
            ocf_match = re.search(r'每股经营性现金流.*?([\d.-]+)', raw)
            eps_match = re.search(r'摊薄每股收益.*?([\d.-]+)', raw)
            if ocf_match and eps_match:
                try:
                    ocf = float(ocf_match.group(1))
                    eps = float(eps_match.group(1))
                    if eps > 0:
                        result['ocf_ratio'] = round(ocf / eps, 2)
                except:
                    pass
    except:
        pass
    
    # 尝试获取分红数据
    try:
        import akshare as ak
        df = ak.stock_dividents_em(symbol=code)
        if df is not None and len(df) > 0:
            current_yr = datetime.now().year
            for yr in [current_yr-1, current_yr-2, current_yr-3]:
                yr_data = df[df['报告期'].astype(str).str.startswith(str(yr))]
                if len(yr_data) > 0:
                    dps = yr_data['派息'].max() if '派息' in yr_data.columns else 0
                    result['dividend_years'].append({'year': yr, 'dps': float(dps) if dps else 0})
                else:
                    result['dividend_years'].append({'year': yr, 'dps': 0})
            result['success'] = True
    except:
        pass
    
    return result


def assess_bank_quality(quality_data: Dict) -> Dict:
    """
    对银行股进行质量评估，返回：
      quality_coefficient: 质量系数 (0-1)，乘在估值分上
      quality_score: 0-20 的质量得分
      findings: 发现的问题列表
    """
    reports = quality_data.get('reports', [])
    if len(reports) < 3:
        return {
            'quality_coefficient': 1.0,
            'quality_score': 10,
            'findings': ['⚠️ 银行质量数据不足（<3个报告期），无法评估质量'],
            'metric_details': {},
            'data_source': '未获取到足够数据',
        }
    
    # 分离年报（兼容 "2025-12-31 00:00:00" 格式）
    annuals = [r for r in reports if '-12-31' in r['report_date']]
    
    findings = []
    bonuses = []
    rule_results = {}
    total_weight = 0
    weighted_coeff = 0.0
    quality_score = 20  # 满分从20开始扣
    
    # ── 1. ROE趋势 ──
    rule = BANK_QUALITY_RULES['roe_decline']
    total_weight += rule['weight']
    if len(annuals) >= 3:
        # annuals 是降序（最新在前），取最近3年，反转为升序
        roes_raw = [r['roe_weighted'] for r in annuals[:3]]
        dates_raw = [r['report_date'] for r in annuals[:3]]
        roes = list(reversed(roes_raw))  # [最旧, ..., 最新]
        dates = list(reversed(dates_raw))
        # 提取年份
        import re as _re
        yrs = [int(_re.search(r'20\d{2}', d).group()) for d in dates if _re.search(r'20\d{2}', d)]
        # 年化下滑：负值 = 恶化
        annual_decline = (roes[-1] - roes[0]) / (len(roes) - 1)
        yr_label = f"FY{yrs[0]}→FY{yrs[-1]}" if len(yrs) >= 2 else ""
        rule_results['roe_decline'] = {
            'value': round(annual_decline, 2),
            'detail': f"ROE: {roes[0]:.1f}%({yr_label})→{roes[-1]:.1f}% (年化{'下滑' if annual_decline<0 else '上升'}{abs(annual_decline):.1f}pp)",
            'roes': roes,
        }
        if annual_decline < -rule['threshold_red']:
            coeff = rule['coefficient_red']
            deduction = 3
            findings.append(f"🔴 ROE年化下滑{abs(annual_decline):.1f}pp（>3pp阈值），盈利能力持续恶化")
            quality_score -= deduction
        elif annual_decline < -rule['threshold_warn']:
            coeff = rule['coefficient_warn']
            deduction = 1.5
            findings.append(f"🟡 ROE年化下滑{abs(annual_decline):.1f}pp（>2pp阈值），需关注")
            quality_score -= deduction
        else:
            coeff = 1.0
            bonuses.append(f"✅ ROE趋势健康（年化变化{annual_decline:+.1f}pp）")
        weighted_coeff += coeff * rule['weight']
    else:
        weighted_coeff += 1.0 * rule['weight']
        rule_results['roe_decline'] = {'value': None, 'detail': '年报不足3年，无法评估'}
    
    # ── 2. NIM趋势 ──
    rule = BANK_QUALITY_RULES['nim_decline']
    total_weight += rule['weight']
    if len(reports) >= 4:
        # 取最近4个季度（年报+一季报+中报+三季报混合）看趋势
        recent_n = reports[:8]  # 取足8个报告期（约2年），取最早和最晚做对比
        nims = [(r['report_date'], r['nim']) for r in recent_n if r['nim'] > 0]
        if len(nims) >= 3:
            # 取最新（列表头）和最旧（列表尾）的NIM值
            nim_latest = nims[0][1]
            nim_earliest = nims[-1][1]
            nim_cumulative_bp = (nim_latest - nim_earliest) * 100  # 负值=压缩
            # 如果当前NIM绝对水平仍>1.85%，压缩的严重程度打折
            nim_is_high = nim_latest > 1.80  # NIM>1.80%说明绝对利差水平尚可
            adj_threshold_red = rule['threshold_red'] + (5 if nim_is_high else 0)  # NIM高→放宽5bp
            adj_threshold_warn = rule['threshold_warn'] + (5 if nim_is_high else 0)
            
            rule_results['nim_decline'] = {
                'value': round(nim_cumulative_bp, 1),
                'detail': f"NIM: {nim_earliest:.2f}%→{nim_latest:.2f}% (累计变化{nim_cumulative_bp:+.0f}bp)",
                'nim_series': [(n[0], n[1]) for n in nims],
            }
            if nim_cumulative_bp < -adj_threshold_red:
                coeff = rule['coefficient_red']
                deduction = 3
                findings.append(f"🔴 NIM累计压缩{abs(nim_cumulative_bp):.0f}bp（>{adj_threshold_red}bp阈值），利差恶化严重")
                quality_score -= deduction
            elif nim_cumulative_bp < -adj_threshold_warn:
                coeff = rule['coefficient_warn']
                deduction = 1.5
                findings.append(f"🟡 NIM压缩{abs(nim_cumulative_bp):.0f}bp（>{adj_threshold_warn}bp阈值），利差持续承压")
                quality_score -= deduction
            elif nim_cumulative_bp >= 0:
                coeff = 1.0
                bonuses.append(f"✅ NIM逆势回升（累计变化{nim_cumulative_bp:+.0f}bp）")
            else:
                coeff = 1.0
                bonuses.append(f"✅ NIM轻微压缩但绝对水平较高（{nim_latest:.2f}%，变化{nim_cumulative_bp:+.0f}bp）")
            weighted_coeff += coeff * rule['weight']
        else:
            weighted_coeff += 1.0 * rule['weight']
            rule_results['nim_decline'] = {'value': None, 'detail': 'NIM数据不足'}
    else:
        weighted_coeff += 1.0 * rule['weight']
        rule_results['nim_decline'] = {'value': None, 'detail': '报告期不足4个'}
    
    # ── 3. 拨备安全性 ──
    rule = BANK_QUALITY_RULES['provision_safety']
    total_weight += rule['weight']
    if reports:
        latest = reports[0]
        pc = latest.get('provision_coverage', 0)
        rule_results['provision_safety'] = {
            'value': pc,
            'detail': f"拨备覆盖率: {pc:.0f}%",
            'coverage_history': [r['provision_coverage'] for r in reports[:5] if r['provision_coverage'] > 0],
        }
        if pc < rule['threshold_red']:
            coeff = rule['coefficient_red']
            deduction = 2
            findings.append(f"🔴 拨备覆盖率{pc:.0f}%（<200%），安全垫薄弱")
            quality_score -= deduction
        elif pc < rule['threshold_warn']:
            coeff = rule['coefficient_warn']
            deduction = 1
            findings.append(f"🟡 拨备覆盖率{pc:.0f}%（<250%），安全垫偏薄")
            quality_score -= deduction
        else:
            coeff = 1.0
            bonuses.append(f"✅ 拨备覆盖率{pc:.0f}%，安全垫充足")
        weighted_coeff += coeff * rule['weight']
    else:
        weighted_coeff += 1.0 * rule['weight']
    
    # ── 4. 不良认定严格度 ──
    rule = BANK_QUALITY_RULES['npl_recognition']
    total_weight += rule['weight']
    if reports:
        # overdue_loans 可能在最近报告期缺失，遍历找最近的
        overdue = None
        for r in reports:
            if r.get('overdue_loans') and r['overdue_loans'] > 0:
                overdue = r['overdue_loans']
                break
        npl = reports[0].get('non_performing_loan', 0)
        if overdue and npl > 0:
            overdue_ratio = overdue / npl * 100
            rule_results['npl_recognition'] = {
                'value': round(overdue_ratio, 1),
                'detail': f"逾期/不良: {overdue_ratio:.0f}% (逾期{overdue/1e8:.0f}亿/不良{npl/1e8:.0f}亿)",
            }
            if overdue_ratio > rule['threshold_red']:
                coeff = rule['coefficient_red']
                deduction = 2
                findings.append(f"🔴 逾期/不良={overdue_ratio:.0f}%（>150%），不良认定可能偏松")
                quality_score -= deduction
            elif overdue_ratio > rule['threshold_warn']:
                coeff = rule['coefficient_warn']
                deduction = 1
                findings.append(f"🟡 逾期/不良={overdue_ratio:.0f}%（>130%），需关注")
                quality_score -= deduction
            else:
                coeff = 1.0
            weighted_coeff += coeff * rule['weight']
        else:
            weighted_coeff += 1.0 * rule['weight']
            rule_results['npl_recognition'] = {'value': None, 'detail': '逾期贷款数据缺失'}
    else:
        weighted_coeff += 1.0 * rule['weight']
    
    # ── 5. 资本充足率 ──
    rule = BANK_QUALITY_RULES['capital_adequacy']
    total_weight += rule['weight']
    if reports:
        latest = reports[0]
        cet1 = latest.get('cet1', 0)
        rule_results['capital_adequacy'] = {
            'value': cet1,
            'detail': f"CET1: {cet1:.2f}%",
        }
        if cet1 < rule['threshold_red']:
            coeff = rule['coefficient_red']
            findings.append(f"🔴 CET1仅{cet1:.2f}%（<8%），资本承压")
            quality_score -= 1.5
        elif cet1 < rule['threshold_warn']:
            coeff = rule['coefficient_warn']
            findings.append(f"🟡 CET1={cet1:.2f}%（<9%），资本偏紧")
            quality_score -= 0.5
        else:
            coeff = 1.0
            bonuses.append(f"✅ CET1={cet1:.2f}%，资本充足")
        weighted_coeff += coeff * rule['weight']
    else:
        weighted_coeff += 1.0 * rule['weight']
    
    # ── 综合计算 ──
    quality_coefficient = weighted_coeff / total_weight if total_weight > 0 else 1.0
    quality_score = max(0, min(20, quality_score))
    
    return {
        'quality_coefficient': round(quality_coefficient, 3),
        'quality_score': round(quality_score, 1),
        'findings': findings,
        'bonuses': bonuses,
        'metric_details': {
            'roe': rule_results.get('roe_decline', {}),
            'nim': rule_results.get('nim_decline', {}),
            'provision': rule_results.get('provision_safety', {}),
            'npl_recognition': rule_results.get('npl_recognition', {}),
            'capital': rule_results.get('capital_adequacy', {}),
        },
        'data_source': '东方财富F10 API',
    }


def assess_general_quality(quality_data: Dict, industry: str) -> Dict:
    """
    对非银行股进行通用质量评估。
    当前实现较简单——大部分数据需要 akshare 支持。
    若数据不足，返回中性系数。
    """
    findings = []
    bonuses = []
    quality_score = 20
    total_weight = 0
    weighted_coeff = 0.0
    
    # ── 盈利质量（经营现金流/净利润）──
    rule = GENERAL_QUALITY_RULES['cash_flow_quality']
    total_weight += rule['weight']
    ocf = quality_data.get('ocf_ratio')
    if ocf is not None:
        if ocf < rule['threshold_red']:
            coeff = rule['coefficient_red']
            findings.append(f"🔴 经营现金流/净利润={ocf:.1f}（<0.5），盈利质量差")
            quality_score -= 3
        elif ocf < rule['threshold_warn']:
            coeff = rule['coefficient_warn']
            findings.append(f"🟡 经营现金流/净利润={ocf:.1f}（<0.7），需关注")
            quality_score -= 1.5
        else:
            coeff = 1.0
            bonuses.append(f"✅ 经营现金流/净利润={ocf:.1f}，盈利质量好")
        weighted_coeff += coeff * rule['weight']
    else:
        weighted_coeff += 1.0 * rule['weight']
    
    # ── 分红可靠性 ──
    rule = GENERAL_QUALITY_RULES['dividend_reliability']
    total_weight += rule['weight']
    div_years = quality_data.get('dividend_years', [])
    if div_years:
        non_zero = [d for d in div_years if d['dps'] > 0]
        if len(non_zero) < len(div_years):
            coeff = rule['coefficient_red']
            findings.append("🔴 近3年存在分红中断")
            quality_score -= 3
        elif len(non_zero) >= 2:
            # 检查是否下降
            dps_values = [d['dps'] for d in non_zero]
            if len(dps_values) >= 2 and dps_values[-1] < dps_values[0] * 0.9:
                coeff = rule['coefficient_warn']
                findings.append("🟡 近3年分红下降>10%")
                quality_score -= 1.5
            else:
                coeff = 1.0
                bonuses.append("✅ 分红记录稳定")
        else:
            coeff = 1.0
        weighted_coeff += coeff * rule['weight']
    else:
        weighted_coeff += 1.0 * rule['weight']
    
    # ── 商誉风险 ──
    rule = GENERAL_QUALITY_RULES['goodwill_risk']
    total_weight += rule['weight']
    goodwill = quality_data.get('goodwill_ratio')
    if goodwill is not None:
        if goodwill > rule['threshold_red']:
            coeff = rule['coefficient_red']
            findings.append(f"🔴 商誉/净资产={goodwill:.0f}%（>30%），商誉暴雷风险高")
            quality_score -= 3
        elif goodwill > rule['threshold_warn']:
            coeff = rule['coefficient_warn']
            findings.append(f"🟡 商誉/净资产={goodwill:.0f}%（>20%），需关注")
            quality_score -= 1.5
        else:
            coeff = 1.0
        weighted_coeff += coeff * rule['weight']
    else:
        weighted_coeff += 1.0 * rule['weight']  # 数据缺失不扣分（银行/ETF大部分无商誉）
    
    # ── ROE趋势(通用) ──
    rule = GENERAL_QUALITY_RULES['roe_quality']
    total_weight += rule['weight']
    # 如果没有ROE数据，给中性分
    weighted_coeff += 1.0 * rule['weight']
    
    quality_coefficient = weighted_coeff / total_weight if total_weight > 0 else 1.0
    quality_score = max(0, min(20, quality_score))
    
    return {
        'quality_coefficient': round(quality_coefficient, 3),
        'quality_score': round(quality_score, 1),
        'findings': findings,
        'bonuses': bonuses,
        'metric_details': quality_data,
        'data_source': '新浪财务指标 / akshare分红',
    }


def detect(code: str, name: str, industry: str) -> Dict:
    """
    主入口：对任意标的进行价值陷阱检测。
    
    参数:
      code: 股票代码
      name: 股票名称
      industry: 所属行业
    
    返回:
      {
        'quality_coefficient': float,   # 0-1，乘在估值分上
        'quality_score': float,         # 0-20，质量得分（新维度）
        'findings': [str],              # 发现的问题
        'bonuses': [str],               # 质量亮点
        'metric_details': dict,         # 各维度详细数据
        'is_bank': bool,                # 是否为银行股
      }
    """
    is_bank = _is_bank(code)
    
    if is_bank:
        quality_data = fetch_bank_quality_data(code)
        if not quality_data['success']:
            return {
                'quality_coefficient': 1.0,
                'quality_score': 10,
                'findings': ['⚠️ 银行质量数据获取失败，使用默认系数1.0'],
                'bonuses': [],
                'metric_details': {},
                'is_bank': True,
            }
        result = assess_bank_quality(quality_data)
        result['is_bank'] = True
        return result
    else:
        quality_data = fetch_general_quality_data(code)
        result = assess_general_quality(quality_data, industry)
        result['is_bank'] = False
        return result


if __name__ == '__main__':
    # 测试：对兴业银行和招商银行分别评估
    for code, name in [('601166', '兴业银行'), ('600036', '招商银行')]:
        print(f"\n{'='*60}")
        print(f" {name} ({code}) 价值陷阱检测")
        print(f"{'='*60}")
        result = detect(code, name, '银行')
        print(f"  质量系数: {result['quality_coefficient']}")
        print(f"  质量得分: {result['quality_score']}/20")
        if result['findings']:
            for f in result['findings']:
                print(f"  {f}")
        if result['bonuses']:
            for b in result['bonuses']:
                print(f"  {b}")
        print(f"  指标详情: {json.dumps(result['metric_details'], ensure_ascii=False, indent=2)}")
