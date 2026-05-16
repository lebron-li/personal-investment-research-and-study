#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cn-long-term-builder — A 股长期建仓助手
长期主义投资者专用：以年为单位 + 日线/周线校准入场时机
评分逻辑：估值低+跌够了 = 高分（与短期交易逻辑完全相反）
"""
import sys, io, re, time, json
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
except (ValueError, AttributeError, OSError):
    pass

import os

PORTFOLIO_FILE = r"<YOUR_PORTFOLIO_FILE_PATH>"
MAX_RETRIES, RETRY_DELAY = 3, 3

# 行业周期位置
INDUSTRY_CYCLE = {
    '银行': {'phase': '底部企稳', 'note': '净息差触底，不良率可控', 'score': 80},
    '电力': {'phase': '成熟稳定', 'note': '零碳基荷能源，现金流永续', 'score': 85},
    '白酒': {'phase': '调整末期', 'note': '库存去化，估值回归', 'score': 65},
    '食品饮料': {'phase': '调整中', 'note': '消费降级压力', 'score': 55},
    '医药生物': {'phase': '筑底阶段', 'note': '集采尾声，创新出海兑现', 'score': 60},
    '生猪养殖': {'phase': '周期底部', 'note': '猪价低位，产能去化中', 'score': 55},
    '房地产': {'phase': '下行出清', 'note': '仅头部国企可关注', 'score': 30},
    '互联网科技': {'phase': '反弹中', 'note': '港股估值洼地+AI催化，波动极大', 'score': 60},
}

# ── 导入扩展模块 ──
def _import_module(mod_name):
    """安全导入同一目录下的模块"""
    script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in dir() else '.'
    spec = importlib.util.spec_from_file_location(mod_name, os.path.join(script_dir, f'{mod_name}.py'))
    if spec is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

import importlib.util

# v2.0: 价值陷阱检测
_vt_module = _import_module('value_trap_detector')
if _vt_module:
    value_trap_detect = _vt_module.detect
else:
    def value_trap_detect(code, name, industry):
        return {'quality_coefficient': 1.0, 'quality_score': 10, 'findings': ['⚠️ 质量模块未加载'], 'bonuses': [], 'metric_details': {}, 'is_bank': False}

# v2.3: TSR综合股东回报率
_tsr_module = _import_module('tsr_calculator')
tsr_calculate = _tsr_module.calculate if _tsr_module else lambda c,n,e,p,d: {'tsr': d or 0, 'dividend_yield': d or 0, 'buyback_yield': 0, 'source': '模块未加载', 'tsr_rating': '无数据'}
tsr_score = _tsr_module.score_tsr if _tsr_module else lambda r: (0, '模块未加载')

# v2.3: AI叙事风险暴露度
_ai_module = _import_module('ai_exposure')
ai_detect = _ai_module.detect if _ai_module else lambda c,n,i,e: {'level': 'none', 'discount': 1.0, 'reason': '模块未加载', 'affected_constituents': []}
ai_apply = _ai_module.apply_discount if _ai_module else lambda s,e,t: (s, '')

# v2.3: 跨市场估值比价
_cm_module = _import_module('cross_market_spread')
cm_get = _cm_module.get_comparison if _cm_module else lambda c,e,i,p: None
cm_fmt = _cm_module.format_cross_market if _cm_module else lambda r: ''

def parse_portfolio(filepath: str) -> List[Dict]:
    holdings = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line: continue
                code_match = re.search(r'(\d{6})', line)
                if code_match:
                    code = code_match.group(1)
                    # Extract name: strip leading number+punctuation, get text before code
                    clean = re.sub(r'^\d+[、.,，。\s]+', '', line)
                    name_part = clean.replace(code, '').strip()
                    name = name_part if name_part else code
                    is_etf = code.startswith('5') or code.startswith('1')
                    holdings.append({'name': name, 'code': code, 'is_etf': is_etf})
    except Exception as e:
        print(f"读取失败：{e}", file=sys.stderr)
    return holdings

def fetch_kline(code: str, is_etf: bool, period: str = 'daily') -> Optional[pd.DataFrame]:
    """获取K线：新浪优先（全天可用），东方财富兜底"""
    import requests as req
    mkt = 'sh' if (code.startswith('6') or code.startswith('5')) else 'sz'
    
    if period == 'daily':
        # 新浪（主数据源）— 尝试获取更多历史数据
        for datalen in [200, 100]:
            try:
                s = req.Session(); s.trust_env = False
                r = s.get(f'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={mkt}{code}&scale=240&ma=no&datalen={datalen}', timeout=10)
                if r.status_code == 200 and len(r.text) > 100:
                    raw = r.json()
                    if raw and len(raw) >= 20:
                        records = [{'date':i['day'],'open':float(i['open']),'close':float(i['close']),'high':float(i['high']),'low':float(i['low']),'volume':float(i['volume'])} for i in raw]
                        return pd.DataFrame(records)
            except: pass
        
        # 东方财富兜底
        try:
            s = req.Session(); s.trust_env = False
            mid = '1' if (code.startswith('6') or code.startswith('5')) else '0'
            r = s.get('https://push2his.eastmoney.com/api/qt/stock/kline/get', params={
                'fields1':'f1,f2,f3,f4,f5,f6',
                'fields2':'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116',
                'ut':'7eea3edcaed734bea9cbfc24409ed989',
                'klt':'101', 'fqt':'1', 'secid':f'{mid}.{code}',
                'beg':(datetime.now()-timedelta(days=365)).strftime('%Y%m%d'),
                'end':datetime.now().strftime('%Y%m%d')
            }, timeout=8)
            if r.status_code == 200:
                d = r.json()
                if d.get('data') and d['data'].get('klines'):
                    records = []
                    for k in d['data']['klines']:
                        p = k.split(',')
                        if len(p) >= 6: records.append({'date':p[0],'open':float(p[1]),'close':float(p[2]),'high':float(p[3]),'low':float(p[4]),'volume':float(p[5])})
                    if len(records) >= 20: return pd.DataFrame(records)
        except: pass
        return None
    
    # 周线：从日线聚合
    if period == 'weekly':
        daily = fetch_kline(code, is_etf, 'daily')
        if daily is not None and len(daily) >= 100:
            try:
                daily['date'] = pd.to_datetime(daily['date'])
                daily = daily.sort_values('date')
                weekly = daily.set_index('date').resample('W').agg({
                    'open': 'first', 'close': 'last',
                    'high': 'max', 'low': 'min', 'volume': 'sum'
                }).dropna()
                if len(weekly) >= 20:
                    weekly = weekly.reset_index()
                    weekly['date'] = weekly['date'].dt.strftime('%Y-%m-%d')
                    return weekly
            except: pass
        return None

def calc_ta(df: pd.DataFrame) -> Dict:
    if len(df) < 20: return {}
    c, h, l, v = df['close'].astype(float), df['high'].astype(float), df['low'].astype(float), df['volume'].astype(float)
    latest = c.iloc[-1]
    ma5, ma10, ma20 = c.rolling(5).mean().iloc[-1], c.rolling(10).mean().iloc[-1], c.rolling(20).mean().iloc[-1]
    ma60 = c.rolling(60).mean().iloc[-1] if len(c) >= 60 else ma20
    h52, l52 = h.max(), l.min()
    dd = (latest - h52) / h52 * 100
    dl = (latest - l52) / l52 * 100
    e12, e26 = c.ewm(span=12,adjust=False).mean(), c.ewm(span=26,adjust=False).mean()
    dif, dea = e12-e26, (e12-e26).ewm(span=9,adjust=False).mean()
    mh = 2*(dif-dea)
    div = False
    if len(c) >= 60:
        div = (c.iloc[-1] <= c.iloc[-60:].min()*1.02) and (dif.iloc[-1] > dif.iloc[-60:].min())
    delta = c.diff(); gain = delta.where(delta>0,0).rolling(14).mean(); loss = (-delta.where(delta<0,0)).rolling(14).mean()
    rs = gain/loss; rsi = (100-100/(1+rs)).iloc[-1]
    l9,h9 = l.rolling(9).min(), h.rolling(9).max()
    rsv = (c-l9)/(h9-l9)*100; k_val = rsv.ewm(com=2,adjust=False).mean(); d_val = k_val.ewm(com=2,adjust=False).mean()
    bm = ma20; bs = c.rolling(20).std().iloc[-1]
    bu = bm + 2*bs; bd = bm - 2*bs
    bp = (latest-bd)/(bu-bd)*100 if bu!=bd else 50
    pdm = h.diff().clip(lower=0); mdm = (-l.diff()).clip(lower=0)
    pdm[pdm>0] = np.where((pdm>mdm)&(pdm>0), pdm, 0)
    mdm[mdm>0] = np.where((mdm>pdm)&(mdm>0), mdm, 0)
    tr = pd.concat([h-l,(h-c.shift(1)).abs(),(l-c.shift(1)).abs()],axis=1).max(axis=1)
    atr = tr.rolling(14).mean(); pdi = pdm.rolling(14).mean()/atr.replace(0, np.nan)*100; mdi = mdm.rolling(14).mean()/atr.replace(0, np.nan)*100
    pdi, mdi = pdi.fillna(0), mdi.fillna(0)
    denom = pdi + mdi
    dx = pd.Series(np.where(denom > 0, (abs(pdi-mdi)/denom*100).values, 0), index=denom.index)
    adx = dx.rolling(14).mean().iloc[-1]
    if pd.isna(adx) or np.isinf(adx): adx = 25.0  # default if not computable
    obv = (np.sign(c.diff())*v).fillna(0).cumsum()
    obv_up = (obv.iloc[-1] > obv.iloc[-20:].mean()) if len(obv)>=20 else False
    # Ensure all scalars
    return {'price':latest,'ma5':float(ma5),'ma10':float(ma10),'ma20':float(ma20),'ma60':float(ma60),
            'high_52w':float(h52),'low_52w':float(l52),'drawdown':float(dd),'dist_low':float(dl),
            'macd_dif':float(dif.iloc[-1]),'macd_dea':float(dea.iloc[-1]),'macd_hist':float(mh.iloc[-1]),
            'macd_divergence':div,'rsi':float(rsi),'kd_k':float(k_val.iloc[-1]),'kd_d':float(d_val.iloc[-1]),
            'boll_upper':float(bu),'boll_mid':float(bm),'boll_lower':float(bd),'boll_pos':float(bp),
            'adx':float(adx),'di_plus':float(pdi.iloc[-1]),'di_minus':float(mdi.iloc[-1]),'obv_up':obv_up,'atr':float(atr.iloc[-1])}

def get_valuation_from_sina(code: str, price: float) -> Dict:
    """从东方财富轻量获取PE/PB（夜间可能不可用）"""
    import requests as req
    result = {'pe':None,'pb':None}
    try:
        s = req.Session(); s.trust_env = False
        mid = '1' if code.startswith('6') else '0'
        r = s.get(f'https://push2.eastmoney.com/api/qt/stock/get?secid={mid}.{code}&fields=f43,f162,f167,f170,f171', timeout=8)
        if r.status_code == 200:
            d = r.json().get('data', {})
            if d:
                if d.get('f162') and float(d['f162']) > 0: result['pe'] = round(float(d['f162']), 2)
                if d.get('f167') and float(d['f167']) > 0: result['pb'] = round(float(d['f167']), 2)
    except:
        pass
    return result

def get_valuation_baidu(code: str) -> Dict:
    """从百度估值接口获取PE/PB及历史分位（独立于东方财富）"""
    result = {'pe':None,'pb':None,'pe_pct':None,'pb_pct':None}
    try:
        import akshare as ak
        # PE TTM 近五年
        df_pe = ak.stock_zh_valuation_baidu(symbol=code, indicator='市盈率(TTM)', period='近五年')
        if df_pe is not None and len(df_pe) >= 100:
            current_pe = float(df_pe['value'].iloc[-1])
            result['pe'] = round(current_pe, 2)
            # 分位计算
            pes = df_pe['value'].dropna().astype(float)
            result['pe_pct'] = round((pes <= current_pe).sum() / len(pes) * 100, 1)
        
        # PB 近五年
        df_pb = ak.stock_zh_valuation_baidu(symbol=code, indicator='市净率', period='近五年')
        if df_pb is not None and len(df_pb) >= 100:
            current_pb = float(df_pb['value'].iloc[-1])
            result['pb'] = round(current_pb, 2)
            pbs = df_pb['value'].dropna().astype(float)
            result['pb_pct'] = round((pbs <= current_pb).sum() / len(pbs) * 100, 1)
    except:
        pass
    return result

def get_dividend_yield(code: str, price: float) -> Optional[float]:
    """获取股息率：巨潮资讯按年度汇总 → akshare EM → 静态参考"""
    import re as _re
    
    # 源1: 巨潮资讯（独立于东方财富），按实施年度汇总每股分红
    try:
        import akshare as ak
        df = ak.stock_dividend_cninfo(symbol=code)
        if df is not None and len(df) > 0:
            # 列顺序: [0]实施公告发布日期 [1]分红方案 [2]送股比例 [3]转增比例 [4]派息比例 [5-9]... [10]报告期
            yearly_div = {}  # year -> total dividend per 10 shares
            for _, row in df.iterrows():
                # 从实施公告发布日期 (col 0) 提取年份
                date_str = str(row.iloc[0])
                yr_match = _re.search(r'(20\d{2})', date_str)
                if not yr_match:
                    continue
                yr = int(yr_match.group(1))
                # 派息比例 (col 4)
                dps_raw = row.iloc[4]
                try:
                    dps_val = float(dps_raw)
                except (ValueError, TypeError):
                    continue
                if dps_val <= 0:
                    continue
                yearly_div[yr] = yearly_div.get(yr, 0) + dps_val
            
            if yearly_div:
                # 取最近完整年份（当前年份可能还不完整）
                current_yr = datetime.now().year
                for yr in [current_yr-1, current_yr, current_yr-2]:
                    if yr in yearly_div:
                        total_per_10 = yearly_div[yr]
                        dps_per_share = total_per_10 / 10
                        if price > 0 and dps_per_share > 0:
                            return round(dps_per_share / price * 100, 2)
    except:
        pass
    
    # 源2: akshare stock_dividents_em (东方财富，夜间可能挂)
    try:
        import akshare as ak
        div = ak.stock_dividents_em(symbol=code)
        if div is not None and len(div) > 0:
            latest_year = datetime.now().year - 1
            for yr in [latest_year, latest_year-1]:
                yr_data = div[div['报告期'].astype(str).str.startswith(str(yr))]
                if len(yr_data) > 0 and '派息' in yr_data.columns:
                    dps = yr_data['派息'].max()
                    if price > 0 and float(dps) > 0:
                        return round(float(dps)/price*100, 2)
    except:
        pass
    
    # 源3: 常见高股息股票的静态参考值（最后兜底——仅当API完全不可用时）
    STATIC_DIV_YIELD = {
        '601166': 5.5,  # 兴业银行
        '600036': 5.0,  # 招商银行
        '600900': 3.8,  # 长江电力
        '002714': 2.0,  # 牧原股份
    }
    if code in STATIC_DIV_YIELD:
        return STATIC_DIV_YIELD[code]
    
    return None

# 已知的约估PE数据（用于历史分位的静态参考——当API不可用时）
# 这些数据手动维护，作为兜底。更新时间：2026-04-25
STATIC_VALUATION_REF = {
    '600036': {'pe': 6.5, 'pb': 0.88, 'pe_5y_low': 6, 'pe_5y_high': 14, 'pe_5y_median': 10, 'pb_5y_low': 0.7, 'pb_5y_high': 1.6, 'pb_5y_median': 1.1},
    '601166': {'pe': 5.2, 'pb': 0.55, 'pe_5y_low': 3.5, 'pe_5y_high': 7, 'pe_5y_median': 5, 'pb_5y_low': 0.45, 'pb_5y_high': 0.9, 'pb_5y_median': 0.65},
    '600900': {'pe': 22, 'pb': 2.8, 'pe_5y_low': 15, 'pe_5y_high': 28, 'pe_5y_median': 21, 'pb_5y_low': 2.0, 'pb_5y_high': 3.5, 'pb_5y_median': 2.8},
    '002714': {'pe': 18, 'pb': 3.5, 'pe_5y_low': 10, 'pe_5y_high': 40, 'pe_5y_median': 20, 'pb_5y_low': 2.5, 'pb_5y_high': 7, 'pb_5y_median': 4.5},
}

def estimate_pct_from_range(current: float, low: float, high: float) -> Optional[float]:
    """从已知区间估算分位"""
    if not current or current <= 0: return None
    if current <= low: return 0.0
    if current >= high: return 100.0
    return round((current - low) / (high - low) * 100, 1)

def get_valuation(code: str, is_etf: bool, price: float) -> Dict:
    """获取估值数据：百度估值优先 → 东方财富 → 静态参考兜底"""
    result = {'pe':None,'pb':None,'pe_pct':None,'pb_pct':None,'div_yield':None}
    if is_etf: return result
    
    # 百度估值（独立于东方财富，全天可用）
    baidu_val = get_valuation_baidu(code)
    result.update(baidu_val)
    
    # 如果百度失败，尝试东方财富
    if result['pe'] is None or result['pb'] is None:
        val = get_valuation_from_sina(code, price)
        if result['pe'] is None: result['pe'] = val.get('pe')
        if result['pb'] is None: result['pb'] = val.get('pb')
    
    # 静态参考（最终兜底）
    ref = STATIC_VALUATION_REF.get(code, {})
    if result['pe'] is None and ref.get('pe'):
        result['pe'] = ref['pe']
    if result['pb'] is None and ref.get('pb'):
        result['pb'] = ref['pb']
    
    # PE分位：优先百度（已有分位），其次静态区间估算
    if result['pe_pct'] is None and result['pe'] and ref.get('pe_5y_low'):
        pct = estimate_pct_from_range(result['pe'], ref['pe_5y_low'], ref['pe_5y_high'])
        if pct is not None: result['pe_pct'] = pct
    
    if result['pb_pct'] is None and result['pb'] and ref.get('pb_5y_low'):
        pct = estimate_pct_from_range(result['pb'], ref['pb_5y_low'], ref['pb_5y_high'])
        if pct is not None: result['pb_pct'] = pct
    
    # 股息率
    result['div_yield'] = get_dividend_yield(code, price)
    
    # 价格分位回退：当PE/PB分位均不可得时，用价格在日线数据中的分位做近似
    if result['pe_pct'] is None and result['pb_pct'] is None:
        result['price_pct'] = None  # will be filled in analyze()
    
    return result

def get_nb_flow(code: str) -> Dict:
    result = {'trend':'无数据','score':0}
    try:
        import akshare as ak
        mkt = '沪股通' if code.startswith('6') else '深股通'
        df = ak.stock_hsgt_individual_em(stock=code, market=mkt)
        if df is not None and len(df)>=20:
            recent=df.tail(20)
            if '持股数量' in recent.columns:
                chg = recent['持股数量'].iloc[-1]-recent['持股数量'].iloc[0]
                if chg>0: result={'trend':'增持','score':80}
                elif chg<0: result={'trend':'减持','score':20}
                else: result={'trend':'持平','score':50}
    except: pass
    return result

def classify(code: str, name: str) -> str:
    m = {'600036':'银行','601166':'银行','600900':'电力','002714':'生猪养殖',
         '000333':'家电','000876':'生猪养殖','000858':'白酒',
         '603259':'医药生物',
         '515170':'食品饮料','515120':'医药生物','159847':'医药生物',
         '513130':'互联网科技','513050':'互联网科技'}
    return m.get(code,'未知')

def calc_price_percentile(code: str, daily: Dict) -> Optional[float]:
    """计算当前价格在日线数据中的分位（近似估值代理）"""
    # 从日线的52周高/低计算
    price = daily.get('price')
    h52 = daily.get('high_52w')
    l52 = daily.get('low_52w')
    if price and h52 and l52 and h52 > l52:
        pct = (price - l52) / (h52 - l52) * 100
        return round(pct, 1)
    return None

def score_val(val: Dict, ind: str, code: str, daily: Dict, tsr_result: Optional[Dict] = None) -> Tuple[float,str]:
    s,dl=0,[]
    pp=val.get('pe_pct')
    if pp is not None:
        if pp<10: s+=15; dl.append(f"PE分位{pp}% 极度低估 +15")
        elif pp<20: s+=12; dl.append(f"PE分位{pp}% 低估 +12")
        elif pp<30: s+=8; dl.append(f"PE分位{pp}% 偏低 +8")
        elif pp<50: s+=5; dl.append(f"PE分位{pp}% 中性 +5")
        elif pp<70: s+=2; dl.append(f"PE分位{pp}% 偏高 +2")
        else: dl.append(f"PE分位{pp}% 高估 +0")
    elif val.get('pe'):
        pe=val['pe']
        if pe<10: s+=12; dl.append(f"PE={pe} 极低 +12")
        elif pe<20: s+=8; dl.append(f"PE={pe} 偏低 +8")
        elif pe<40: s+=5; dl.append(f"PE={pe} 中性 +5")
    bp=val.get('pb_pct')
    if bp is not None:
        if bp<10: s+=10; dl.append(f"PB分位{bp}% 极度低估 +10")
        elif bp<20: s+=7; dl.append(f"PB分位{bp}% 低估 +7")
    
    # v2.3: TSR综合股东回报率替代裸股息率（上限8分 vs 旧版5分）
    if tsr_result:
        ts, td = tsr_score(tsr_result)
        s += ts
        if td: dl.append(td)
    else:
        dy=val.get('div_yield')
        if dy:
            if dy>5: s+=5; dl.append(f"股息率{dy}% 极具吸引力 +5")
            elif dy>3: s+=3; dl.append(f"股息率{dy}% 有吸引力 +3")
            elif dy>1.5: s+=1; dl.append(f"股息率{dy}% 一般 +1")
    
    # 价格分位回退：当PE和PB分位均不可得时
    if pp is None and bp is None and daily:
        price_pct = calc_price_percentile(code, daily)
        if price_pct is not None:
            val['price_pct'] = price_pct
            if price_pct < 10: s+=12; dl.append(f"价格1年分位{price_pct}% 极低位替代估值 +12")
            elif price_pct < 20: s+=8; dl.append(f"价格1年分位{price_pct}% 低位替代估值 +8")
            elif price_pct < 30: s+=5; dl.append(f"价格1年分位{price_pct}% 偏低替代估值 +5")
    
    return min(s,30), ' | '.join(dl) if dl else '数据不足'

def fetch_all_time_high(code: str, is_etf: bool) -> Optional[Dict]:
    """
    从新浪获取历史最高价和总回撤。
    策略：优先用周线（scale=1200, 约270条覆盖5-6年），数据不足时回退日线。
    日线只有约1000条（约4年），对于2021年上市的ETF/股票会漏掉早期高点。
    """
    import requests as req
    mkt = 'sh' if (code.startswith('6') or code.startswith('5')) else 'sz'
    try:
        s = req.Session(); s.trust_env = False
        all_time_high = None
        current = None
        best_source = ''
        
        # 方案1：周线 — 数据量少但时间跨度长（约270条→5-6年），能抓到2021年的高点
        r_week = s.get(
            f'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={mkt}{code}&scale=1200&ma=no&datalen=500',
            timeout=15
        )
        if r_week.status_code == 200 and len(r_week.text) > 1000:
            raw = r_week.json()
            if raw and len(raw) >= 20:
                highs_w = [float(x['high']) for x in raw]
                closes_w = [float(x['close']) for x in raw]
                ath_w = max(highs_w)
                cur_w = closes_w[-1]
                all_time_high = ath_w
                current = cur_w
                best_source = 'weekly'
        
        # 方案2：日线兜底 — 数据量最多（约1000条），但时间仅约4年
        r_day = s.get(
            f'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={mkt}{code}&scale=240&ma=no&datalen=1020',
            timeout=10
        )
        if r_day.status_code == 200 and len(r_day.text) > 1000:
            raw = r_day.json()
            if raw and len(raw) >= 100:
                highs_d = [float(x['high']) for x in raw]
                closes_d = [float(x['close']) for x in raw]
                ath_d = max(highs_d)
                cur_d = closes_d[-1]
                # 如果日线ATH更高（说明周线漏了高点），用日线的ATH
                if all_time_high is None or ath_d > all_time_high:
                    all_time_high = ath_d
                    current = cur_d
                    best_source = 'daily(better ATH)' if all_time_high is not None else 'daily'
        
        if all_time_high is not None and current is not None:
            total_dd = (current - all_time_high) / all_time_high * 100
            return {
                'all_time_high': round(all_time_high, 2),
                'total_drawdown': round(total_dd, 1),
            }
    except: pass
    return None

def score_cycle(daily: Dict, weekly: Dict, total_dd_info: Optional[Dict] = None) -> Tuple[float,str]:
    s,dl=0,[]
    dd=daily.get('drawdown',0); dlw=daily.get('dist_low',100)
    if dd<-40: s+=15; dl.append(f"52周回撤{dd:.0f}% 深度 +15")
    elif dd<-30: s+=12; dl.append(f"52周回撤{dd:.0f}% 显著 +12")
    elif dd<-20: s+=8; dl.append(f"52周回撤{dd:.0f}% 中等 +8")
    elif dd<-10: s+=4; dl.append(f"52周回撤{dd:.0f}% 小幅 +4")
    
    # 全生命周期回撤（月线数据，独立于52周）
    if total_dd_info and total_dd_info.get('total_drawdown') is not None:
        total_dd = total_dd_info['total_drawdown']
        ath = total_dd_info['all_time_high']
        if total_dd < -70: s+=10; dl.append(f"历史总回撤{total_dd:.0f}%(高{ath:.1f}) 史诗级 +10")
        elif total_dd < -50: s+=8; dl.append(f"历史总回撤{total_dd:.0f}%(高{ath:.1f}) 深度 +8")
        elif total_dd < -30: s+=5; dl.append(f"历史总回撤{total_dd:.0f}%(高{ath:.1f}) 显著 +5")
        elif total_dd < -20: s+=2; dl.append(f"历史总回撤{total_dd:.0f}%(高{ath:.1f}) 中等 +2")
    
    if dlw<5: s+=10; dl.append(f"距52周低点+{dlw:.1f}% +10")
    elif dlw<10: s+=7; dl.append(f"距52周低点+{dlw:.1f}% +7")
    elif dlw<15: s+=4; dl.append(f"距52周低点+{dlw:.1f}% +4")
    if weekly.get('macd_divergence'): s+=5; dl.append("周线MACD底背离 +5")
    return min(s,35), ' | '.join(dl) if dl else '无数据'

def score_tech(daily: Dict, weekly: Dict) -> Tuple[float,str]:
    s,dl=0,[]
    r=daily.get('rsi',50)
    if r<25: s+=7; dl.append(f"RSI={r:.0f} 深度超卖 +7")
    elif r<35: s+=5; dl.append(f"RSI={r:.0f} 超卖 +5")
    elif r<45: s+=2; dl.append(f"RSI={r:.0f} 偏弱 +2")
    kk=daily.get('kd_k',50)
    if kk<20: s+=5; dl.append(f"KD(K={kk:.0f}) 超卖 +5")
    bp=daily.get('boll_pos',50)
    if bp<15: s+=5; dl.append("布林下轨 +5")
    elif bp<30: s+=3; dl.append("布林偏低位 +3")
    # --- ADX 极端趋势检测 (v2.2) ---
    ad= daily.get('adx',25); pd_= daily.get('di_plus',0); md=daily.get('di_minus',0)
    aw=weekly.get('adx',25); pw=weekly.get('di_plus',0); mw=weekly.get('di_minus',0)
    # 日线 ADX 极端趋势惩罚：趋势过强时不宜猜底/追顶
    if ad>50:   s-=5; dl.append(f"ADX={ad:.0f}>50 极端趋势 -5")
    elif ad>40: s-=2; dl.append(f"ADX={ad:.0f}>40 强趋势 -2")
    # 周线向上趋势奖励
    if aw>25 and pw>mw: s+=3; dl.append(f"周线向上(DI+>{mw:.0f}) +3")
    # DI 比值分析：单边绝对主导时扣分
    di_ratio = max(pd_,md)/min(pd_,md) if pd_>0 and md>0 else 0
    if di_ratio>3 and ad>25:
        dominant='多头' if pd_>md else '空头'
        s-=2; dl.append(f"日线{dominant}绝对主导(DI比{di_ratio:.1f}:1) -2")
    if daily.get('obv_up'): s+=2; dl.append("OBV上升 +2")
    return min(s,20), ' | '.join(dl) if dl else '中性'

def score_capital(code: str) -> Tuple[float,str]:
    nb=get_nb_flow(code); sc=nb['score']
    if sc>=70: return 10, f"北向：{nb['trend']} +10"
    elif sc>=50: return 5, f"北向：{nb['trend']} +5"
    return 2, f"北向：{nb['trend']} +2"

def score_ind(industry: str) -> Tuple[float,str]:
    c=INDUSTRY_CYCLE.get(industry,{'phase':'未知','note':'数据缺失','score':50})
    return round(c['score']/10,1), f"{industry}: {c['phase']} — {c['note']}"

def build_plan(price: float, daily: Dict, score: float) -> str:
    l52 = daily.get('low_52w', price * 0.9)
    ma20 = daily.get('ma20', price)
    # 锚定价：取 52周低点 和 MA20 中较低者，确保不会大幅低于合理区间
    anchor = min(max(l52, price * 0.7), ma20)
    
    if score >= 80:
        tiers = [(price, 30), (price*0.95, 35), (price*0.88, 25), (price*0.80, 10)]
        strat = "黄金收集区 — 当前就是好时机"
    elif score >= 70:
        tiers = [(price, 20), (price*0.93, 30), (price*0.85, 30), (price*0.78, 20)]
        strat = "可分4批在6个月内完成建仓"
    elif score >= 55:
        tiers = [(price, 15), (price*0.90, 25), (price*0.82, 35), (price*0.75, 25)]
        strat = "轻仓试探，等待更好价格"
    elif score >= 40:
        tiers = [(anchor, 15), (anchor*0.92, 25), (anchor*0.85, 35), (anchor*0.78, 25)]
        strat = "暂不建仓，关注回调至MA20/52周低点附近"
    else:
        # 估值数据缺失导致极低分：仅给参考区间，不做具体价格建议
        tiers = [(price*0.90, 15), (price*0.82, 25), (price*0.75, 35), (price*0.68, 25)]
        strat = "估值数据缺失，建仓价格仅供参考；建议先确认估值分位后再决策"
    
    lines = [f"  策略: {strat}"]
    for i, (t, pct) in enumerate(tiers):
        label = ['试探仓', '加码仓', '重仓', '极端机会'][i]
        lines.append(f"  {label}: {t:.2f}元 — {pct}%")
    avg = sum(t*p/100 for t, p in tiers)
    lines.append(f"  估算成本: {avg:.2f}元")
    lines.append(f"  止损参考: 基本面恶化或跌破 {anchor:.2f}")
    return '\n'.join(lines)

def analyze(holding: Dict) -> Dict:
    code,name,is_etf=holding['code'],holding['name'],holding['is_etf']
    res={'code':code,'name':name,'is_etf':is_etf}
    try:
        daily=fetch_kline(code,is_etf,'daily')
        if daily is None or len(daily)<20:
            res['error']='数据不足'; return res
        dt=calc_ta(daily)
        price=dt.get('price',0)
        weekly=fetch_kline(code,is_etf,'weekly')
        wt=calc_ta(weekly) if weekly is not None and len(weekly)>=20 else {}
        val=get_valuation(code,is_etf,price)
        ind=classify(code,name)
        
        # 全生命周期回撤（周线优先，日线兜底）
        ath_info = fetch_all_time_high(code, is_etf)
        
        # ── v2.0: 价值陷阱质量检测 ──
        vt_result = value_trap_detect(code, name, ind)
        quality_coeff = vt_result.get('quality_coefficient', 1.0)
        quality_score_val = vt_result.get('quality_score', 10)
        
        # ── v2.3: TSR综合股东回报率 ──
        tsr_result = tsr_calculate(code, name, is_etf, price, val.get('div_yield'))
        
        # ── v2.3: AI叙事风险暴露度 ──
        is_tech = ind in ('互联网科技',)
        ai_exposure = ai_detect(code, name, ind, is_etf)
        
        # ── v2.3: 跨市场估值比价 (港股/跨境科技ETF) ──
        cross_market = cm_get(code, is_etf, ind, val.get('pe'))
        
        # 估值温度计得分 × 质量系数（v2.3: 传入TSR结果）
        vs,vd=score_val(val,ind,code,dt,tsr_result)
        vs_adjusted = vs * quality_coeff
        cs,cd=score_cycle(dt,wt,ath_info)
        ts,td=score_tech(dt,wt)
        ks,kd=score_capital(code); ii,id_=score_ind(ind)
        # 新权重：质量20% + 估值25% + 周期20% + 技术15% + 资金10% + 行业10%
        total=round(quality_score_val + vs_adjusted*25.0/30 + cs*20.0/25 + ts*15.0/20 + ks*10.0/15 + ii*10.0/10)
        
        # ── v2.3: AI风险折扣（仅对科技行业标的生效） ──
        total_ai_adjusted, ai_discount_note = ai_apply(total, ai_exposure, is_tech)
        
        res.update({'daily_ta':dt,'weekly_ta':wt,'val_data':val,'industry':ind,
            'ath_info':ath_info,
            'vt_result': vt_result,
            'tsr_result': tsr_result,
            'ai_exposure': ai_exposure,
            'cross_market': cross_market,
            'scores':{'quality': round(quality_score_val,1), 'valuation':vs,'valuation_adjusted': round(vs_adjusted,1), 'cycle':cs,'technical':ts,'capital':ks,'industry':ii},
            'details':{'valuation':vd,'cycle':cd,'technical':td,'capital':kd,'industry':id_},
            'total_score': total,
            'total_score_ai_adjusted': total_ai_adjusted,
            'ai_discount_note': ai_discount_note})
    except Exception as e: res['error']=str(e)
    return res

def fmt(res: Dict) -> str:
    if 'error' in res: return f"\n {res['name']} ({res['code']}) 失败：{res['error']}"
    code,name,is_etf=res['code'],res['name'],res['is_etf']
    tag=' [ETF]' if is_etf else ''
    dt,wt,val,ind=res['daily_ta'],res['weekly_ta'],res['val_data'],res['industry']
    sc,ds=res['scores'],res['details']
    total_raw = res['total_score']
    total_ai = res.get('total_score_ai_adjusted', total_raw)
    ai_note = res.get('ai_discount_note', '')
    total = total_ai  # 用AI调整后得分做评级
    rating='🟢 黄金收集区' if total>=80 else '🟢 可收集' if total>=70 else '🟡 观察' if total>=55 else '🟡 暂不收集' if total>=40 else '🔴 远离'
    price=dt.get('price',0)
    tsr_res = res.get('tsr_result', {})
    lines=[
        f"\n{'='*70}",
        f" {name}{tag} ({code}) — 长期建仓评估",
        f"{'='*70}",
        "",
        "【估值温度计】",
        f"  PE: {val.get('pe','N/A')} | 分位: {val.get('pe_pct','N/A')}%",
        f"  PB: {val.get('pb','N/A')} | 分位: {val.get('pb_pct','N/A')}%",
    ]
    
    # v2.3: TSR综合股东回报率显示
    if tsr_res and tsr_res.get('tsr', 0) > 0:
        tsr_val = tsr_res.get('tsr', 0)
        div_y = tsr_res.get('dividend_yield', 0)
        buy_y = tsr_res.get('buyback_yield', 0)
        if buy_y > 0.5:
            lines.append(f"  TSR(综合回报): {tsr_val}% (股息{div_y}% + 回购{buy_y}%)")
        else:
            lines.append(f"  TSR(综合回报): {tsr_val}% (股息{div_y}%)")
        lines.append(f"  → {tsr_res.get('tsr_rating', '')} | {tsr_res.get('source', '')}")
    elif val.get('div_yield'):
        lines.append(f"  股息率: {val['div_yield']}%")
    
    lines.append(f"  → {ds['valuation']}")
    
    # v2.3: 跨市场估值比价
    cm = res.get('cross_market')
    if cm and cm.get('spreads'):
        lines.append("")
        lines.append("【跨市场估值比价】")
        lines.append(f"  {cm_fmt(cm)}")
    
    lines.append("")
    lines.append("【周期位置】")
    lines.append(f"  52周: {dt['low_52w']:.2f} - {dt['high_52w']:.2f}")
    lines.append(f"  距高点: {dt['drawdown']:.1f}% | 距52周低点: +{dt['dist_low']:.1f}%")
    
    # 全生命周期回撤
    ath = res.get('ath_info')
    if ath:
        lines.append(f"  历史最高: {ath['all_time_high']:.2f} | 历史总回撤: {ath['total_drawdown']:.1f}%")
    
    lines.append(f"  \u2192 {ds['cycle']}")
    lines.append("")
    lines.append("\u3010\u65e5\u7ebf\u5165\u573a\u6821\u51c6\u3011")
    lines.append(f"  RSI: {dt['rsi']:.1f} | KD: K{dt['kd_k']:.0f}/D{dt['kd_d']:.0f}")
    lines.append(f"  ADX: {dt['adx']:.1f} | DI+:{dt['di_plus']:.1f}/DI-:{dt['di_minus']:.1f}")
    lines.append(f"  \u5e03\u6797: {dt['boll_lower']:.2f} - {dt['boll_upper']:.2f} (\u4f4d\u7f6e{dt['boll_pos']:.0f}%)")
    lines.append(f"  \u2192 {ds['technical']}")
    lines.append("")
    lines.append("\u3010\u5468\u7ebf\u8d8b\u52bf\u3011")
    lines.append(f"  MA20: {wt['ma20']:.2f} | MA60: {wt['ma60']:.2f}" if wt else "  \u5468\u7ebf\u6570\u636e\u4e0d\u8db3")
    lines.append(f"  MACD: {'\u5e95\u80cc\u79bb' if wt.get('macd_divergence') else '\u65e0\u80cc\u79bb'}" if wt else "")
    lines.append(f"  ADX: {wt['adx']:.1f} | DI+:{wt['di_plus']:.1f}/DI-:{wt['di_minus']:.1f}" if wt else "")
    lines.append("")
    lines.append("\u3010\u8d44\u91d1\u9762\u3011")
    lines.append(f"  \u2192 {ds['capital']}")
    lines.append("")
    lines.append("\u3010\u884c\u4e1a\u5468\u671f\u3011")
    lines.append(f"  \u2192 {ds['industry']}")
    lines.append("")
    lines.append(f"{'\u2550'*70}")
    # v2.3: AI调整后的评分展示
    if ai_note:
        lines.append(f" \u7efc\u5408\u5efa\u4ed3\u8bc4\u7ea7: {rating} ({total:.0f}/100) [原始{total_raw:.0f}分, {ai_note}]")
    else:
        lines.append(f" \u7efc\u5408\u5efa\u4ed3\u8bc4\u7ea7: {rating} ({total:.0f}/100)")
    vs_raw = sc.get('valuation', 0)
    vs_adj = sc.get('valuation_adjusted', vs_raw)
    qs_display = sc.get('quality', 10)
    if abs(vs_adj - vs_raw) > 0.5:
        lines.append(f" 质量({qs_display}) + 估值({vs_raw:.0f}→{vs_adj:.0f}) + 周期({sc['cycle']}) + 技术({sc['technical']}) + 资金({sc['capital']}) + 行业({sc['industry']})")
    else:
        lines.append(f" 质量({qs_display}) + 估值({sc['valuation']}) + 周期({sc['cycle']}) + 技术({sc['technical']}) + 资金({sc['capital']}) + 行业({sc['industry']})")
    # v2.3: AI暴露度提示
    ai_exp = res.get('ai_exposure', {})
    if ai_exp and ai_exp.get('level') not in ('none', None):
        level = ai_exp.get('level', '')
        reason = ai_exp.get('reason', '')
        lines.append(f" AI暴露: {level} — {reason}")
    lines.append(f"{'\u2550'*70}")
    lines.append("\u3010\u5206\u6279\u5efa\u4ed3\u8ba1\u5212\u3011")
    lines.append(build_plan(price, dt, total))
    return '\n'.join(lines)

def _get_effective_score(r: Dict) -> float:
    """获取有效评分：AI调整后 > 原始"""
    return r.get('total_score_ai_adjusted', r.get('total_score', 50))

def summary(results: List[Dict], holdings: List[Dict]) -> str:
    scored=[r for r in results if 'error' not in r]
    scored.sort(key=_get_effective_score, reverse=True)
    lines=[
        f"\n{'='*70}",
        " 长期建仓组合总览",
        f"{'='*70}",
    ]
    def _disp_score(r):
        raw = r['total_score']
        adj = r.get('total_score_ai_adjusted', raw)
        if adj != raw:
            return f"{raw:.0f}→{adj:.0f}分"
        return f"{adj:.0f}分"
    lines.append("\n【当前可收集】(≥70)")
    sc70=[s for s in scored if _get_effective_score(s)>=70]
    if sc70:
        for i,s in enumerate(sc70):
            etf=' [ETF]' if s['is_etf'] else ''
            lines.append(f"  {i+1}. 🟢 {s['name']}{etf} ({s['code']}) — {_disp_score(s)}")
    else: lines.append("  (无)")
    lines.append("\n【观察等待】(55-69)")
    sc55=[s for s in scored if 55<=_get_effective_score(s)<70]
    if sc55:
        for i,s in enumerate(sc55):
            etf=' [ETF]' if s['is_etf'] else ''
            lines.append(f"  {i+1}. 🟡 {s['name']}{etf} ({s['code']}) — {_disp_score(s)}")
    else: lines.append("  (无)")
    lines.append("\n【暂不收集/远离】(<55)")
    sc_low=[s for s in scored if _get_effective_score(s)<55]
    if sc_low:
        for i,s in enumerate(sc_low):
            etf=' [ETF]' if s['is_etf'] else ''
            lines.append(f"  {i+1}. 🔴 {s['name']}{etf} ({s['code']}) — {_disp_score(s)}")
    else: lines.append("  (无)")
    avg=sum(_get_effective_score(s) for s in scored)/len(scored) if scored else 50
    lines.append(f"\n【整体建议】")
    lines.append(f"  平均评分: {avg:.0f}/100")
    if avg>=70: lines.append("  当前市场为长线资金提供了较好的收集窗口")
    elif avg>=55: lines.append("  部分标的具备收集价值，建议选择性建仓")
    else: lines.append("  多数标的估值或技术面尚未到理想收集区，保持耐心")
    return '\n'.join(lines)

def main():
    print("="*70, file=sys.stderr)
    print(" A 股长期建仓助手 — 以年为单位 + 日线/周线校准", file=sys.stderr)
    print("="*70, file=sys.stderr)
    holdings=parse_portfolio(PORTFOLIO_FILE)
    if not holdings:
        print("未找到持仓", file=sys.stderr); sys.exit(1)
    print(f" {len(holdings)} 只标的", file=sys.stderr)
    results=[]
    for h in holdings:
        etf='[ETF]' if h['is_etf'] else ''
        print(f"  分析 {h['name']}{etf}({h['code']})...", file=sys.stderr)
        res=analyze(h); results.append(res)
        print(fmt(res))
    if len(holdings)>1:
        print(summary(results, holdings))
    print("\n"+"="*70, file=sys.stderr)
    print(" 分析完成", file=sys.stderr)

if __name__=="__main__":
    main()
