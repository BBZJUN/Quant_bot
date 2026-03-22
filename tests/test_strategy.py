"""
전략 로직 단위 테스트 (API 없이 실행 가능)
실행: python tests/test_strategy.py
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from utils.date_utils import is_trading_day, is_rebalance_day, get_last_trading_day_of_month
from backtest.backtester import Backtester


def test_date_utils():
    """거래일 계산 테스트"""
    print("\n[1] 거래일 유틸 테스트")
    from datetime import datetime

    cases = [
        datetime(2026, 3, 23),  # 월요일
        datetime(2026, 3, 21),  # 토요일
        datetime(2026, 3, 22),  # 일요일
        datetime(2026, 1, 1),   # 신정
    ]
    for d in cases:
        result = "거래일" if is_trading_day(d) else "비거래일"
        print(f"  {d.strftime('%Y-%m-%d (%a)')} → {result}")

    last = get_last_trading_day_of_month(2026, 3)
    print(f"  2026년 3월 마지막 거래일: {last.strftime('%Y-%m-%d')}")
    print("  ✅ 완료")


def test_backtester():
    """백테스터 기본 동작 테스트 (랜덤 데이터)"""
    print("\n[2] 백테스터 테스트 (가상 데이터)")

    # 가상 주가 데이터 생성
    dates   = pd.date_range("2023-01-01", "2025-12-31", freq="B")
    tickers = ["A", "B", "C", "D", "E"]
    np.random.seed(42)

    price_data = {}
    for t in tickers:
        prices = [10000]
        for _ in range(len(dates) - 1):
            prices.append(int(prices[-1] * (1 + np.random.normal(0.0003, 0.015))))
        price_data[t] = prices

    price_df = pd.DataFrame(price_data, index=dates)

    # 매월 첫날 전체 종목 동일비중 보유 신호
    signals = pd.Series(index=dates, dtype=object)
    for date in dates:
        if date.day <= 3:
            signals[date] = tickers
        else:
            signals[date] = None

    bt      = Backtester(initial_capital=10_000_000)
    result  = bt.run(price_df, signals)
    metrics = bt.calc_metrics(result)

    print(f"  총 수익률  : {metrics['total_return']}")
    print(f"  연간 수익률: {metrics['annual_return']}")
    print(f"  MDD       : {metrics['mdd']}")
    print(f"  샤프비율   : {metrics['sharpe']}")
    print(f"  최종 자산  : {metrics['end_capital']}")
    print("  ✅ 완료")


if __name__ == "__main__":
    print("=" * 50)
    print("  전략 단위 테스트 (API 불필요)")
    print("=" * 50)

    test_date_utils()
    test_backtester()

    print("\n" + "=" * 50)
    print("  테스트 완료")
    print("=" * 50)
