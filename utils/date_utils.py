"""
날짜 유틸리티
- 한국 증시 거래일 계산
- 마지막 거래일 조회
"""

from datetime import datetime, timedelta
import pandas as pd


# 공휴일은 매년 업데이트 필요 (또는 외부 API로 자동화)
HOLIDAYS_2025 = {
    "20250101", "20250127", "20250128", "20250129",
    "20250130", "20250131", "20250301", "20250505",
    "20250506", "20250602", "20250815", "20251003",
    "20251009", "20251225",
}

HOLIDAYS_2026 = {
    "20260101", "20260216", "20260217", "20260218",
    "20260301", "20260505", "20260525", "20260601",
    "20260815", "20261001", "20261002", "20261003",
    "20261009", "20261225",
}

ALL_HOLIDAYS = HOLIDAYS_2025 | HOLIDAYS_2026


def is_trading_day(date: datetime = None) -> bool:
    """주어진 날짜가 거래일인지 확인"""
    if date is None:
        date = datetime.now()
    if date.weekday() >= 5:  # 토=5, 일=6
        return False
    return date.strftime("%Y%m%d") not in ALL_HOLIDAYS


def get_last_trading_day(date: datetime = None) -> datetime:
    """가장 최근 거래일 반환"""
    if date is None:
        date = datetime.now()
    while not is_trading_day(date):
        date -= timedelta(days=1)
    return date


def get_last_trading_day_of_month(year: int = None, month: int = None) -> datetime:
    """해당 월의 마지막 거래일 반환"""
    if year is None:
        year = datetime.now().year
    if month is None:
        month = datetime.now().month

    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)

    last_day = next_month - timedelta(days=1)
    return get_last_trading_day(last_day)


def is_rebalance_day() -> bool:
    """오늘이 리밸런싱일(월 마지막 거래일)인지 확인"""
    today = datetime.now()
    last_day = get_last_trading_day_of_month(today.year, today.month)
    return today.date() == last_day.date()


def get_market_open_close():
    """장 시작/종료 시간 반환"""
    today = datetime.now()
    open_time  = today.replace(hour=9,  minute=0,  second=0, microsecond=0)
    close_time = today.replace(hour=15, minute=30, second=0, microsecond=0)
    return open_time, close_time


def is_market_open() -> bool:
    """현재 장 운영 중인지 확인"""
    now = datetime.now()
    if not is_trading_day(now):
        return False
    open_t, close_t = get_market_open_close()
    return open_t <= now <= close_t
