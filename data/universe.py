"""
투자 유니버스 구성
- KRX에서 코스피/코스닥 전체 종목 리스트 다운로드
- 최소 시가총액 / 거래대금 필터 적용
"""

import requests
import pandas as pd
from io import BytesIO
from datetime import datetime
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))
from config.settings import STRATEGY_CONFIG
from utils.logger import get_logger

logger = get_logger(__name__)

KRX_URL = "https://kind.krx.co.kr/corpgeneral/corpList.do"


def get_krx_tickers(market: str = "kospi") -> pd.DataFrame:
    """
    KRX에서 종목 리스트 다운로드
    market: "kospi" or "kosdaq"
    """
    market_code = {"kospi": "stockMkt", "kosdaq": "kosdaqMkt"}[market.lower()]
    params  = {"method": "download", "searchType": 1, "marketType": market_code}
    headers = {"User-Agent": "Mozilla/5.0"}

    resp = requests.get(KRX_URL, params=params, headers=headers, timeout=15)
    resp.raise_for_status()

    df = pd.read_html(BytesIO(resp.content), header=0)[0]
    df = df[["회사명", "종목코드", "업종"]].copy()
    df.columns = ["name", "ticker", "sector"]
    df["ticker"] = df["ticker"].astype(str).str.zfill(6)
    df["market"] = market.upper()
    logger.info(f"{market.upper()} 종목 수: {len(df)}")
    return df


def get_full_universe() -> pd.DataFrame:
    """코스피 + 코스닥 전체 종목"""
    kospi  = get_krx_tickers("kospi")
    kosdaq = get_krx_tickers("kosdaq")
    df = pd.concat([kospi, kosdaq], ignore_index=True)
    logger.info(f"전체 유니버스: {len(df)}종목")
    return df


def filter_universe(df: pd.DataFrame, price_data: dict = None) -> pd.DataFrame:
    """
    최소 시가총액 / 거래대금 필터 적용
    price_data: {ticker: {"market_cap": int, "avg_volume": int}}
    """
    if price_data is None:
        logger.warning("price_data 없음 → 필터 미적용, 전체 반환")
        return df

    min_cap    = STRATEGY_CONFIG["min_market_cap"]
    min_volume = STRATEGY_CONFIG["min_daily_volume"]

    mask = df["ticker"].map(
        lambda t: (
            price_data.get(t, {}).get("market_cap", 0) >= min_cap and
            price_data.get(t, {}).get("avg_volume",  0) >= min_volume
        )
    )
    filtered = df[mask].reset_index(drop=True)
    logger.info(
        f"필터 후 유니버스: {len(filtered)}종목 "
        f"(시총≥{min_cap/1e8:.0f}억, 거래대금≥{min_volume/1e8:.0f}억)"
    )
    return filtered


if __name__ == "__main__":
    df = get_full_universe()
    print(df.head(10))
    out = Path(__file__).parent / "processed" / "universe.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"저장 완료: {out}")
