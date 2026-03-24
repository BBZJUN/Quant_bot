"""
자동 스케줄러
- 장 시작 전: 신호 확인
- 장 중 (실시간): 손절/익절 모니터링
- 장 마감 후: 일일 리포트
- 월 마지막 거래일: 리밸런싱
"""

import schedule
import time
from datetime import datetime
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent))
from config.settings import ACTIVE_MODE, SCHEDULER_CONFIG
from data.kis_api import KISApi
from data.universe import get_full_universe, filter_universe
from data.database import init_db
from strategy.dual_momentum import DualMomentum
from strategy.factor_strategy import FactorStrategy
from portfolio.risk_manager import RiskManager
from portfolio.rebalancer import Rebalancer
from execution.order_manager import OrderManager
from monitoring.reporter import Reporter
from utils.logger import get_logger
from utils.date_utils import is_trading_day, is_rebalance_day, is_market_open

# 돈깡 계절성 필터: 해당 월은 신규 진입 자제 (역사적으로 변동성 높은 달)
RISKY_MONTHS = {7, 9, 10}

logger = get_logger(__name__)


class TradingBot:
    def __init__(self, mode: str = ACTIVE_MODE):
        logger.info(f"TradingBot 초기화 (모드: {mode})")
        init_db()

        self.api      = KISApi(mode)
        self.om       = OrderManager(self.api)
        self.risk     = RiskManager(self.api, self.om)
        self.rebal    = Rebalancer(self.api, self.om, self.risk)
        self.momentum = DualMomentum(self.api)
        self.factor   = FactorStrategy(self.api)
        self.reporter = Reporter(self.api)

    # =========================================================
    # 핵심 작업
    # =========================================================
    def morning_task(self):
        """08:50 - 장 시작 전 듀얼 모멘텀 신호 확인"""
        if not is_trading_day():
            return
        logger.info("=== 오전 작업 시작 ===")
        signal = self.momentum.get_signal()
        logger.info(f"시장 신호: {signal}")

        # 이탈 신호 → 전량 현금화
        if not signal["invest"]:
            balance = self.api.get_balance()
            for h in balance.get("holdings", []):
                self.om.sell_all(h["ticker"], h["quantity"], h.get("name", ""))
            logger.info("시장 이탈 신호 → 전량 현금화 완료")

        # 계절성 경고
        current_month = datetime.now().month
        if current_month in RISKY_MONTHS:
            logger.warning(
                f"[계절성 경고] {current_month}월은 역사적 고변동성 구간 → 신규 진입 자제"
            )

    def risk_monitoring(self):
        """장 중 10분마다 - 손절/익절 모니터링"""
        if not is_market_open():
            return
        balance = self.api.get_balance()
        if balance:
            self.risk.execute_stop_loss(balance)

    def rebalance_task(self):
        """월 마지막 거래일 14:00 - 리밸런싱"""
        if not is_trading_day() or not is_rebalance_day():
            return

        logger.info("=== 월간 리밸런싱 시작 ===")

        # 계절성 필터: 위험 달에는 리밸런싱(신규 매수) 건너뜀
        current_month = datetime.now().month
        if current_month in RISKY_MONTHS:
            logger.warning(f"[계절성 필터] {current_month}월 → 리밸런싱 건너뜀 (고변동성 구간)")
            return

        signal = self.momentum.get_signal()

        if not signal["invest"]:
            logger.info("현금 보유 신호 → 리밸런싱 건너뜀")
            return

        # 유니버스 구성
        universe = get_full_universe()
        # 목표 포트폴리오 계산
        target = self.factor.get_target_portfolio(universe)
        if not target:
            logger.warning("목표 포트폴리오 없음 → 리밸런싱 중단")
            return

        self.rebal.rebalance(target)

    def evening_task(self):
        """16:00 - 일일 리포트"""
        if not is_trading_day():
            return
        logger.info("=== 일일 리포트 생성 ===")
        self.reporter.daily_report()

    # =========================================================
    # 스케줄 등록 및 실행
    # =========================================================
    def run(self):
        cfg = SCHEDULER_CONFIG
        logger.info("스케줄러 시작")
        logger.info(f"  신호 확인    : {cfg['signal_check_time']}")
        logger.info(f"  리스크 모니터: 10분마다 (장 중)")
        logger.info(f"  리밸런싱     : {cfg['rebalance_time']} (월 마지막 거래일)")
        logger.info(f"  일일 리포트  : {cfg['daily_report_time']}")

        schedule.every().day.at(cfg["signal_check_time"]).do(self.morning_task)
        schedule.every(10).minutes.do(self.risk_monitoring)
        schedule.every().day.at(cfg["rebalance_time"]).do(self.rebalance_task)
        schedule.every().day.at(cfg["daily_report_time"]).do(self.evening_task)

        logger.info("스케줄러 가동 중... (Ctrl+C로 종료)")
        while True:
            schedule.run_pending()
            time.sleep(30)


if __name__ == "__main__":
    bot = TradingBot(mode=ACTIVE_MODE)
    bot.run()
