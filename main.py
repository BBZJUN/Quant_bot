"""
quant_bot 진입점
사용법:
    python main.py           → 자동매매 봇 실행
    python main.py status    → 현재 잔고/포트폴리오 출력
    python main.py report    → 수익률 리포트 출력
    python main.py rebalance → 수동 리밸런싱 실행
    python main.py backtest  → 백테스트 실행
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))
from config.settings import ACTIVE_MODE
from data.kis_api import KISApi
from data.database import init_db
from monitoring.reporter import Reporter
from utils.logger import get_logger

logger = get_logger("main")


def cmd_status():
    api = KISApi(ACTIVE_MODE)
    reporter = Reporter(api)
    reporter.daily_report()
    reporter.show_trade_history(days=7)


def cmd_report():
    api = KISApi(ACTIVE_MODE)
    reporter = Reporter(api)
    reporter.show_performance(days=30)


def cmd_rebalance():
    from data.universe import get_full_universe
    from strategy.dual_momentum import DualMomentum
    from strategy.factor_strategy import FactorStrategy
    from portfolio.risk_manager import RiskManager
    from portfolio.rebalancer import Rebalancer
    from execution.order_manager import OrderManager

    api      = KISApi(ACTIVE_MODE)
    om       = OrderManager(api)
    risk     = RiskManager(api, om)
    rebal    = Rebalancer(api, om, risk)
    momentum = DualMomentum(api)
    factor   = FactorStrategy(api)

    signal = momentum.get_signal()
    logger.info(f"시장 신호: {signal['reason']}")

    if not signal["invest"]:
        logger.info("현금 보유 신호 → 리밸런싱 안 함")
        return

    universe = get_full_universe()
    target   = factor.get_target_portfolio(universe)
    rebal.rebalance(target)


def cmd_backtest():
    logger.info("백테스트 기능은 backtest/backtester.py 를 직접 실행하세요.")
    logger.info("  python backtest/backtester.py")


def cmd_run():
    from scheduler import TradingBot
    init_db()
    bot = TradingBot(mode=ACTIVE_MODE)
    bot.run()


COMMANDS = {
    "status":    cmd_status,
    "report":    cmd_report,
    "rebalance": cmd_rebalance,
    "backtest":  cmd_backtest,
}

if __name__ == "__main__":
    init_db()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"

    if cmd in COMMANDS:
        COMMANDS[cmd]()
    elif cmd == "run":
        cmd_run()
    else:
        print(__doc__)
