"""
월 1회 포트폴리오 리밸런싱
- 현재 보유 종목 vs 목표 포트폴리오 비교
- 매도 → 매수 순으로 실행
"""

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))
from utils.logger import get_logger

logger = get_logger(__name__)


class Rebalancer:
    def __init__(self, kis_api, order_manager, risk_manager):
        self.api  = kis_api
        self.om   = order_manager
        self.risk = risk_manager

    def rebalance(self, target_portfolio: list):
        """
        리밸런싱 실행
        target_portfolio: [{"ticker", "name", "weight", ...}, ...]
        """
        logger.info("=" * 50)
        logger.info("리밸런싱 시작")

        # 현재 잔고 조회
        balance = self.api.get_balance()
        if not balance:
            logger.error("잔고 조회 실패 → 리밸런싱 중단")
            return

        total_eval  = balance["total_eval"]
        holdings    = {h["ticker"]: h for h in balance["holdings"]}
        target_map  = {t["ticker"]: t for t in target_portfolio}

        logger.info(f"총 평가금액: {total_eval:,}원")
        logger.info(f"현재 보유: {list(holdings.keys())}")
        logger.info(f"목표 종목: {list(target_map.keys())}")

        # ① 목표에 없는 종목 → 전량 매도
        to_sell = [t for t in holdings if t not in target_map]
        for ticker in to_sell:
            qty = holdings[ticker]["quantity"]
            logger.info(f"매도 (제외 종목) [{ticker}] {qty}주")
            self.om.sell_all(ticker, qty)

        # ② 잔고 재조회 후 매수
        balance  = self.api.get_balance()
        total_cash = balance.get("cash", 0) + balance.get("total_eval", 0)

        for target in target_portfolio:
            ticker = target["ticker"]
            weight = target["weight"]
            market = "J" if target["market"] == "KOSPI" else "Q"

            price_data = self.api.get_current_price(ticker, market)
            price      = price_data.get("current_price", 0)
            if price == 0:
                logger.warning(f"현재가 조회 실패 [{ticker}] → 건너뜀")
                continue

            target_qty = self.risk.calc_position_size(total_cash, weight, price)
            current_qty = holdings.get(ticker, {}).get("quantity", 0)
            diff_qty    = target_qty - current_qty

            if diff_qty > 0:
                logger.info(f"매수 [{ticker}] {diff_qty}주 @{price:,}원")
                self.om.buy(ticker, diff_qty, price)
            elif diff_qty < 0:
                logger.info(f"매도 (초과 비중) [{ticker}] {abs(diff_qty)}주")
                self.om.sell(ticker, abs(diff_qty), price)
            else:
                logger.info(f"유지 [{ticker}] (변동 없음)")

        logger.info("리밸런싱 완료")
        logger.info("=" * 50)
