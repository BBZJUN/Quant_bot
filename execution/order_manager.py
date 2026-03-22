"""
주문 관리
- 매수 / 매도 실행 래퍼
- 거래 기록 DB 저장
- 주문 실패 시 재시도 로직
"""

import time
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))
from data.database import record_trade
from utils.logger import get_logger

logger = get_logger(__name__)

MAX_RETRY = 3
RETRY_DELAY = 2  # 초


class OrderManager:
    def __init__(self, kis_api):
        self.api = kis_api

    # =========================================================
    # 매수
    # =========================================================
    def buy(self, ticker: str, quantity: int, price: int = 0,
            name: str = "", strategy: str = "factor"):
        """매수 실행 (price=0이면 시장가)"""
        if quantity <= 0:
            return

        for attempt in range(1, MAX_RETRY + 1):
            try:
                if price == 0:
                    result = self.api.buy_market(ticker, quantity)
                else:
                    result = self.api.buy_limit(ticker, quantity, price)

                if result.get("success"):
                    exec_price = price or self._get_price(ticker)
                    record_trade(
                        ticker=ticker, name=name, action="BUY",
                        quantity=quantity, price=exec_price,
                        order_no=result.get("order_no"),
                        strategy=strategy,
                    )
                    return result
                else:
                    logger.warning(f"매수 실패 [{ticker}] 시도 {attempt}/{MAX_RETRY}: {result.get('message')}")

            except Exception as e:
                logger.error(f"매수 오류 [{ticker}] 시도 {attempt}/{MAX_RETRY}: {e}")

            if attempt < MAX_RETRY:
                time.sleep(RETRY_DELAY)

        logger.error(f"매수 최종 실패 [{ticker}]")
        return {"success": False}

    # =========================================================
    # 매도
    # =========================================================
    def sell(self, ticker: str, quantity: int, price: int = 0,
             name: str = "", strategy: str = "factor"):
        """매도 실행 (price=0이면 시장가)"""
        if quantity <= 0:
            return

        for attempt in range(1, MAX_RETRY + 1):
            try:
                if price == 0:
                    result = self.api.sell_market(ticker, quantity)
                else:
                    result = self.api.sell_limit(ticker, quantity, price)

                if result.get("success"):
                    exec_price = price or self._get_price(ticker)
                    record_trade(
                        ticker=ticker, name=name, action="SELL",
                        quantity=quantity, price=exec_price,
                        order_no=result.get("order_no"),
                        strategy=strategy,
                    )
                    return result
                else:
                    logger.warning(f"매도 실패 [{ticker}] 시도 {attempt}/{MAX_RETRY}: {result.get('message')}")

            except Exception as e:
                logger.error(f"매도 오류 [{ticker}] 시도 {attempt}/{MAX_RETRY}: {e}")

            if attempt < MAX_RETRY:
                time.sleep(RETRY_DELAY)

        logger.error(f"매도 최종 실패 [{ticker}]")
        return {"success": False}

    def sell_all(self, ticker: str, quantity: int, name: str = ""):
        """전량 시장가 매도"""
        logger.info(f"전량 매도 [{ticker}] {quantity}주")
        return self.sell(ticker, quantity, price=0, name=name, strategy="risk")

    # =========================================================
    # 내부 유틸
    # =========================================================
    def _get_price(self, ticker: str) -> int:
        """현재가 조회 (체결가 기록용)"""
        try:
            data = self.api.get_current_price(ticker)
            return data.get("current_price", 0)
        except Exception:
            return 0
