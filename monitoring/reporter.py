"""
일일 리포트 생성
- 포트폴리오 현황 출력
- 당일 거래 내역
- 수익률 요약
"""

from datetime import datetime
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))
from data.database import save_snapshot, get_trade_history, get_snapshots
from utils.logger import get_logger

logger = get_logger(__name__)


class Reporter:
    def __init__(self, kis_api):
        self.api = kis_api

    def daily_report(self):
        """일일 리포트 생성 및 DB 저장"""
        balance = self.api.get_balance()
        if not balance:
            logger.error("잔고 조회 실패 → 리포트 생성 불가")
            return

        total_eval   = balance["total_eval"]
        cash         = balance["cash"]
        stock_eval   = total_eval - cash
        total_profit = balance["total_profit"]
        profit_rate  = balance["total_profit_rate"]
        holdings     = balance["holdings"]

        # DB 저장
        save_snapshot(
            total_eval=total_eval,
            cash=cash,
            stock_eval=stock_eval,
            total_profit=total_profit,
            profit_rate=profit_rate,
            holdings=holdings,
        )

        # 콘솔 출력
        print("\n" + "=" * 60)
        print(f"  일일 리포트  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 60)
        print(f"  총 평가금액  : {total_eval:>15,}원")
        print(f"  주식 평가금  : {stock_eval:>15,}원")
        print(f"  현금        : {cash:>15,}원")
        print(f"  총 손익      : {total_profit:>+15,}원")
        print(f"  수익률       : {profit_rate:>+14.2f}%")
        print("-" * 60)
        print(f"  {'종목':<10} {'수량':>6} {'평균단가':>10} {'현재가':>10} {'수익률':>8}")
        print("-" * 60)
        for h in sorted(holdings, key=lambda x: x["profit_rate"], reverse=True):
            print(
                f"  {h['name'][:10]:<10} "
                f"{h['quantity']:>6,}주 "
                f"{h['avg_price']:>10,.0f} "
                f"{h['current_price']:>10,} "
                f"{h['profit_rate']:>+7.2f}%"
            )
        print("=" * 60 + "\n")

    def show_trade_history(self, days: int = 7):
        """최근 거래 내역 출력"""
        trades = get_trade_history(days)
        print(f"\n최근 {days}일 거래 내역 ({len(trades)}건)")
        print("-" * 60)
        for t in trades:
            print(
                f"  [{t['timestamp'][:16]}] "
                f"{t['action']:4} {t['ticker']} "
                f"{t['quantity']:>6,}주 "
                f"@{t['price']:>8,}원 "
                f"= {t['amount']:>12,}원"
            )
        print()

    def show_performance(self, days: int = 30):
        """수익률 추이 출력"""
        snapshots = get_snapshots(days)
        if not snapshots:
            print("데이터 없음")
            return

        print(f"\n최근 {days}일 수익률 추이")
        print("-" * 40)
        for s in reversed(snapshots):
            bar = "+" * int(max(0, s["profit_rate"]))
            print(f"  {s['date']}  {s['profit_rate']:>+7.2f}%  {bar}")
        print()
