#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""午间快报集成测试 — 测试重试和兜底"""
import os, sys, time

sys.path.insert(0, os.path.dirname(__file__))

from ta_utils import calculate_ta_indicators, calculate_score, get_top_signals
from midday_briefing import parse_portfolio, fetch_daily_kline
from datetime import datetime, timedelta

f = open(os.path.join(os.path.dirname(__file__), 'test_output.txt'), 'w', encoding='utf-8')

def log(msg):
    print(msg)
    f.write(msg + '\n')
    f.flush()

log("=" * 55)
log(" Midday Briefing Integration Test v2")
log("=" * 55)

holdings = parse_portfolio()
log(f"\n[1] Holdings: {len(holdings)}")
for h in holdings:
    log(f"    {h['code']} {h['name']} (ETF={h['is_etf']})")

end = datetime.now().strftime('%Y%m%d')
start = (datetime.now() - timedelta(days=90)).strftime('%Y%m%d')

ok, fail = 0, 0
for h in holdings:
    code = h['code']
    name = h['name']
    is_etf = h['is_etf']

    log(f"\n  --- {name} ({code}) {'[ETF]' if is_etf else ''} ---")
    log(f"  Fetching daily kline...")
    t0 = time.time()
    df = fetch_daily_kline(code, start, end, is_etf)
    elapsed = time.time() - t0

    if df is None:
        log(f"  FAIL after {elapsed:.1f}s: all sources exhausted")
        fail += 1
        continue

    log(f"  OK ({elapsed:.1f}s): {len(df)} bars")

    ta = calculate_ta_indicators(df)
    if ta is None:
        log(f"  FAIL: calc failed")
        fail += 1
        continue

    score, rating, conf, sigs = calculate_score(ta)
    log(f"  Score={score}/100 {rating} conf={conf:.0f}% RSI={ta['rsi14']:.1f} ADX={ta['adx']:.1f}")
    ok += 1

log(f"\n{'='*55}")
log(f" Results: {ok} OK, {fail} failed (out of {len(holdings)})")
log(f"{'='*55}")
f.close()
