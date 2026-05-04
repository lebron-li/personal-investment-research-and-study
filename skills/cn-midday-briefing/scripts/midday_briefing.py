#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A 股午间快报 — 每交易日 11:35 自动运行
结合近期日K技术面 + 当天上午分时走势，输出轻量快报和下午操作提示
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import re
import time
import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from ta_utils import calculate_ta_indicators, calculate_score, get_top_signals

# 路径配置
SCRIPT_DIR = Path(__file__).parent
SKILL_DIR = SCRIPT_DIR.parent
PORTFOLIO_FILE = Path(r"C:\agent\03-portfolio-tools\my-holdings.txt")
OUTPUT_DIR = Path(r"C:\agent\07-investment-suggestion\short-term-builder-weekly")
STATE_FILE = SCRIPT_DIR / "midday_state.json"

# 重试配置
MAX_RETRIES = 5
RETRY_DELAY = 2  # 基础等待秒数（会指数增长）

# A股交易时间
MORNING_OPEN = (9, 30)
MORNING_CLOSE = (11, 30)


# ══════════════════════════════════════════════════════════════
# 持仓解析
# ══════════════════════════════════════════════════════════════

def parse_portfolio() -> List[Dict[str, str]]:
    """解析持仓文件"""
    holdings = []
    if not PORTFOLIO_FILE.exists():
        print(f"⚠️ 持仓文件不存在: {PORTFOLIO_FILE}", file=sys.stderr)
        return holdings

    with open(PORTFOLIO_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 2:
                name = parts[1] if len(parts) == 2 else ' '.join(parts[1:-1])
                code_match = re.search(r'\d{6}', parts[-1])
                if code_match:
                    code = code_match.group()
                    is_etf = code.startswith('5') or code.startswith('1')
                    holdings.append({'name': name, 'code': code, 'is_etf': is_etf})
    return holdings


# ══════════════════════════════════════════════════════════════
# 数据获取（东方财富 HTTP API，去除 akshare 依赖）
# ══════════════════════════════════════════════════════════════

def _make_session():
    import requests as req
    s = req.Session()
    s.trust_env = False
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://quote.eastmoney.com/',
    })
    return s


def _retry_delay(attempt: int) -> float:
    """指数退避等待：2s, 4s, 8s, 16s, 32s"""
    return min(RETRY_DELAY * (2 ** attempt), 60)


def _try_eastmoney_kline(secid: str, start_date: str, end_date: str, klt: str = '101') -> Optional[pd.DataFrame]:
    """尝试东方财富 K 线接口，带 5 次重试 + 指数退避 + 重启 session"""
    import requests as req
    
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            s = _make_session()
            r = s.get('https://push2his.eastmoney.com/api/qt/stock/kline/get', params={
                'fields1': 'f1,f2,f3,f4,f5,f6',
                'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116',
                'ut': '7eea3edcaed734bea9cbfc24409ed989',
                'klt': klt, 'fqt': '1',
                'secid': secid,
                'beg': start_date, 'end': end_date
            }, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if data.get('data') and data['data'].get('klines'):
                    records = []
                    for kline in data['data']['klines']:
                        parts = kline.split(',')
                        if len(parts) >= 6:
                            records.append({
                                'date' if klt == '101' else 'time': parts[0],
                                'open': float(parts[1]),
                                'close': float(parts[2]),
                                'high': float(parts[3]),
                                'low': float(parts[4]),
                                'volume': float(parts[5])
                            })
                    if records:
                        return pd.DataFrame(records)
            else:
                last_error = f'HTTP {r.status_code}'
        except Exception as e:
            last_error = str(e)[:80]

        if attempt < MAX_RETRIES - 1:
            delay = _retry_delay(attempt)
            print(f"    东方财富第{attempt+1}次失败 ({last_error})，{delay:.0f}s后重试...", file=sys.stderr)
            time.sleep(delay)

    print(f"    东方财富全部{MAX_RETRIES}次失败，启用兜底...", file=sys.stderr)
    return None


def _try_sina_kline(code: str) -> Optional[pd.DataFrame]:
    """兜底源1：新浪财经（重试3次）"""
    market = 'sh' if code.startswith('6') else 'sz'
    for attempt in range(3):
        try:
            s = _make_session()
            r = s.get(
                'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData',
                params={'symbol': f'{market}{code}', 'scale': '240', 'ma': 'no', 'datalen': '100'},
                timeout=15
            )
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
                    print(f"    新浪兜底成功，{len(records)}条", file=sys.stderr)
                    return pd.DataFrame(records)
        except:
            if attempt < 2:
                time.sleep(2)
    return None


def _try_akshare_kline(code: str, start_date: str, end_date: str, is_etf: bool) -> Optional[pd.DataFrame]:
    """兜底源2：akshare（如已安装）"""
    try:
        import akshare as ak
        if is_etf:
            df = ak.fund_etf_hist_em(symbol=code, period='daily', start_date=start_date, end_date=end_date)
        else:
            df = ak.stock_zh_a_hist(symbol=code, period='daily', start_date=start_date, end_date=end_date)
        if df is not None and len(df) >= 20:
            # 统一列名
            col_map = {c: c.lower() for c in df.columns}
            df = df.rename(columns=col_map)
            for col in ['open', 'close', 'high', 'low', 'volume']:
                if col not in df.columns:
                    for c2 in df.columns:
                        if col in c2:
                            df = df.rename(columns={c2: col})
                            break
            if 'close' in df.columns:
                print(f"    akshare兜底成功，{len(df)}条", file=sys.stderr)
                return df
    except Exception as e:
        print(f"    akshare兜底失败: {str(e)[:60]}", file=sys.stderr)
    return None


def fetch_daily_kline(code: str, start_date: str, end_date: str, is_etf: bool = False) -> Optional[pd.DataFrame]:
    """获取日K线数据 — 多层兜底：东方财富 → 新浪 → akshare"""
    if is_etf:
        secid = f'1.{code}'
    else:
        market_id = '1' if code.startswith('6') else '0'
        secid = f'{market_id}.{code}'

    # 源1：东方财富（5次重试 + 指数退避）
    df = _try_eastmoney_kline(secid, start_date, end_date, klt='101')
    if df is not None and len(df) >= 20:
        return df

    # 源2：新浪财经
    df = _try_sina_kline(code)
    if df is not None and len(df) >= 20:
        return df

    # 源3：akshare
    df = _try_akshare_kline(code, start_date, end_date, is_etf)
    if df is not None and len(df) >= 20:
        return df

    return None


def fetch_intraday_5min(code: str, is_etf: bool = False) -> Optional[pd.DataFrame]:
    """获取当天分时K线 — 优先5分钟，兜底1分钟"""
    today = datetime.now().strftime('%Y%m%d')
    if is_etf:
        secid = f'1.{code}'
    else:
        market_id = '1' if code.startswith('6') else '0'
        secid = f'{market_id}.{code}'

    # 尝试 5 分钟K线
    df = _try_eastmoney_kline(secid, today, today, klt='5')
    if df is not None and len(df) > 0:
        return df

    # 兜底：1 分钟K线
    df = _try_eastmoney_kline(secid, today, today, klt='1')
    if df is not None and len(df) > 0:
        return df

    return None


def fetch_recent_5min(code: str, is_etf: bool, days: int = 5) -> Optional[pd.DataFrame]:
    """获取最近几天的 5 分钟K线（用于计算近期上午量能均值）"""
    end = datetime.now().strftime('%Y%m%d')
    start = (datetime.now() - timedelta(days=days + 3)).strftime('%Y%m%d')
    if is_etf:
        secid = f'1.{code}'
    else:
        market_id = '1' if code.startswith('6') else '0'
        secid = f'{market_id}.{code}'

    return _try_eastmoney_kline(secid, start, end, klt='5')


def fetch_realtime_quote(code: str, is_etf: bool = False) -> Optional[Dict]:
    """获取实时行情报价 — 腾讯/新浪 API 兜底验证"""
    result = None
    
    # 源1: 腾讯行情 API（最可靠）
    market = 'sh' if code.startswith('6') else 'sz'
    try:
        s = _make_session()
        r = s.get(f'https://qt.gtimg.cn/q={market}{code}', timeout=8)
        if r.status_code == 200 and r.text:
            # 解析腾讯行情返回格式
            text = r.text
            # 格式: v_sh600036="1~招商银行~600036~39.38~39.60~..."
            parts = text.split('~')
            if len(parts) >= 10:
                result = {
                    'name': parts[1],
                    'code': parts[2],
                    'prev_close': float(parts[3]) if parts[3].replace('.','').replace('-','').isdigit() else None,
                    'current': float(parts[4]) if parts[4].replace('.','').replace('-','').isdigit() else None,
                    'source': 'tencent'
                }
    except:
        pass

    # 源2: 新浪实时行情 API（兜底）
    if result is None or result.get('prev_close') is None:
        try:
            s = _make_session()
            r = s.get(f'https://hq.sinajs.cn/list={market}{code}', timeout=8, 
                       headers={'Referer': 'https://finance.sina.com.cn'})
            if r.status_code == 200 and r.text:
                # 格式: var hq_str_sh600036="招商银行,39.380,39.600,..."
                text = r.text.split('"')[1] if '"' in r.text else ''
                parts = text.split(',')
                if len(parts) >= 3:
                    result = {
                        'name': parts[0],
                        'prev_close': float(parts[2]) if parts[2].replace('.','').replace('-','').isdigit() else None,
                        'current': float(parts[3]) if parts[3].replace('.','').replace('-','').isdigit() else None,
                        'source': 'sina'
                    }
        except:
            pass
    
    return result


# ══════════════════════════════════════════════════════════════
# 前收盘价获取（修复核心bug）
# ══════════════════════════════════════════════════════════════

def get_prev_close(df_daily: pd.DataFrame) -> float:
    """
    从日K数据中显式找前一个自然日的收盘价，而不是盲目用 iloc[-1]。

    问题背景：不同API源/不同标的返回的日K线最新日期可能不一致。
    如果最新日期 == 今天（当天日K已生成），iloc[-1] 取到的是当天收盘价，
    在上午时段这是错误的——应该取前一日的收盘价。

    逻辑：
    - 检查日K数据的日期列，找到最大日期（最新日期）
    - 如果最新日期 == 今天（strftime('%Y-%m-%d')）且行数>1，用 iloc[-2]（倒数第二行）
    - 如果最新日期在昨天或更早，用 iloc[-1]（就是数据中最新的）
    - 无论如何都返回 float
    """
    today_str = datetime.now().strftime('%Y-%m-%d')
    # 找到日期列（可能是 'date' 或 'time'）
    date_col = None
    for col in ['date', 'time']:
        if col in df_daily.columns:
            date_col = col
            break

    if date_col:
        # 获取最新日期（字符串形式，取前10字符即 YYYY-MM-DD）
        latest_date_str = str(df_daily[date_col].iloc[-1])[:10]
        if latest_date_str == today_str and len(df_daily) > 1:
            # 最新日期是今天，取前一日的收盘价
            return float(df_daily['close'].iloc[-2])

    # 默认：最新一条就是前一日
    return float(df_daily['close'].iloc[-1])


# ══════════════════════════════════════════════════════════════
# 数据校验层
# ══════════════════════════════════════════════════════════════

def validate_data(morning: Dict, prev_close: float, name: str, code: str) -> List[str]:
    """校验数据合理性，返回警告列表"""
    warnings = []
    if morning.get('prev_close') and abs(morning['prev_close'] - prev_close) > prev_close * 0.02:
        warnings.append(f"⚠️ 前收盘价校验偏差过大：快报={morning['prev_close']:.3f}, 日K={prev_close:.3f}")
    if morning.get('chg_pct') and abs(morning['chg_pct']) < 0.001:
        warnings.append("⚠️ 上午涨跌幅接近0%，可能数据未更新")
    return warnings


# ══════════════════════════════════════════════════════════════
# 上午走势分析
# ══════════════════════════════════════════════════════════════

def analyze_morning(df_intraday: pd.DataFrame, prev_close: float,
                    df_recent_5min: Optional[pd.DataFrame] = None) -> Dict:
    """分析上午走势"""
    if df_intraday is None or len(df_intraday) == 0:
        return {'error': '无上午分时数据'}

    # 筛选上午时段 (9:30-11:30)
    morning_data = df_intraday[df_intraday['time'].str.contains(r' 09:| 10:| 11:')]

    if len(morning_data) == 0:
        # 检查是否有今天的数据（可能时间格式不同）
        today_str = datetime.now().strftime('%Y-%m-%d')
        morning_data = df_intraday[df_intraday['time'].str.startswith(today_str)]

    if len(morning_data) == 0:
        return {'error': '无上午时段数据'}

    open_price = morning_data['open'].iloc[0]
    midday_price = morning_data['close'].iloc[-1]
    morning_high = morning_data['high'].max()
    morning_low = morning_data['low'].min()
    morning_volume = morning_data['volume'].sum()
    morning_range = (morning_high - morning_low) / open_price * 100 if open_price > 0 else 0
    chg_pct = (midday_price - prev_close) / prev_close * 100 if prev_close > 0 else 0
    open_gap = (open_price - prev_close) / prev_close * 100 if prev_close > 0 else 0

    # 走势形态：高开/低开后走势
    if open_gap > 0.5:
        open_desc = '高开'
    elif open_gap < -0.5:
        open_desc = '低开'
    else:
        open_desc = '平开'

    # 午间相对于开盘的方向
    midday_vs_open = (midday_price - open_price) / open_price * 100 if open_price > 0 else 0
    if midday_vs_open > 0.3:
        trend_desc = f'{open_desc}后走高'
    elif midday_vs_open < -0.3:
        trend_desc = f'{open_desc}后走低'
    else:
        trend_desc = f'{open_desc}后震荡'

    # 量能对比：计算近5日同上午时段平均成交量
    vol_ratio = None
    vol_desc = ''
    if df_recent_5min is not None and len(df_recent_5min) > 0:
        # 按日期分组，筛选上午时段的成交量
        df_recent_5min['date'] = df_recent_5min['time'].str[:10]
        recent_morning_vols = []
        for date, group in df_recent_5min.groupby('date'):
            morning = group[group['time'].str.contains(r' 09:| 10:| 11:')]
            if len(morning) > 0:
                recent_morning_vols.append(morning['volume'].sum())

        if len(recent_morning_vols) >= 2:
            avg_vol = np.mean(recent_morning_vols[:-1])  # 排除今天（最后一天）
            if avg_vol > 0:
                vol_ratio = morning_volume / avg_vol
                if vol_ratio > 1.5:
                    vol_desc = '放量明显'
                elif vol_ratio > 1.1:
                    vol_desc = '略微放量'
                elif vol_ratio > 0.9:
                    vol_desc = '量能持平'
                elif vol_ratio > 0.6:
                    vol_desc = '略微缩量'
                else:
                    vol_desc = '缩量明显'

    result = {
        'open_price': open_price,
        'midday_price': midday_price,
        'morning_high': morning_high,
        'morning_low': morning_low,
        'morning_volume': morning_volume,
        'morning_range': morning_range,
        'chg_pct': chg_pct,
        'open_gap': open_gap,
        'open_desc': open_desc,
        'trend_desc': trend_desc,
        'midday_vs_open': midday_vs_open,
        'vol_ratio': vol_ratio,
        'vol_desc': vol_desc,
    }
    return result


# ══════════════════════════════════════════════════════════════
# 下午操作建议（支持强制差异化覆盖）
# ══════════════════════════════════════════════════════════════

def generate_afternoon_advice(morning: Dict, ta_score: int, ta_rating: str,
                               ta_data: Dict, ta_signals: List[str],
                               force_level: Optional[str] = None,
                               force_action: Optional[str] = None) -> Dict:
    """综合上午走势和技术面，生成下午操作建议。

    force_level / force_action 用于后处理强制差异化时覆盖评级。
    """
    advice = {'level': '', 'action': '', 'note': ''}

    # 如果被强制覆盖（差异化处理），直接使用强制值
    if force_level and force_action:
        advice['level'] = force_level
        advice['action'] = force_action
        # 特殊场景仍然附加
        if morning.get('morning_range', 0) > 3:
            advice['note'] = '上午振幅较大，下午波动可能加剧'
        return advice

    # 评分 + 上午走势综合
    if ta_score >= 70:
        if morning.get('chg_pct', 0) > 0 and morning.get('vol_ratio', 1) and morning['vol_ratio'] > 1.1:
            advice['level'] = '🟢 可操作'
            advice['action'] = '放量上涨，下午可持有或逢回调加仓'
        elif morning.get('midday_vs_open', 0) < -0.5:
            advice['level'] = '🟡 观望'
            advice['action'] = '上午冲高回落，下午等待企稳后再操作'
        else:
            advice['level'] = '🟢 可操作'
            advice['action'] = '技术面偏多，下午可继续持有'
    elif ta_score >= 55:
        if morning.get('chg_pct', 0) > 1:
            advice['level'] = '🟡 观望'
            advice['action'] = '涨幅已大但技术面中性，不宜追高'
        elif morning.get('chg_pct', 0) < -1:
            advice['level'] = '🔴 谨慎'
            advice['action'] = '跌幅较大且技术面中性，下午观望为主'
        else:
            advice['level'] = '🟡 观望'
            advice['action'] = '技术面方向不明，下午等待信号'
    else:
        advice['level'] = '🔴 谨慎'
        advice['action'] = '技术面偏空，下午不建议操作'
        if morning.get('chg_pct', 0) < -2:
            advice['action'] += '；急跌后可能有短线反弹，但风险较大'

    # 特殊场景
    if morning.get('morning_range', 0) > 3:
        advice['note'] = '上午振幅较大，下午波动可能加剧'

    return advice


# ══════════════════════════════════════════════════════════════
# 格式化输出
# ══════════════════════════════════════════════════════════════

def format_single_briefing(holding: Dict, morning: Dict, ta_data: Dict,
                            ta_score: int, ta_rating: str, ta_signals: List[str],
                            advice: Dict, warnings: Optional[List[str]] = None) -> str:
    """格式化单只标的的午间快报"""
    lines = []
    name = holding['name']
    code = holding['code']
    etf_flag = " [ETF]" if holding.get('is_etf') else ""
    industry = holding.get('industry', '')

    lines.append(f"\n{'─'*54}")
    lines.append(f" {name} ({code}){etf_flag}{' — ' + industry if industry else ''}")
    lines.append(f"{'─'*54}")

    # 数据校验警告
    if warnings:
        for w in warnings:
            lines.append(f"  {w}")

    # 上午复盘
    lines.append("【上午复盘】")
    prev_close_str = f"{morning.get('prev_close', 0):.2f}" if morning.get('prev_close') else 'N/A'
    open_str = f"{morning['open_price']:.2f}" if morning.get('open_price') else 'N/A'
    open_gap_str = f"{morning['open_gap']:+.2f}%" if morning.get('open_gap') is not None else ''
    midday_str = f"{morning['midday_price']:.2f}" if morning.get('midday_price') else 'N/A'

    lines.append(f"  前收 {prev_close_str} | 开盘 {open_str} ({open_gap_str}) | 午间 {midday_str}")

    if morning.get('morning_high') and morning.get('morning_low'):
        lines.append(f"  上午高 {morning['morning_high']:.2f} / 低 {morning['morning_low']:.2f}"
                     f" | 振幅 {morning.get('morning_range', 0):.2f}%")

    chg_str = f"{morning.get('chg_pct', 0):+.2f}%"
    trend_str = morning.get('trend_desc', '')
    vol_str = ''
    if morning.get('vol_ratio') is not None:
        vol_str = f" | 量能 {morning['vol_ratio']:.1f}x 近5日上午均值 ({morning.get('vol_desc', '')})"
    lines.append(f"  涨跌 {chg_str} | {trend_str}{vol_str}")

    # 技术快照
    lines.append(f"\n【技术快照】评分 {ta_score}/100 | {ta_rating}")
    top_sigs = get_top_signals(ta_signals, 4)
    lines.append(f"  {' | '.join(top_sigs)}")

    # 关键位置
    lines.append(f"\n【关键位置】")
    price = morning.get('midday_price', ta_data.get('price', 0))
    supports = []
    resistances = []

    # 支撑位
    for ma_name, ma_key in [('MA5', 'ma5'), ('MA10', 'ma10'), ('MA20', 'ma20'), ('MA60', 'ma60')]:
        ma_val = ta_data.get(ma_key, 0)
        if ma_val > 0 and price > ma_val:
            dist = (price - ma_val) / price * 100
            supports.append(f"{ma_name} {ma_val:.2f} (下方 {dist:.1f}%)")

    # 压力位
    for ma_name, ma_key in [('MA60', 'ma60'), ('MA20', 'ma20'), ('MA10', 'ma10'), ('MA5', 'ma5')]:
        ma_val = ta_data.get(ma_key, 0)
        if ma_val > 0 and price < ma_val:
            dist = (ma_val - price) / price * 100
            resistances.append(f"{ma_name} {ma_val:.2f} (上方 {dist:.1f}%)")

    if ta_data.get('boll_upper', 0) > price:
        dist = (ta_data['boll_upper'] - price) / price * 100
        resistances.append(f"布林上轨 {ta_data['boll_upper']:.2f} (上方 {dist:.1f}%)")
    if ta_data.get('boll_lower', 0) < price:
        dist = (price - ta_data['boll_lower']) / price * 100
        supports.append(f"布林下轨 {ta_data['boll_lower']:.2f} (下方 {dist:.1f}%)")

    if supports:
        lines.append(f"  支撑：{' | '.join(supports[-2:])}")
    if resistances:
        lines.append(f"  压力：{' | '.join(resistances[-2:])}")

    # 关键位突破提醒
    # 最近支撑
    nearest_support = None
    nearest_support_dist = 999
    for ma_name, ma_key in [('MA5', 'ma5'), ('MA10', 'ma10'), ('MA20', 'ma20'), ('MA60', 'ma60')]:
        ma_val = ta_data.get(ma_key, 0)
        if ma_val > 0 and price > ma_val:
            dist = price - ma_val
            if dist < nearest_support_dist:
                nearest_support_dist = dist
                nearest_support = (ma_name, ma_val)

    nearest_resistance = None
    nearest_resistance_dist = 999
    for ma_name, ma_key in [('MA5', 'ma5'), ('MA10', 'ma10'), ('MA20', 'ma20'), ('MA60', 'ma60')]:
        ma_val = ta_data.get(ma_key, 0)
        if ma_val > 0 and price < ma_val:
            dist = ma_val - price
            if dist < nearest_resistance_dist:
                nearest_resistance_dist = dist
                nearest_resistance = (ma_name, ma_val)

    # 下午关注
    focus_parts = []
    if nearest_support and (nearest_support_dist / price) < 0.02:
        focus_parts.append(f"支撑 {nearest_support[0]} {nearest_support[1]:.2f}")
    if nearest_resistance and (nearest_resistance_dist / price) < 0.02:
        focus_parts.append(f"压力 {nearest_resistance[0]} {nearest_resistance[1]:.2f}")

    if focus_parts:
        lines.append(f"  🎯 下午关注：{' / '.join(focus_parts)}")

    # 下午建议
    lines.append(f"\n【下午建议】{advice['level']} · {advice['action']}")
    if advice.get('note'):
        lines.append(f"  💡 {advice['note']}")

    return '\n'.join(lines)


def format_summary(results: List[Dict]) -> str:
    """生成下午操作速览总结"""
    lines = []
    lines.append(f"\n{'─'*54}")
    lines.append(" 📋 下午操作速览")
    lines.append(f"{'─'*54}")

    categories = {
        '🟢 可操作': [],
        '🟡 观望': [],
        '🔴 谨慎': [],
        '❌ 数据异常': [],
    }

    for r in results:
        if r.get('error'):
            categories['❌ 数据异常'].append(r['error'])
            continue
        level = r.get('advice', {}).get('level', '🟡 观望')
        name = r['holding']['name']
        code = r['holding']['code']
        categories[level].append(f"{code} {name}")

    for cat, items in categories.items():
        if items:
            lines.append(f"  {cat}：{'、'.join(items)}")

    # 整体建议
    scores = [r.get('ta_score', 50) for r in results if not r.get('error')]
    if scores:
        avg_score = sum(scores) / len(scores)
        if avg_score >= 70:
            overall = '上午走势配合技术面偏多，下午整体偏乐观，可适度操作'
        elif avg_score >= 55:
            overall = '方向不明，下午建议以观望为主，等待方向明确'
        else:
            overall = '技术面偏空，下午建议谨慎，控制仓位'
        lines.append(f"\n 💡 整体建议：{overall}")

    return '\n'.join(lines)


# ══════════════════════════════════════════════════════════════
# 交易日检查
# ══════════════════════════════════════════════════════════════

def is_trading_day() -> Tuple[bool, str]:
    """检查今日是否为A股交易日"""
    today = datetime.now()
    # 周末
    if today.weekday() >= 5:
        return False, '周末休市'

    # 检查时间：上午收盘后才有意义
    now = today.hour * 60 + today.minute
    if now < MORNING_CLOSE[0] * 60 + MORNING_CLOSE[1]:
        return False, '上午尚未收盘'

    # 简单交易日判断：尝试获取一只大盘股数据看今天有没有
    try:
        df = fetch_intraday_5min('600036', is_etf=False)
        if df is None or len(df) == 0:
            return False, '今日无交易数据（可能为节假日）'
    except:
        return True, ''  # 网络问题就假定交易日，让后续逻辑兜底

    return True, ''


# ══════════════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════════════

def main():
    print("=" * 54, file=sys.stderr)
    print(" A 股午间快报生成器", file=sys.stderr)
    print("=" * 54, file=sys.stderr)

    # 交易日检查
    is_trade, reason = is_trading_day()
    if not is_trade:
        print(f"\n⏸️ 跳过分析：{reason}", file=sys.stderr)
        print(f"\n⏸️ 今日{reason}，无需生成午间快报。")
        return

    # 解析持仓
    print(f"\n 读取持仓文件：{PORTFOLIO_FILE}", file=sys.stderr)
    holdings = parse_portfolio()
    if not holdings:
        print(" 未找到持仓数据", file=sys.stderr)
        sys.exit(1)
    print(f" 找到 {len(holdings)} 只持仓标的", file=sys.stderr)

    # 日期范围
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=90)).strftime('%Y%m%d')

    # 报告头
    today_str = datetime.now().strftime('%Y-%m-%d')
    weekday_map = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    weekday = weekday_map[datetime.now().weekday()]
    report_time = datetime.now().strftime('%H:%M')

    full_output_lines = []
    header = f"\n{'═'*54}\n 📊 A 股午间快报 — {today_str} ({weekday})\n{'═'*54}"
    full_output_lines.append(header)
    print(header)

    results = []
    total = len(holdings)

    for i, h in enumerate(holdings, 1):
        code = h['code']
        name = h['name']
        is_etf = h['is_etf']
        etf_flag = "[ETF]" if is_etf else ""

        print(f"  [{i}/{total}] 分析 {name} {etf_flag}({code})...", file=sys.stderr)

        result_entry = {'holding': h}

        try:
            # 1. 获取日K线数据（技术面基础）
            df_daily = fetch_daily_kline(code, start_date, end_date, is_etf)
            if df_daily is None or len(df_daily) < 20:
                result_entry['error'] = f'{name} ({code}) 日K数据获取失败'
                results.append(result_entry)
                continue

            # 兼容列名
            if 'close' not in df_daily.columns:
                df_daily.columns = ['date', 'code', 'open', 'close', 'high', 'low',
                                    'volume', 'amount', 'amp', 'chg', 'pct', 'turn'][:len(df_daily.columns)]
            for col in ['open', 'close', 'high', 'low', 'volume']:
                if col in df_daily.columns:
                    df_daily[col] = pd.to_numeric(df_daily[col], errors='coerce')

            # 前日收盘价（从日K数据中显式找前一个自然日的收盘价）
            prev_close = get_prev_close(df_daily)

            # 数据交叉验证：获取实时行情验证前收盘价
            realtime = fetch_realtime_quote(code, is_etf)
            if realtime and realtime.get('prev_close') is not None:
                current_market_close = realtime['prev_close']
                # 如果日K数据的前收盘价与腾讯/新浪行情偏差超过2%，使用行情数据
                if abs(prev_close - current_market_close) / current_market_close > 0.02:
                    print(f"  ⚠️ {name} 前收盘价偏差: 日K={prev_close:.3f} vs 行情={current_market_close:.3f}，使用行情数据", file=sys.stderr)
                    prev_close = current_market_close

            # 2. 计算技术指标
            ta_data = calculate_ta_indicators(df_daily)
            if ta_data is None:
                result_entry['error'] = f'{name} ({code}) 技术指标计算失败'
                results.append(result_entry)
                continue

            # 3. 获取上午分时数据
            df_intraday = fetch_intraday_5min(code, is_etf)

            # 4. 获取近5天分时（用于量能对比）
            df_recent = fetch_recent_5min(code, is_etf, days=5)

            # 5. 上午走势分析
            morning = analyze_morning(df_intraday, prev_close, df_recent)
            morning['prev_close'] = prev_close

            # 6. 用午间价更新 ta_data 中的当前价
            if morning.get('midday_price') and morning['midday_price'] > 0:
                ta_data['price'] = morning['midday_price']

            # 7. 数据校验
            data_warnings = validate_data(morning, prev_close, name, code)

            # 8. 技术面评分（整合上午动量）
            morning_momentum = {'chg_pct': morning.get('chg_pct', 0), 'vol_ratio': morning.get('vol_ratio')}
            ta_score, ta_rating, ta_conf, ta_signals = calculate_score(ta_data, morning_momentum)

            # 9. 下午操作建议（暂不强制覆盖，等批处理后统一差异化处理）
            advice = generate_afternoon_advice(morning, ta_score, ta_rating, ta_data, ta_signals)

            result_entry.update({
                'morning': morning,
                'ta_data': ta_data,
                'ta_score': ta_score,
                'ta_rating': ta_rating,
                'ta_conf': ta_conf,
                'ta_signals': ta_signals,
                'advice': advice,
                'warnings': data_warnings,
            })

            # 行业信息（简单映射）
            industry_map = {
                '600036': '银行', '600900': '电力', '601166': '银行',
                '002714': '畜牧业', '000333': '家电',
                '515170': '食品饮料', '515120': '创新药'
            }
            h['industry'] = industry_map.get(code, 'ETF' if is_etf else '')

            # 输出单只报告（附带校验警告）
            output = format_single_briefing(h, morning, ta_data, ta_score, ta_rating, ta_signals, advice, data_warnings)
            full_output_lines.append(output)
            print(output)

        except Exception as e:
            result_entry['error'] = f'{name} ({code}) 分析异常: {str(e)[:80]}'
            print(f"\n  ⚠️ {name} ({code}) 分析失败: {str(e)[:80]}")

        results.append(result_entry)
        time.sleep(0.5)  # 请求间隔

    # ════════════════════════════════════════════════════════════
    # 后处理：去同质化——强制差异化建议评级
    # 如果全部标的评分都 < 55（全部"谨慎"），则强制排名：
    # 评分最高的 2 只上调为 "🟡 观望"
    # ════════════════════════════════════════════════════════════
    valid_results = [r for r in results if not r.get('error') and r.get('ta_score') is not None]
    if len(valid_results) >= 2:
        all_scores = [r['ta_score'] for r in valid_results]
        # 检查是否全部标的评分 < 55
        if all(s < 55 for s in all_scores):
            # 按评分降序排列，取前2名
            ranked = sorted(valid_results, key=lambda r: r['ta_score'], reverse=True)
            top_two = ranked[:2]
            for r in top_two:
                r['advice'] = generate_afternoon_advice(
                    r['morning'], r['ta_score'], r['ta_rating'],
                    r['ta_data'], r['ta_signals'],
                    force_level='🟡 观望',
                    force_action='技术面偏弱，但评分相对最高，下午可关注企稳信号'
                )
                # 同步更新格式化输出
                h = r['holding']
                new_output = format_single_briefing(
                    h, r['morning'], r['ta_data'],
                    r['ta_score'], r['ta_rating'], r['ta_signals'],
                    r['advice'], r.get('warnings')
                )
                # 替换 full_output_lines 中对应的旧输出
                for idx, line in enumerate(full_output_lines):
                    if f"{h['name']} ({h['code']})" in line:
                        # 找到这个标的的起始行
                        start_idx = idx - 1  # 分隔线行
                        # 找到下一个标的的起始分隔线或总结的开始
                        end_idx = start_idx + 1
                        while end_idx < len(full_output_lines):
                            if chr(9472) in full_output_lines[end_idx] and end_idx > start_idx + 1:
                                break
                            if '下午操作速览' in full_output_lines[end_idx]:
                                break
                            end_idx += 1
                        # 切割并替换
                        new_block_lines = new_output.strip().split('\n')
                        full_output_lines = (
                            full_output_lines[:start_idx]
                            + new_block_lines
                            + full_output_lines[end_idx:]
                        )
                        break

    # 输出总结
    summary = format_summary(results)
    full_output_lines.append(summary)
    print(summary)

    # 尾注
    footer = f"\n{'═'*54}\n 分析时间：{report_time} | 数据来源：东方财富/新浪财经\n ⚠️ 以上分析仅供参考，不构成投资建议\n{'═'*54}\n"
    full_output_lines.append(footer)
    print(footer)

    # 构建完整输出字符串
    full_output = '\n'.join(full_output_lines)

    # 保存完整报告到文件
    _save_report(full_output, today_str, summary, footer, results)

    # 保存状态
    state = {
        'last_run': datetime.now().isoformat(),
        'results_count': len([r for r in results if not r.get('error')]),
        'errors_count': len([r for r in results if r.get('error')]),
    }
    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except:
        pass

    print("=" * 54, file=sys.stderr)
    print(" 午间快报生成完毕", file=sys.stderr)
    print("=" * 54, file=sys.stderr)


def _save_report(full_output: str, today_str: str, summary: str, footer: str, results: List[Dict]):
    """保存完整报告到输出目录"""
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime('%Y%m%d')
        # 主报告文件
        report_path = OUTPUT_DIR / f"midday-briefing-{today}.txt"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(full_output)
        print(f"\n📁 报告已保存：{report_path}", file=sys.stderr)

        # 简要 Markdown 版本（方便阅读）
        md_path = OUTPUT_DIR / f"midday-briefing-{today}.md"
        _save_markdown(md_path, today_str, results, summary, footer)
        print(f"📁 Markdown版已保存：{md_path}", file=sys.stderr)
    except Exception as e:
        print(f"⚠️ 报告保存失败：{e}", file=sys.stderr)


def _save_markdown(path: Path, today_str: str, results: List[Dict], summary: str, footer: str):
    """保存 Markdown 格式的午间快报"""
    lines = []
    weekday_map = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    weekday = weekday_map[datetime.now().weekday()]
    report_time = datetime.now().strftime('%H:%M')

    lines.append(f"# 📊 A 股午间快报 — {today_str} ({weekday})")
    lines.append(f"")
    lines.append(f"> 生成时间：{report_time} | 数据来源：东方财富/新浪财经")
    lines.append(f"")

    # 操作速览表
    categories = {'🟢 可操作': [], '🟡 观望': [], '🔴 谨慎': [], '❌ 数据异常': []}
    for r in results:
        if r.get('error'):
            categories['❌ 数据异常'].append(r['error'])
            continue
        level = r.get('advice', {}).get('level', '🟡 观望')
        h = r['holding']
        code = h['code']
        name = h['name']
        morning = r.get('morning', {})
        chg = morning.get('chg_pct', 0)
        score = r.get('ta_score', 0)
        categories[level].append(f"{code} {name} ({chg:+.2f}%, 评分{score})")

    lines.append("## 📋 下午操作速览")
    lines.append("")
    lines.append("| 分类 | 标的 |")
    lines.append("|------|------|")
    for cat, items in categories.items():
        if items:
            for item in items:
                lines.append(f"| {cat} | {item} |")
    lines.append("")

    # 各标的详情
    lines.append("## 📈 各标的详情")
    lines.append("")
    for r in results:
        if r.get('error'):
            lines.append(f"### ⚠️ {r['error']}")
            continue
        h = r['holding']
        m = r.get('morning', {})
        ta = r.get('ta_data', {})
        score = r.get('ta_score', 0)
        rating = r.get('ta_rating', '')
        advice = r.get('advice', {})

        etf_flag = " [ETF]" if h.get('is_etf') else ""
        industry = h.get('industry', '')
        lines.append(f"### {h['name']} ({h['code']}){etf_flag}{' — ' + industry if industry else ''}")
        lines.append("")

        lines.append(f"- **上午走势**：前收 {m.get('prev_close', 0):.2f} | 午间 {m.get('midday_price', 0):.2f} | 涨跌 {m.get('chg_pct', 0):+.2f}% | {m.get('trend_desc', '')}")
        if m.get('vol_ratio') is not None:
            lines.append(f"- **量能**：{m.get('vol_ratio', 0):.1f}x 近5日上午均值 ({m.get('vol_desc', '')})")
        lines.append(f"- **技术面**：评分 {score}/100 | {rating} | RSI={ta.get('rsi14', 0):.1f} | ADX={ta.get('adx', 0):.1f}")
        lines.append(f"- **下午建议**：{advice.get('level', '')} · {advice.get('action', '')}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*⚠️ 以上分析仅供参考，不构成投资建议*")

    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


if __name__ == "__main__":
    main()
