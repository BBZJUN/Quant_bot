"""
리스크 관리
- 종목별 손절 / 익절
- 포트폴리오 전체 손절
- 포지션 크기 제한
"""

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))
from config.settings import RISK_CONFIG
from utils.logger import get_logger

logger = get_logger(__name__)


class RiskManager:
    def __init__(self, kis_api, order_manager):
        self.api   = kis_api
        self.om    = order_manager
        self.cfg   = RISK_CONFIG

    def check_stop_loss(self, balance: dict) -> list:
        """
        보유 종목 중 손절 조건 확인
        Returns: 손절 대상 종목 리스트
        """
        stop_threshold = self.cfg["stop_loss_per_stock"]
        targets = []

        for holding in balance.get("holdings", []):
            profit_rate = holding["profit_rate"] / 100  # % → 소수
            if profit_rate <= stop_threshold:
                logger.warning(
                    f"손절 신호 [{holding['ticker']}] "
                    f"수익률: {profit_rate:.2%} ≤ {stop_threshold:.2%}"
                )
                targets.append(holding)

        return targets

    def check_take_profit(self, balance: dict) -> list:
        """익절 조건 확인"""
        take_threshold = self.cfg["take_profit"]
        targets = []

        for holding in balance.get("holdings", []):
            profit_rate = holding["profit_rate"] / 100
            if profit_rate >= take_threshold:
                logger.info(
                    f"익절 신호 [{holding['ticker']}] "
                    f"수익률: {profit_rate:.2%} ≥ {take_threshold:.2%}"
                )
                targets.append(holding)

        return targets

    def check_portfolio_stop(self, balance: dict) -> bool:
        """포트폴리오 전체 손절 확인"""
        portfolio_rate = balance.get("total_profit_rate", 0) / 100
        threshold      = self.cfg["stop_loss_portfolio"]

        if portfolio_rate <= threshold:
            logger.error(
                f"포트폴리오 전체 손절 발동! "
                f"수익률: {portfolio_rate:.2%} ≤ {threshold:.2%}"
            )
            return True
        return False

    def execute_stop_loss(self, balance: dict):
        """손절 조건 확인 후 자동 매도"""
        # 포트폴리오 전체 손절
        if self.check_portfolio_stop(balance):
            logger.error("전체 포트폴리오 현금화 실행")
            for holding in balance.get("holdings", []):
                self.om.sell_all(holding["ticker"], holding["quantity"])
            return

        # 종목별 손절
        for holding in self.check_stop_loss(balance):
            logger.warning(f"종목 손절 실행: {holding['ticker']}")
            self.om.sell_all(holding["ticker"], holding["quantity"])

        # 종목별 익절
        for holding in self.check_take_profit(balance):
            logger.info(f"종목 익절 실행: {holding['ticker']}")
            self.om.sell_all(holding["ticker"], holding["quantity"])

    def calc_position_size(self, total_cash: int, weight: float,
                           price: int) -> int:
        """
        목표 비중에 맞는 매수 주수 계산
        total_cash: 투자 가능 금액
        weight: 목표 비중 (예: 0.05 = 5%)
        price: 현재가
        """
        if price <= 0:
            return 0
        amount  = total_cash * weight
        qty     = int(amount // price)
        max_qty = int(total_cash * self.cfg["max_single_weight"] // price)
        qty     = min(qty, max_qty)
        logger.debug(f"포지션 계산: 금액={amount:,.0f}원, 주수={qty}주 @{price:,}원")
        return qty
