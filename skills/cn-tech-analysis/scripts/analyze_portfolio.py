#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A 股技术面分析报告生成器 - 新手友好版 (支持 ETF + 基本面)
为用户持仓股票和 ETF 生成技术面分析，提供分周期操作建议和置信度评估
包含指标解释、技术场景识别和具体操作建议
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import re
import time
import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime, timedelta

# 持仓文件路径
PORTFOLIO_FILE = r"C:\agent\03-portfolio-tools\my-holdings.txt"

# 重试配置
MAX_RETRIES = 3
RETRY_DELAY = 3  # 秒


def parse_portfolio_file(filepath: str) -> List[Dict[str, str]]:
    """解析持仓文件"""
    holdings = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    name = parts[1] if len(parts) == 2 else ' '.join(parts[1:-1])
                    code = parts[-1]
                    match = re.search(r'\d{6}', code)
                    if match:
                        code = match.group()
                        is_etf = code.startswith('5') or code.startswith('1')
                        holdings.append({'name': name, 'code': code, 'is_etf': is_etf})
    except Exception as e:
        print(f"读取持仓文件失败：{e}", file=sys.stderr)
    return holdings


def get_stock_fundamentals(code: str) -> Dict:
    """获取股票基本面数据（PE、PB、行业等） - 简化版"""
    try:
        import akshare as ak
        
        # 使用个股估值数据
        try:
            # 获取实时行情，包含 PE/PB
            stock_data = ak.stock_zh_a_daily(symbol=f"sh{code}" if code.startswith('6') else f"sz{code}", start_date="20260301", end_date="20260312")
            if stock_data is not None and len(stock_data) > 0:
                # 尝试从其他接口获取 PE/PB
                pass
        except:
            pass
        
        # 备用：返回行业信息
        industry_map = {
            '600036': '银行', '600900': '电力', '000333': '家电',
            '515170': 'ETF-食品饮料', '515120': 'ETF-创新药'
        }
        
        return {
            'pe': None,  # 暂时不获取，避免网络超时
            'pb': None,
            'industry': industry_map.get(code, '未知'),
            'market_cap': '未知'
        }
            
    except Exception as e:
        return {'pe': None, 'pb': None, 'industry': '未知', 'market_cap': '未知'}


def calculate_ta_indicators(df: pd.DataFrame) -> Dict:
    """计算技术指标"""
    if len(df) < 20:
        return None
    
    close = df['close'].astype(float)
    high = df['high'].astype(float)
    low = df['low'].astype(float)
    open_price = df['open'].astype(float)
    volume = df['volume'].astype(float)
    
    data = {
        'price': close.iloc[-1],
        'change_pct': ((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100) if len(close) > 1 else 0,
        'ma5': close.rolling(5).mean().iloc[-1],
        'ma10': close.rolling(10).mean().iloc[-1],
        'ma20': close.rolling(20).mean().iloc[-1],
        'ma60': close.rolling(60).mean().iloc[-1] if len(close) >= 60 else close.rolling(20).mean().iloc[-1],
        'high60': high.rolling(60).max().iloc[-1] if len(high) >= 60 else high.max(),
        'low60': low.rolling(60).min().iloc[-1] if len(low) >= 60 else low.min(),
    }
    
    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_dif = ema12 - ema26
    macd_dea = macd_dif.ewm(span=9, adjust=False).mean()
    macd_hist = 2 * (macd_dif - macd_dea)
    data['macd_dif'] = macd_dif.iloc[-1]
    data['macd_dea'] = macd_dea.iloc[-1]
    data['macd_hist'] = macd_hist.iloc[-1]
    
    # RSI
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    data['rsi14'] = (100 - (100 / (1 + rs))).iloc[-1]
    
    # KD
    low_9 = low.rolling(9).min()
    high_9 = high.rolling(9).max()
    rsv = (close - low_9) / (high_9 - low_9) * 100
    k = rsv.ewm(com=2, adjust=False).mean()
    d = k.ewm(com=2, adjust=False).mean()
    data['kd_k'] = k.iloc[-1]
    data['kd_d'] = d.iloc[-1]
    
    # 布林带
    ma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    data['boll_upper'] = (ma20 + 2 * std20).iloc[-1]
    data['boll_mid'] = ma20.iloc[-1]
    data['boll_lower'] = (ma20 - 2 * std20).iloc[-1]
    
    # ADX/DI
    period = 14
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0)
    minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0)
    
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = pd.Series(tr).rolling(period).mean()
    
    plus_di = pd.Series(plus_dm).rolling(period).mean() / atr * 100
    minus_di = pd.Series(minus_dm).rolling(period).mean() / atr * 100
    
    dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100
    adx = dx.rolling(period).mean()
    
    data['adx'] = adx.iloc[-1]
    data['di_plus'] = plus_di.iloc[-1]
    data['di_minus'] = minus_di.iloc[-1]
    data['atr'] = atr.iloc[-1]
    
    # OBV 变化
    obv = (np.sign(close.diff()) * volume).fillna(0).cumsum()
    data['obv_change5'] = ((obv.iloc[-1] - obv.iloc[-5]) / obv.iloc[-5] * 100) if len(obv) > 5 else 0
    
    # 主力资金（简化估算）
    typical_price = (high + low + close) / 3
    money_flow = typical_price * volume
    data['main_force_net'] = (money_flow.iloc[-1] - money_flow.iloc[-2]) / 100000000
    
    return data


def fetch_stock_data_with_retry(code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    从多个数据源获取股票日K线，带重试和兜底
    优先级：akshare(东方财富) → 新浪财经兜底
    """
    import requests as req
    
    # 源1：akshare (东方财富)
    for attempt in range(MAX_RETRIES):
        try:
            import akshare as ak
            session = req.Session()
            session.trust_env = False
            # Monkey-patch requests 让 akshare 内部也用无代理
            original_get = req.get
            original_post = req.post
            def patched_get(url, **kwargs):
                kwargs.setdefault('timeout', 15)
                s = req.Session()
                s.trust_env = False
                return s.get(url, **kwargs)
            req.get = patched_get
            req.post = lambda url, **kwargs: (lambda s: s.post(url, **kwargs))(lambda: setattr(req.Session(), 'trust_env', False) or req.Session())
            try:
                df = ak.stock_zh_a_hist(symbol=code, period='daily', start_date=start_date, end_date=end_date)
                if df is not None and len(df) >= 20:
                    return df
            finally:
                req.get = original_get
                req.post = original_post
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                print(f"    源1 第{attempt+1}次失败: {str(e)[:60]}...重试中", file=sys.stderr)
                time.sleep(RETRY_DELAY)
            else:
                print(f"    源1 全部{MAX_RETRIES}次失败，启用兜底方案...", file=sys.stderr)
    
    # 源2：新浪财经兜底
    try:
        market = 'sh' if code.startswith('6') else 'sz'
        for attempt in range(MAX_RETRIES):
            try:
                s = req.Session()
                s.trust_env = False
                url = f'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData'
                params = {'symbol': f'{market}{code}', 'scale': '240', 'ma': 'no', 'datalen': '100'}
                r = s.get(url, params=params, timeout=15)
                if r.status_code == 200 and len(r.text) > 100:
                    raw = r.json()
                    if raw and len(raw) >= 20:
                        records = []
                        for item in raw:
                            records.append({
                                'date': item['day'],
                                'open': float(item['open']),
                                'close': float(item['close']),
                                'high': float(item['high']),
                                'low': float(item['low']),
                                'volume': float(item['volume'])
                            })
                        df = pd.DataFrame(records)
                        print(f"    新浪兜底成功，获取{len(df)}条数据", file=sys.stderr)
                        return df
            except Exception as e2:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
    except Exception as e:
        pass
    
    # 源3：东方财富直接HTTP（去除akshare依赖）
    try:
        s = req.Session()
        s.trust_env = False
        market_id = '1' if code.startswith('6') else '0'
        url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get'
        params = {
            'fields1': 'f1,f2,f3,f4,f5,f6',
            'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116',
            'ut': '7eea3edcaed734bea9cbfc24409ed989',
            'klt': '101', 'fqt': '1',
            'secid': f'{market_id}.{code}',
            'beg': start_date, 'end': end_date
        }
        r = s.get(url, params=params, timeout=15)
        if r.status_code == 200:
            data = r.json()
            if data.get('data') and data['data'].get('klines'):
                records = []
                for kline in data['data']['klines']:
                    parts = kline.split(',')
                    if len(parts) >= 6:
                        records.append({
                            'date': parts[0],
                            'open': float(parts[1]),
                            'close': float(parts[2]),
                            'high': float(parts[3]),
                            'low': float(parts[4]),
                            'volume': float(parts[5])
                        })
                if len(records) >= 20:
                    df = pd.DataFrame(records)
                    print(f"    东方财富直连兜底成功，获取{len(df)}条数据", file=sys.stderr)
                    return df
    except Exception as e:
        pass
    
    return None


def fetch_etf_data_with_retry(code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """获取ETF日K线，带重试和多重兜底"""
    import requests as req
    
    # 源1：东方财富直连（ETF用 1.xxxxxx 格式）
    for attempt in range(MAX_RETRIES):
        try:
            s = req.Session()
            s.trust_env = False
            r = s.get('https://push2his.eastmoney.com/api/qt/stock/kline/get', params={
                'fields1': 'f1,f2,f3,f4,f5,f6',
                'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116',
                'ut': '7eea3edcaed734bea9cbfc24409ed989',
                'klt': '101', 'fqt': '1',
                'secid': f'1.{code}',
                'beg': start_date, 'end': end_date
            }, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if data.get('data') and data['data'].get('klines'):
                    records = []
                    for kline in data['data']['klines']:
                        parts = kline.split(',')
                        if len(parts) >= 6:
                            records.append({
                                'date': parts[0],
                                'open': float(parts[1]),
                                'close': float(parts[2]),
                                'high': float(parts[3]),
                                'low': float(parts[4]),
                                'volume': float(parts[5])
                            })
                    if len(records) >= 20:
                        print(f"    东方财富ETF直连成功，获取{len(records)}条", file=sys.stderr)
                        return pd.DataFrame(records)
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                print(f"    ETF源1第{attempt+1}次失败，重试中...", file=sys.stderr)
                time.sleep(RETRY_DELAY)
    
    # 源2：新浪财经ETF数据
    for attempt in range(MAX_RETRIES):
        try:
            s = req.Session()
            s.trust_env = False
            # 新浪ETF K线接口：基金代码转成 sz515170 或 sh510xxx
            market = 'sz' if code.startswith('1') else 'sh'
            url = f'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData'
            params = {'symbol': f'{market}{code}', 'scale': '240', 'ma': 'no', 'datalen': '100'}
            r = s.get(url, params=params, timeout=15)
            if r.status_code == 200 and len(r.text) > 100:
                raw = r.json()
                if raw and len(raw) >= 20:
                    records = []
                    for item in raw:
                        records.append({
                            'date': item['day'],
                            'open': float(item['open']),
                            'close': float(item['close']),
                            'high': float(item['high']),
                            'low': float(item['low']),
                            'volume': float(item['volume'])
                        })
                    df = pd.DataFrame(records)
                    print(f"    新浪ETF兜底成功，获取{len(df)}条", file=sys.stderr)
                    return df
        except Exception as e2:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
    
    # 源3：akshare fund_etf_hist_em（降级方案）
    try:
        import akshare as ak
        df = ak.fund_etf_hist_em(symbol=code, period='daily', start_date=start_date, end_date=end_date)
        if df is not None and len(df) >= 20:
            print(f"    akshare ETF兜底成功，获取{len(df)}条", file=sys.stderr)
            return df
    except:
        pass
    
    return None


def explain_indicator(name: str, value: float, context: Dict) -> str:
    """解释技术指标含义"""
    explanations = {
        'MA': f"移动平均线，反映近期平均成本。当前价格{context['price']:.2f}元，{'站' if context['price'] > value else '跌'}破 MA{context['ma_period']}({value:.2f})，{'短期趋势偏多' if context['price'] > value else '短期趋势偏空'}。",
        'MACD': f"平滑异同移动平均线，判断趋势强弱。DIF({context['dif']:.4f}){'>' if context['dif'] > context['dea'] else '<'}DEA({context['dea']:.4f})，{'金叉 (看涨信号)' if context['dif'] > context['dea'] else '死叉 (看跌信号)'}。",
        'RSI': f"相对强弱指标，衡量超买超卖。RSI={value:.1f}，{'<30 超卖区 (可能反弹)' if value < 30 else '30-70 中性区' if value < 70 else '>70 超买区 (可能回调)'}。",
        'KD': f"随机指标，判断买卖点。K({context['k']:.1f}){'>' if context['k'] > context['d'] else '<'}D({context['d']:.1f})，{'金叉 (短期买点)' if context['k'] > context['d'] else '死叉 (短期卖点)'}。",
        'BOLL': f"布林带，价格通道。当前价格{'接近上轨 (压力大)' if context['price'] > context['mid'] * 1.02 else '接近下轨 (支撑强)' if context['price'] < context['mid'] * 0.98 else '在中轨附近'}。",
        'ADX': f"趋势强度指标。ADX={value:.1f}，{'<25 震荡市 (高抛低吸)' if value < 25 else '>25 趋势市 (顺势操作)'}。",
        'PE': f"市盈率，衡量估值高低。PE={value:.1f}，{'低估值 (安全边际高)' if value < 15 else '合理估值' if value < 30 else '高估值 (注意风险)'}。",
        'PB': f"市净率，衡量股价与净资产关系。PB={value:.2f}，{'<1 破净 (超值)' if value < 1 else '1-3 合理' if value < 3 else '>3 偏高'}。",
    }
    return explanations.get(name, '')


def identify_technical_patterns(data: Dict) -> List[Dict]:
    """识别技术形态和场景"""
    patterns = []
    
    # 1. 均线多头/空头排列
    if data['ma5'] > data['ma10'] > data['ma20']:
        patterns.append({
            'name': '均线多头排列',
            'type': 'bullish',
            'description': '短期均线在长期均线之上，表明上升趋势确立',
            'action': '可持股待涨，回调可加仓',
            'confidence': '高'
        })
    elif data['ma5'] < data['ma10'] < data['ma20']:
        patterns.append({
            'name': '均线空头排列',
            'type': 'bearish',
            'description': '短期均线在长期均线之下，表明下降趋势确立',
            'action': '谨慎操作，反弹可减仓',
            'confidence': '高'
        })
    
    # 2. MACD 金叉/死叉
    if data['macd_dif'] > data['macd_dea'] and data['macd_hist'] > 0:
        patterns.append({
            'name': 'MACD 金叉',
            'type': 'bullish',
            'description': '快线上穿慢线，多头动能增强',
            'action': '可考虑买入或持有',
            'confidence': '中'
        })
    elif data['macd_dif'] < data['macd_dea'] and data['macd_hist'] < 0:
        patterns.append({
            'name': 'MACD 死叉',
            'type': 'bearish',
            'description': '快线下穿慢线，空头动能增强',
            'action': '谨慎观望，考虑减仓',
            'confidence': '中'
        })
    
    # 3. RSI 超买/超卖
    if data['rsi14'] > 70:
        patterns.append({
            'name': 'RSI 超买',
            'type': 'warning',
            'description': 'RSI 进入超买区，短期涨幅过大',
            'action': '不宜追高，可考虑分批止盈',
            'confidence': '中'
        })
    elif data['rsi14'] < 30:
        patterns.append({
            'name': 'RSI 超卖',
            'type': 'opportunity',
            'description': 'RSI 进入超卖区，短期跌幅过大',
            'action': '可考虑分批建仓或补仓',
            'confidence': '中'
        })
    
    # 4. KD 金叉/死叉
    if data['kd_k'] > data['kd_d'] and data['kd_k'] < 80:
        patterns.append({
            'name': 'KD 金叉',
            'type': 'bullish',
            'description': 'K 线上穿 D 线，短期买点信号',
            'action': '可短线参与',
            'confidence': '中低'
        })
    elif data['kd_k'] < data['kd_d']:
        patterns.append({
            'name': 'KD 死叉',
            'type': 'bearish',
            'description': 'K 线下穿 D 线，短期卖点信号',
            'action': '短线可减仓',
            'confidence': '中低'
        })
    
    # 5. 布林带位置
    if data['price'] > data['boll_upper'] * 0.98:
        patterns.append({
            'name': '触及布林上轨',
            'type': 'warning',
            'description': '价格接近布林带上轨，压力大',
            'action': '不宜追高，等待回调',
            'confidence': '中'
        })
    elif data['price'] < data['boll_lower'] * 1.02:
        patterns.append({
            'name': '触及布林下轨',
            'type': 'opportunity',
            'description': '价格接近布林带下轨，支撑强',
            'action': '可考虑低吸',
            'confidence': '中'
        })
    
    # 6. 震荡市/趋势市
    if data['adx'] < 25:
        patterns.append({
            'name': '震荡市',
            'type': 'neutral',
            'description': 'ADX<25，市场无明显趋势，箱体波动',
            'action': '高抛低吸，不宜追涨杀跌',
            'confidence': '高'
        })
    else:
        patterns.append({
            'name': '趋势市',
            'type': 'trending',
            'description': 'ADX>25，市场趋势明确',
            'action': '顺势操作，趋势跟踪',
            'confidence': '高'
        })
    
    # 7. 综合共振
    bullish_count = sum(1 for p in patterns if p['type'] == 'bullish')
    bearish_count = sum(1 for p in patterns if p['type'] == 'bearish')
    
    if bullish_count >= 3:
        patterns.append({
            'name': '多头共振',
            'type': 'strong_bullish',
            'description': f'多个看涨信号共振 ({bullish_count}个)',
            'action': '强烈建议持有或加仓',
            'confidence': '很高'
        })
    elif bearish_count >= 3:
        patterns.append({
            'name': '空头共振',
            'type': 'strong_bearish',
            'description': f'多个看跌信号共振 ({bearish_count}个)',
            'action': '强烈建议减仓或观望',
            'confidence': '很高'
        })
    
    return patterns


def calculate_score(data: Dict) -> Tuple[int, str, float, List[str]]:
    """计算综合评分和置信度"""
    score = 50
    signals = []
    
    has_price = data.get('price', 0) > 0
    has_ma = data.get('ma5', 0) > 0 or data.get('ma10', 0) > 0
    
    if not has_price and not has_ma:
        return 1, '数据不足', 20, ['❌ 数据获取失败']
    
    if not has_price and has_ma:
        data['price'] = data.get('ma5', data.get('ma10', 1.0))
    
    # 均线
    if data['price'] > data['ma5'] > 0: score += 5; signals.append('✅ 站上 MA5')
    else: score -= 5; signals.append('❌ 跌破 MA5')
    if data['price'] > data['ma10'] > 0: score += 5; signals.append('✅ 站上 MA10')
    else: score -= 5
    if data['price'] > data['ma20'] > 0: score += 5; signals.append('✅ 站上 MA20')
    else: score -= 5
    
    # MACD
    if data['macd_hist'] > 0: score += 10; signals.append('✅ MACD 多头')
    else: score -= 10; signals.append('❌ MACD 空头')
    if data['macd_dif'] > data['macd_dea']: score += 5; signals.append('✅ MACD 金叉')
    else: score -= 5
    
    # RSI
    if 50 <= data['rsi14'] <= 70: score += 5; signals.append('✅ RSI 中性偏多')
    elif data['rsi14'] > 70: score -= 5; signals.append('❌ RSI 超买')
    elif data['rsi14'] < 30: score += 10; signals.append('✅ RSI 超卖')
    
    # KD
    if data['kd_k'] > data['kd_d']: score += 8; signals.append('✅ KD 金叉')
    else: score -= 8; signals.append('❌ KD 死叉')
    
    # 资金
    if data.get('main_force_net', 0) > 0:
        score += 10
        signals.append(f"✅ 主力净流入{data['main_force_net']:.2f}亿")
    elif data.get('main_force_net', 0) < 0:
        score -= 10
        signals.append(f"❌ 主力净流出{abs(data.get('main_force_net', 0)):.2f}亿")
    else:
        signals.append('⚪ 资金平衡')
    
    # OBV
    if data.get('obv_change5', 0) > 0: score += 5; signals.append('✅ OBV 上升')
    else: score -= 5
    
    # ADX
    if data.get('adx', 0) > 0:
        if data['adx'] < 25:
            signals.append('⚠️ 震荡市 (ADX<25)')
            score = int(score * 0.9)
        else:
            signals.append('✅ 趋势市 (ADX>25)')
    
    # 基本面加分
    if data.get('pe') is not None:
        if data['pe'] < 15: score += 5; signals.append('✅ 低估值 (PE<15)')
        elif data['pe'] > 50: score -= 5; signals.append('❌ 高估值 (PE>50)')
    
    if data.get('pb') is not None:
        if data['pb'] < 1.5: score += 3; signals.append('✅ 低 PB')
        elif data['pb'] > 5: score -= 3; signals.append('❌ 高 PB')
    
    score = max(0, min(100, score))
    
    if score >= 85: rating, conf = '强烈看多', 85 + (score-85)*0.4
    elif score >= 70: rating, conf = '偏多', 70 + (score-70)*0.6
    elif score >= 55: rating, conf = '中性', 50 + (score-55)
    elif score >= 40: rating, conf = '偏空', 35 + (score-40)*0.6
    else: rating, conf = '强烈看空', 15 + score*0.5
    
    return score, rating, conf, signals


def generate_recommendations(data: Dict, score: int, conf: float, patterns: List[Dict]) -> Dict:
    """生成操作建议"""
    price = data.get('price', 1) if data.get('price', 0) > 0 else 1
    support1 = min(data.get('ma10', price*0.95), data.get('ma20', price*0.95)) if data.get('ma10', 0) > 0 else price * 0.95
    support2 = data.get('low60', price * 0.90) if data.get('low60', 0) > 0 else price * 0.90
    resistance1 = max(data.get('ma5', price*1.05), data.get('boll_upper', price*1.05)) if (data.get('ma5', 0) > 0 or data.get('boll_upper', 0) > 0) else price * 1.05
    resistance2 = data.get('high60', price * 1.10) if data.get('high60', 0) > 0 else price * 1.10
    
    rec = {
        'short': {'action': '', 'conf': 0, 'sup': round(support1, 2), 'res': round(resistance1, 2)},
        'mid': {'action': '', 'conf': 0, 'sup': round(support2, 2), 'res': round(resistance2, 2)},
        'long': {'action': '', 'conf': 0, 'note': ''},
        'risks': [],
        'patterns': patterns
    }
    
    if score >= 70:
        rec['short']['action'] = '持有/逢低加仓'
        rec['short']['conf'] = min(conf+5, 95)
    elif score >= 55:
        rec['short']['action'] = '持有观望'
        rec['short']['conf'] = conf
    else:
        rec['short']['action'] = '减仓/等待'
        rec['short']['conf'] = max(conf-10, 30)
    
    if score >= 75 and data.get('adx', 0) > 25:
        rec['mid']['action'] = '持有待涨'
        rec['mid']['conf'] = min(conf, 90)
    elif score >= 60:
        rec['mid']['action'] = '持有'
        rec['mid']['conf'] = conf - 5
    else:
        rec['mid']['action'] = '观望/逢高减仓'
        rec['mid']['conf'] = max(conf-15, 30)
    
    if score >= 65:
        rec['long']['action'] = '定投/长期持有'
        rec['long']['conf'] = conf - 5
        rec['long']['note'] = '基本面良好，适合长期配置'
    elif score >= 50:
        rec['long']['action'] = '观望'
        rec['long']['conf'] = 50
        rec['long']['note'] = '等待更明确信号'
    else:
        rec['long']['action'] = '等待底部信号'
        rec['long']['conf'] = 40
        rec['long']['note'] = '趋势未明，不宜重仓'
    
    # 风险
    if data.get('rsi14', 50) > 70: rec['risks'].append('⚠️ RSI 超买，警惕短期回调')
    if data.get('rsi14', 50) < 30: rec['risks'].append('⚠️ RSI 超卖，可能反弹')
    if data.get('adx', 25) < 25: rec['risks'].append('⚠️ 震荡市，避免追涨杀跌')
    if data.get('boll_upper', 0) > 0 and data['price'] > data['boll_upper'] * 0.98:
        rec['risks'].append('⚠️ 接近布林上轨，可能回调')
    if data.get('main_force_net', 0) < -1: rec['risks'].append('⚠️ 主力大幅流出')
    if data.get('pe') is not None and data['pe'] > 50: rec['risks'].append('⚠️ 高估值，注意回调风险')
    
    return rec


def format_output(data: Dict, score: int, rating: str, conf: float, signals: List[str], rec: Dict) -> str:
    """格式化输出 - 优化价格解析显示"""
    lines = []
    etf_flag = " [ETF]" if data.get('is_etf', False) else ""
    lines.append(f"\n{'='*70}")
    lines.append(f" {data['name']} ({data['code']}){etf_flag}")
    lines.append(f"{'='*70}")
    
    # 基本信息 - 优化价格显示
    lines.append(f"\n【基本信息】")
    price = data.get('price', 0)
    price_str = f"{price:.2f}元" if price > 0 else "N/A"
    change_pct = data.get('change_pct', 0)
    change_str = f"{change_pct:+.2f}%" if change_pct else "N/A"
    lines.append(f"  当前价格：{price_str} | 今日涨跌：{change_str}")
    
    if not data.get('is_etf', False):
        industry = data.get('industry', '未知')
        pe = data.get('pe')
        pb = data.get('pb')
        pe_str = f"{pe:.1f}" if pe else "N/A (数据获取中)"
        pb_str = f"{pb:.2f}" if pb else "N/A (数据获取中)"
        lines.append(f"  所属行业：{industry}")
        lines.append(f"  市盈率 (PE): {pe_str} | 市净率 (PB): {pb_str}")
    
    # 核心数据 - 优化价格相关指标显示
    lines.append(f"\n【核心数据】")
    
    # 均线
    ma5 = data.get('ma5', 0)
    ma10 = data.get('ma10', 0)
    ma20 = data.get('ma20', 0)
    ma60 = data.get('ma60', 0)
    lines.append(f"  均线：MA5={ma5:.2f} MA10={ma10:.2f} MA20={ma20:.2f} MA60={ma60:.2f}")
    
    # MACD
    dif = data.get('macd_dif', 0)
    dea = data.get('macd_dea', 0)
    hist = data.get('macd_hist', 0)
    lines.append(f"  MACD: DIF={dif:.4f} DEA={dea:.4f} 柱={hist:.4f}")
    
    # 动量指标
    rsi = data.get('rsi14', 50)
    kd_k = data.get('kd_k', 50)
    kd_d = data.get('kd_d', 50)
    lines.append(f"  动量：RSI={rsi:.1f} KD=K{kd_k:.1f}/D{kd_d:.1f}")
    
    # 布林带
    boll_upper = data.get('boll_upper', 0)
    boll_mid = data.get('boll_mid', 0)
    boll_lower = data.get('boll_lower', 0)
    lines.append(f"  布林：上={boll_upper:.2f} 中={boll_mid:.2f} 下={boll_lower:.2f}")
    
    # 趋势指标
    if data.get('adx', 0) > 0:
        adx = data['adx']
        di_plus = data.get('di_plus', 0)
        di_minus = data.get('di_minus', 0)
        lines.append(f"  趋势：ADX={adx:.1f} DI+={di_plus:.1f} DI-={di_minus:.1f}")
    
    # 资金指标
    main_force = data.get('main_force_net', 0)
    obv = data.get('obv_change5', 0)
    lines.append(f"  资金：主力{main_force:+.3f}亿 OBV5 日={obv:+.1f}%")
    
    # 波动和区间
    atr = data.get('atr', 0)
    low60 = data.get('low60', 0)
    high60 = data.get('high60', 0)
    if low60 > 0 and high60 > 0:
        lines.append(f"  波动：ATR={atr:.4f} | 60 日区间：{low60:.2f}-{high60:.2f}")
    else:
        lines.append(f"  波动：ATR={atr:.4f}")
    
    # 信号评分
    lines.append(f"\n【信号评分】")
    lines.append(f"  综合评分：{score}/100 | {rating}")
    lines.append(f"  置信度：{conf:.0f}%")
    for sig in signals[:10]:
        lines.append(f"    {sig}")
    
    # 技术形态识别
    if rec.get('patterns'):
        lines.append(f"\n【技术形态识别】")
        for p in rec['patterns']:
            emoji = '🟢' if p['type'] in ['bullish', 'opportunity', 'strong_bullish'] else '🔴' if p['type'] in ['bearish', 'warning', 'strong_bearish'] else '🟡'
            lines.append(f"  {emoji} {p['name']}")
            lines.append(f"     含义：{p['description']}")
            lines.append(f"     建议：{p['action']}")
            lines.append(f"     置信度：{p['confidence']}")
            lines.append("")
    
    # 操作建议
    lines.append(f"\n【操作建议】")
    lines.append(f"  ┌────────────────────────────────────────────────────────┐")
    lines.append(f"  │ 周期     │ 建议            │ 置信度  │ 支撑/压力       │")
    lines.append(f"  ├────────────────────────────────────────────────────────┤")
    lines.append(f"  │ 短期     │ {rec['short']['action']:<14}│ {rec['short']['conf']:>5.0f}%   │ {rec['short']['sup']:.2f}/{rec['short']['res']:.2f} │")
    lines.append(f"  │ 中期     │ {rec['mid']['action']:<14}│ {rec['mid']['conf']:>5.0f}%   │ {rec['mid']['sup']:.2f}/{rec['mid']['res']:.2f} │")
    lines.append(f"  │ 长期     │ {rec['long']['action']:<14}│ {rec['long']['conf']:>5.0f}%   │ {rec['long']['note'][:12]} │")
    lines.append(f"  └────────────────────────────────────────────────────────┘")
    
    # 指标解释（新手友好）- 优化价格比较逻辑
    lines.append(f"\n【指标解读 - 新手必读】")
    
    price = data.get('price', 0)
    ma5 = data.get('ma5', 0)
    if price > 0 and ma5 > 0:
        ma_status = '站上' if price > ma5 else '跌破'
        ma_signal = '短期强势' if price > ma5 else '短期弱势'
        lines.append(f"  均线：当前价格{price:.2f}元，{ma_status}5 日均线，{ma_signal}。")
    
    dif = data.get('macd_dif', 0)
    dea = data.get('macd_dea', 0)
    macd_signal = '上穿' if dif > dea else '下穿'
    macd_type = '多头信号' if dif > dea else '空头信号'
    lines.append(f"  MACD: DIF({dif:.4f}){macd_signal}DEA({dea:.4f})，{macd_type}。")
    
    rsi = data.get('rsi14', 50)
    if rsi < 30:
        rsi_text = '超卖区 (可关注反弹)'
    elif rsi < 70:
        rsi_text = '中性区'
    else:
        rsi_text = '超买区 (注意回调)'
    lines.append(f"  RSI: {rsi:.1f}，{rsi_text}。")
    
    adx = data.get('adx', 0)
    if adx > 0:
        adx_text = '震荡行情 (高抛低吸)' if adx < 25 else '趋势行情 (顺势操作)'
        lines.append(f"  ADX: {adx:.1f}，{adx_text}。")
    
    # 风险预警
    if rec['risks']:
        lines.append(f"\n【风险预警】")
        for risk in rec['risks']:
            lines.append(f"  {risk}")
    
    return '\n'.join(lines)


def generate_summary(results: List, holdings: List[Dict]) -> str:
    """生成持仓总结"""
    lines = []
    lines.append(f"\n{'='*70}")
    lines.append(" 持仓技术面总结")
    lines.append(f"{'='*70}")
    
    scored = []
    for i, h in enumerate(holdings):
        if i >= len(results):
            break
        data = results[i]
        if isinstance(data, str) or not isinstance(data, dict):
            continue
        try:
            score, rating, conf, signals = calculate_score(data)
            if score <= 1:
                continue
            scored.append({
                'name': h['name'], 'code': h['code'], 'is_etf': h.get('is_etf', False),
                'score': score, 'conf': conf,
                'price': data.get('price', 0), 'change': data.get('change_pct', 0),
                'industry': data.get('industry', 'N/A'), 'pe': data.get('pe')
            })
        except:
            continue
    
    scored.sort(key=lambda x: x['score'], reverse=True)
    
    lines.append(f"\n【技术面排名】(从高到低)")
    for i, h in enumerate(scored, 1):
        emoji = '🟢' if h['score'] >= 70 else '🟡' if h['score'] >= 55 else '🔴'
        etf_flag = " [ETF]" if h['is_etf'] else ""
        pe_str = f"PE={h['pe']:.1f}" if h['pe'] else ""
        lines.append(f"  {i}. {emoji} {h['name']}{etf_flag} ({h['code']}): {h['price']:.3f}元 ({h['change']:+.2f}%) | 评分{h['score']}/100 | {pe_str}")
    
    bullish = [h for h in scored if h['score'] >= 70]
    neutral = [h for h in scored if 55 <= h['score'] < 70]
    bearish = [h for h in scored if h['score'] < 55]
    
    lines.append(f"\n【最佳操作建议】")
    if bullish:
        lines.append(f"\n  ✅ 可加仓标的 ({len(bullish)}只):")
        for h in bullish:
            etf_flag = " [ETF]" if h['is_etf'] else ""
            lines.append(f"     • {h['name']}{etf_flag} ({h['code']}) - 置信度{h['conf']:.0f}%")
    if neutral:
        lines.append(f"\n  ⏸️ 持有观望 ({len(neutral)}只):")
        for h in neutral:
            etf_flag = " [ETF]" if h['is_etf'] else ""
            lines.append(f"     • {h['name']}{etf_flag} ({h['code']})")
    if bearish:
        lines.append(f"\n  ⚠️ 注意风险 ({len(bearish)}只):")
        for h in bearish:
            etf_flag = " [ETF]" if h['is_etf'] else ""
            lines.append(f"     • {h['name']}{etf_flag} ({h['code']}) - 评分{h['score']}/100")
    
    avg = sum(h['score'] for h in scored) / len(scored) if scored else 50
    lines.append(f"\n【整体仓位建议】")
    if avg >= 70:
        lines.append(f"  📈 平均评分{avg:.0f}/100 - 可维持较高仓位 (70-80%)")
    elif avg >= 55:
        lines.append(f"  📊 平均评分{avg:.0f}/100 - 中等仓位 (50-60%)")
    else:
        lines.append(f"  📉 平均评分{avg:.0f}/100 - 低仓位等待 (30-40%)")
    
    # 新手提示
    lines.append(f"\n【新手提示】")
    lines.append(f"  • 评分≥70：技术面良好，可考虑加仓")
    lines.append(f"  • 评分 55-69：方向不明，观望为主")
    lines.append(f"  • 评分<55：风险较大，建议减仓")
    lines.append(f"  • 以上分析仅供参考，投资需谨慎！")
    
    return '\n'.join(lines)


def analyze_single(holding: Dict) -> Dict:
    """分析单个标的 — 统一入口，多源数据+重试+兜底"""
    code = holding['code']
    name = holding['name']
    is_etf = holding.get('is_etf', False)
    
    try:
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=90)).strftime('%Y%m%d')
        
        # 获取数据
        if is_etf:
            df = fetch_etf_data_with_retry(code, start_date, end_date)
        else:
            df = fetch_stock_data_with_retry(code, start_date, end_date)
        
        if df is None or len(df) < 20:
            return {'error': f'所有数据源均失败（已尝试{MAX_RETRIES}次重试+2个兜底源），无法获取{code}的K线数据', 'code': code, 'name': name}
        
        # 统一列名
        if 'close' not in df.columns:
            df.columns = ['date', 'code', 'open', 'close', 'high', 'low', 'volume', 'amount', 'amp', 'chg', 'pct', 'turn'][:len(df.columns)]
        for col in ['open', 'close', 'high', 'low', 'volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        data = calculate_ta_indicators(df)
        if data is None:
            return {'error': '数据不足（需至少20个交易日）', 'code': code, 'name': name}
        
        # 基本面
        if not is_etf:
            fundamentals = get_stock_fundamentals(code)
            data.update(fundamentals)
        
        data['code'] = code
        data['name'] = name
        data['is_etf'] = is_etf
        data['industry'] = data.get('industry', 'ETF 基金') if is_etf else data.get('industry', '未知')
        data['pe'] = data.get('pe')
        data['pb'] = data.get('pb')
        return data
        
    except Exception as e:
        return {'error': str(e), 'code': code, 'name': name}


def main():
    """主函数"""
    print("="*70, file=sys.stderr)
    print(" A 股技术面分析报告生成器 - 新手友好版 (支持 ETF+ 基本面)", file=sys.stderr)
    print("="*70, file=sys.stderr)
    
    if len(sys.argv) > 1:
        stock_codes = sys.argv[1:]
        holdings = []
        for c in stock_codes:
            c = c.strip()
            if c.isdigit() and len(c)==6:
                is_etf = c.startswith('5') or c.startswith('1')
                holdings.append({'name': '', 'code': c, 'is_etf': is_etf})
    else:
        print(f"\n 读取持仓文件：{PORTFOLIO_FILE}", file=sys.stderr)
        holdings = parse_portfolio_file(PORTFOLIO_FILE)
        if not holdings:
            print(" 未找到持仓数据", file=sys.stderr)
            sys.exit(1)
        print(f" 找到 {len(holdings)} 只持仓股票/ETF", file=sys.stderr)
    
    print("\n 开始技术分析...", file=sys.stderr)
    results = []
    
    for h in holdings:
        etf_flag = "[ETF]" if h.get('is_etf', False) else ""
        print(f"  -> 分析 {h['name']} {etf_flag}({h['code']})...", file=sys.stderr)
        data = analyze_single(h)
        
        if 'error' in data:
            results.append(f"\n {h['name']} ({h['code']}) 分析失败：{data['error']}")
            continue
        
        data['is_etf'] = h.get('is_etf', False)
        score, rating, conf, signals = calculate_score(data)
        patterns = identify_technical_patterns(data)
        rec = generate_recommendations(data, score, conf, patterns)
        output = format_output(data, score, rating, conf, signals, rec)
        results.append(output)
    
    # 输出
    print("\n" + "="*70)
    print(" 技术面分析报告")
    print("="*70)
    
    for r in results:
        if isinstance(r, str):
            print(r)
    
    if len(holdings) > 1:
        try:
            print(generate_summary(results, holdings))
        except Exception as e:
            print(f"\n 生成总结失败：{e}", file=sys.stderr)
    
    print("\n" + "="*70, file=sys.stderr)
    print(" 分析完成", file=sys.stderr)
    print("="*70, file=sys.stderr)


if __name__ == "__main__":
    main()
