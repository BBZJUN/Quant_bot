"""
팩터 투자 전략
- PBR 하위 30% (저평가)
- ROE 상위 30% (수익성)
- 12개월 모멘텀 상위 30%
→ 3개 교집합 종목을 동일비중 보유
"""

import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))
from config.settings import STRATEGY_CONFIG
from utils.logger import get_logger

logger = get_logger(__name__)


class FactorStrategy:
    def __init__(self, kis_api):
        self.api = kis_api
        self.cfg = STRATEGY_CONFIG

    # =========================================================
    # 팩터 계산
    # =========================================================
    def calc_momentum(self, ticker: str, months: int = 12,
                      market: str = "J") -> float:
        """N개월 가격 모멘텀"""
        end   = datetime.now()
        start = end - timedelta(days=months * 31 + 30)
        data  = self.api.get_ohlcv(
            ticker, period="M",
            start=start.strftime("%Y%m%d"),
            end=end.strftime("%Y%m%d"),
            market=market,
        )
        if len(data) < months:
            return None

        old = data[-months]["close"]
        new = data[-1]["close"]
        return (new - old) / old if old else None

    def get_fundamental(self, ticker: str, market: str = "J") -> dict:
        """
        PBR / ROE 조회
        - PBR: 현재가 API에서 직접 추출 (안정적)
        - ROE: EPS / (현재가 / PBR) 로 추정
        """
        try:
            price_data = self.api.get_current_price(ticker, market="J")
            pbr = price_data.get("pbr", 0)
            eps = price_data.get("eps", 0)
            price = price_data.get("current_price", 0)

            # ROE 추정: EPS / BPS = EPS / (Price / PBR)
            roe = 0.0
            if pbr > 0 and price > 0 and eps > 0:
                bps = price / pbr
                roe = (eps / bps) * 100  # % 단위

            return {"pbr": pbr, "roe": roe}
        except Exception as e:
            logger.warning(f"재무 조회 실패 [{ticker}]: {e}")
            return {}

    # =========================================================
    # 종목 스크리닝
    # =========================================================
    def screen(self, universe: pd.DataFrame) -> pd.DataFrame:
        """
        유니버스에서 팩터 조건 충족 종목 선별
        universe: DataFrame with columns [ticker, name, sector, market]
        """
        records = []
        total = len(universe)
        logger.info(f"팩터 스크리닝 시작: {total}종목")

        for i, (_, row) in enumerate(universe.iterrows()):
            ticker = row["ticker"]
            market = "J" if row["market"] == "KOSPI" else "Q"

            if i % 50 == 0:
                logger.info(f"  진행: {i}/{total}")

            # 모멘텀
            momentum = self.calc_momentum(
                ticker,
                months=self.cfg["momentum_months"],
                market=market,
            )
            if momentum is None:
                continue

            # PBR / ROE
            fundamental = self.get_fundamental(ticker, market)
            pbr = fundamental.get("pbr")
            roe = fundamental.get("roe")

            if pbr is None or roe is None or pbr <= 0:
                continue

            # 수급 분석 (점수 가산용, 하드 필터 아님)
            investor = self.api.get_investor_trend(ticker, market)
            institution_buy = investor.get("institution", 0)
            foreign_buy     = investor.get("foreign", 0)
            # 기관+외국인 순매수 합산 (양수일수록 좋음)
            flow_score = institution_buy + foreign_buy

            records.append({
                "ticker":      ticker,
                "name":        row["name"],
                "sector":      row["sector"],
                "market":      row["market"],
                "pbr":         pbr,
                "roe":         roe,
                "momentum":    momentum,
                "flow_score":  flow_score,
            })

        if not records:
            logger.warning("스크리닝 결과 없음")
            return pd.DataFrame()

        df = pd.DataFrame(records)

        # 팩터 순위 계산
        df["pbr_rank"]      = df["pbr"].rank(pct=True)         # 낮을수록 좋음
        df["roe_rank"]      = df["roe"].rank(pct=True, ascending=False)
        df["momentum_rank"] = df["momentum"].rank(pct=True, ascending=False)

        pbr_cut = self.cfg["pbr_percentile"]
        roe_cut = self.cfg["roe_percentile"]
        mom_cut = self.cfg["momentum_percentile"]

        selected = df[
            (df["pbr_rank"]      <= pbr_cut) &
            (df["roe_rank"]      <= roe_cut) &
            (df["momentum_rank"] <= mom_cut)
        ].copy()

        # 수급 순위 (높을수록 좋음 → ascending=False로 낮은 rank가 좋은 것)
        selected["flow_rank"] = selected["flow_score"].rank(pct=True, ascending=False)

        # 종합 점수: 팩터 3개 + 수급 1개 (낮을수록 좋음)
        selected["score"] = (
            selected["pbr_rank"] + selected["roe_rank"] +
            selected["momentum_rank"] + selected["flow_rank"]
        ) / 4
        selected = selected.sort_values("score").reset_index(drop=True)

        logger.info(f"팩터 스크리닝 완료: {len(selected)}종목 선별")
        return selected

    def get_target_portfolio(self, universe: pd.DataFrame) -> list:
        """
        목표 포트폴리오 종목 리스트 반환 (상위 N종목)
        """
        screened = self.screen(universe)
        if screened.empty:
            return []

        n = self.cfg["target_stocks"]
        top = screened.head(n)
        weight = 1.0 / len(top)  # 동일비중

        result = []
        for _, row in top.iterrows():
            result.append({
                "ticker": row["ticker"],
                "name":   row["name"],
                "sector": row["sector"],
                "market": row["market"],
                "weight": weight,
                "pbr":    row["pbr"],
                "roe":    row["roe"],
                "momentum": row["momentum"],
            })

        logger.info(f"목표 포트폴리오 {len(result)}종목 (동일비중 {weight:.1%})")
        return result
