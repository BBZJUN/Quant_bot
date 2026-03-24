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
    """섹터별 상위 5종목 고정 유니버스 (약 60종목)"""
    return get_core_universe()


def get_core_universe() -> pd.DataFrame:
    """
    섹터별 대형 우량주 상위 5종목 고정 리스트
    - 전체 탐색 대신 검증된 종목만 빠르게 스크리닝
    """
    stocks = [
        # 반도체
        ("005930", "삼성전자",         "반도체", "KOSPI"),
        ("000660", "SK하이닉스",        "반도체", "KOSPI"),
        ("009150", "삼성전기",          "반도체", "KOSPI"),
        ("066970", "엘앤에프",          "반도체", "KOSDAQ"),
        ("042700", "한미반도체",         "반도체", "KOSDAQ"),
        # IT/전기전자
        ("066570", "LG전자",            "IT전기전자", "KOSPI"),
        ("006400", "삼성SDI",           "IT전기전자", "KOSPI"),
        ("051910", "LG화학",            "IT전기전자", "KOSPI"),
        ("034220", "LG디스플레이",       "IT전기전자", "KOSPI"),
        ("081660", "휴젤",              "IT전기전자", "KOSDAQ"),
        # 2차전지
        ("373220", "LG에너지솔루션",     "2차전지", "KOSPI"),
        ("247540", "에코프로비엠",       "2차전지", "KOSDAQ"),
        ("086520", "에코프로",           "2차전지", "KOSDAQ"),
        ("096770", "SK이노베이션",       "2차전지", "KOSPI"),
        ("006400", "삼성SDI",           "2차전지", "KOSPI"),
        # 바이오/제약
        ("207940", "삼성바이오로직스",   "바이오제약", "KOSPI"),
        ("068270", "셀트리온",          "바이오제약", "KOSPI"),
        ("000100", "유한양행",           "바이오제약", "KOSPI"),
        ("128940", "한미약품",           "바이오제약", "KOSPI"),
        ("326030", "SK바이오팜",         "바이오제약", "KOSPI"),
        # 금융
        ("105560", "KB금융",            "금융", "KOSPI"),
        ("055550", "신한지주",          "금융", "KOSPI"),
        ("086790", "하나금융지주",       "금융", "KOSPI"),
        ("000810", "삼성화재",          "금융", "KOSPI"),
        ("003540", "대신증권",          "금융", "KOSPI"),
        # 자동차
        ("005380", "현대차",            "자동차", "KOSPI"),
        ("000270", "기아",              "자동차", "KOSPI"),
        ("012330", "현대모비스",         "자동차", "KOSPI"),
        ("011210", "현대위아",          "자동차", "KOSPI"),
        ("060980", "한라홀딩스",         "자동차", "KOSPI"),
        # 방산
        ("012450", "한화에어로스페이스", "방산", "KOSPI"),
        ("079550", "LIG넥스원",         "방산", "KOSPI"),
        ("064350", "현대로템",           "방산", "KOSPI"),
        ("000880", "한화",              "방산", "KOSPI"),
        ("047810", "한국항공우주",       "방산", "KOSPI"),
        # 철강/소재
        ("005490", "POSCO홀딩스",       "철강소재", "KOSPI"),
        ("010130", "고려아연",           "철강소재", "KOSPI"),
        ("004020", "현대제철",          "철강소재", "KOSPI"),
        ("011790", "SKC",              "철강소재", "KOSPI"),
        ("009830", "한화솔루션",         "철강소재", "KOSPI"),
        # 통신
        ("017670", "SK텔레콤",          "통신", "KOSPI"),
        ("030200", "KT",               "통신", "KOSPI"),
        ("032640", "LG유플러스",         "통신", "KOSPI"),
        ("018260", "삼성에스디에스",     "통신", "KOSPI"),
        ("035420", "NAVER",            "통신", "KOSPI"),
        # 유통/소비
        ("035720", "카카오",            "유통소비", "KOSPI"),
        ("023530", "롯데쇼핑",          "유통소비", "KOSPI"),
        ("004170", "신세계",            "유통소비", "KOSPI"),
        ("097950", "CJ제일제당",         "유통소비", "KOSPI"),
        ("139480", "이마트",            "유통소비", "KOSPI"),
        # 건설/에너지
        ("028260", "삼성물산",          "건설에너지", "KOSPI"),
        ("000720", "현대건설",          "건설에너지", "KOSPI"),
        ("010950", "S-Oil",            "건설에너지", "KOSPI"),
        ("267250", "HD현대",            "건설에너지", "KOSPI"),
        ("009540", "HD한국조선해양",     "건설에너지", "KOSPI"),
    ]

    df = pd.DataFrame(stocks, columns=["ticker", "name", "sector", "market"])
    # 중복 제거
    df = df.drop_duplicates(subset="ticker").reset_index(drop=True)
    logger.info(f"코어 유니버스: {len(df)}종목 ({df['sector'].nunique()}개 섹터)")
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
