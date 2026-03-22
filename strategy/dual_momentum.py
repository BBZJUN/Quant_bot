"""
듀얼 모멘텀 전략
- 절대 모멘텀: 코스피200 수익률 > 국고채 → 주식 투자 / 아니면 현금
- 상대 모멘텀: 코스피 vs 코스닥 중 강한 시장 선택
"""

from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))
from config.settings import DUAL_MOMENTUM_CONFIG
from utils.logger import get_logger

logger = get_logger(__name__)


class DualMomentum:
    def __init__(self, kis_api):
        self.api        = kis_api
        self.cfg        = DUAL_MOMENTUM_CONFIG
        self.lookback   = self.cfg["lookback_months"]
        self.rf_ticker  = self.cfg["risk_free_ticker"]   # 국고채 ETF
        self.bm_ticker  = self.cfg["benchmark_ticker"]   # KODEX 200

    def _calc_return(self, ticker: str, months: int, market: str = "J") -> float:
        """N개월 수익률 계산"""
        end   = datetime.now()
        start = end - timedelta(days=months * 31)
        data  = self.api.get_ohlcv(
            ticker, period="M",
            start=start.strftime("%Y%m%d"),
            end=end.strftime("%Y%m%d"),
            market=market,
        )
        if len(data) < 2:
            logger.warning(f"{ticker} 데이터 부족")
            return 0.0

        old_close = data[0]["close"]
        new_close = data[-1]["close"]
        ret = (new_close - old_close) / old_close if old_close else 0.0
        logger.info(f"{ticker} {months}개월 수익률: {ret:.2%}")
        return ret

    def get_signal(self) -> dict:
        """
        시장 진입/이탈 신호 반환
        returns:
            {
                "invest": bool,        # True=주식 투자, False=현금 보유
                "market": str,         # "KOSPI" or "KOSDAQ" or None
                "reason": str,
            }
        """
        # 절대 모멘텀: 코스피200 vs 국고채 ETF
        kospi200_ret = self._calc_return(self.bm_ticker, self.lookback)
        rf_ret       = self._calc_return(self.rf_ticker, self.lookback)

        if kospi200_ret <= rf_ret:
            logger.info(f"절대 모멘텀 → 현금 (코스피200 {kospi200_ret:.2%} ≤ 국고채 {rf_ret:.2%})")
            return {
                "invest": False,
                "market": None,
                "reason": f"코스피200({kospi200_ret:.2%}) ≤ 국고채({rf_ret:.2%}) → 현금 보유",
            }

        # 상대 모멘텀: 코스피 vs 코스닥 (KODEX 코스닥150 = 229200)
        kosdaq_ret = self._calc_return("229200", self.lookback, market="Q")

        if kospi200_ret >= kosdaq_ret:
            chosen = "KOSPI"
            reason = f"코스피({kospi200_ret:.2%}) ≥ 코스닥({kosdaq_ret:.2%})"
        else:
            chosen = "KOSDAQ"
            reason = f"코스닥({kosdaq_ret:.2%}) > 코스피({kospi200_ret:.2%})"

        logger.info(f"절대 모멘텀 → 투자 / 상대 모멘텀 → {chosen} ({reason})")
        return {
            "invest": True,
            "market": chosen,
            "reason": reason,
        }
