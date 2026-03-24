"""
동적 매도 판단 엔진
- 기술적 지표 + 뉴스 감성 + 시장 상황 + 수익률을 종합해 매도 결정
- 고정 익절가 없이 알고리즘이 최적 매도 타이밍 판단

점수 체계 (0~100점, 높을수록 매도 신호 강함):
  기술적 지표  최대 50점
  뉴스 감성    최대 25점
  시장 상황    최대 15점
  수익률 보정  최대 10점

판단 기준:
  점수 70+ AND 수익률 > 0%   → 익절 매도
  점수 80+                   → 수익률 무관 방어 매도 (하락 대비)
  수익률 <= HARD_STOP        → 무조건 손절
"""

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))
from strategy.technical_analyzer import TechnicalAnalyzer
from data.news_collector import NewsCollector
from utils.logger import get_logger

logger = get_logger(__name__)

HARD_STOP   = -0.03   # -3% 무조건 손절
SELL_SCORE  = 70      # 익절 매도 기준 점수
DEFENSE_SCORE = 80    # 수익률 무관 방어 매도 기준


class ExitStrategy:
    def __init__(self, kis_api):
        self.api       = kis_api
        self.tech      = TechnicalAnalyzer()
        self.news      = NewsCollector()

    # =========================================================
    # 기술적 점수 (0~50점)
    # =========================================================
    def _tech_score(self, tech: dict) -> tuple[int, list]:
        score   = 0
        reasons = []

        rsi = tech.get("rsi")
        if rsi is not None:
            if rsi >= 75:
                score += 20
                reasons.append(f"RSI 과매수({rsi:.0f})")
            elif rsi >= 70:
                score += 12
                reasons.append(f"RSI 주의({rsi:.0f})")
            elif rsi <= 30:
                score -= 10   # 과매도 → 매도 신호 낮춤
                reasons.append(f"RSI 과매도({rsi:.0f}) → 매도 보류")

        macd = tech.get("macd")
        if macd:
            if macd["cross"] == "dead":
                score += 15
                reasons.append("MACD 데드크로스")
            elif macd["histogram"] < 0 and macd["macd"] < 0:
                score += 7
                reasons.append("MACD 음전환")

        bb = tech.get("bollinger")
        if bb:
            if bb["position"] >= 0.95:
                score += 15
                reasons.append(f"볼린저 상단 돌파(position={bb['position']:.2f})")
            elif bb["position"] >= 0.85:
                score += 8
                reasons.append(f"볼린저 상단 근접(position={bb['position']:.2f})")

        ma = tech.get("ma", {})
        if ma.get("ma_cross") == "dead":
            score += 10
            reasons.append("이동평균 데드크로스(5일<20일)")
        elif ma.get("ma_trend") == "down":
            score += 3
            reasons.append("이동평균 하향 배열")

        vol = tech.get("volume", {})
        if vol.get("dry"):
            score += 5
            reasons.append(f"거래량 급감(평균 대비 {vol['ratio']:.1f}배)")

        return min(score, 50), reasons

    # =========================================================
    # 뉴스 감성 점수 (0~25점)
    # =========================================================
    def _news_score(self, ticker: str) -> tuple[int, list]:
        try:
            news_data = self.news.analyze(ticker)
            sentiment = news_data["sentiment"]
            signal    = news_data["signal"]

            if signal == "negative":
                score = int(25 * abs(sentiment))
                score = max(score, 10)
                return min(score, 25), [f"부정 뉴스 감지(감성={sentiment:.2f})"]
            elif signal == "positive":
                return -5, [f"긍정 뉴스(감성={sentiment:.2f}) → 매도 보류"]
            else:
                return 0, []
        except Exception as e:
            logger.warning(f"뉴스 점수 계산 실패 [{ticker}]: {e}")
            return 0, []

    # =========================================================
    # 시장 상황 점수 (0~15점)
    # =========================================================
    def _market_score(self) -> tuple[int, list]:
        try:
            # 코스피 ETF (KODEX 200) 당일 등락률로 시장 판단
            market_data = self.api.get_current_price("069500", market="J")
            change_rate = market_data.get("change_rate", 0)

            if change_rate <= -2.0:
                return 15, [f"코스피 급락({change_rate:+.2f}%)"]
            elif change_rate <= -1.0:
                return 8, [f"코스피 하락({change_rate:+.2f}%)"]
            elif change_rate >= 1.0:
                return -5, [f"코스피 강세({change_rate:+.2f}%) → 매도 보류"]
            else:
                return 0, []
        except Exception as e:
            logger.warning(f"시장 점수 계산 실패: {e}")
            return 0, []

    # =========================================================
    # 수익률 보정 점수 (-5~10점)
    # =========================================================
    def _profit_score(self, profit_rate: float) -> tuple[int, list]:
        if profit_rate >= 0.03:
            return 10, [f"수익 충분({profit_rate:+.1%}) → 익절 가중"]
        elif profit_rate >= 0.015:
            return 5, [f"수익 발생({profit_rate:+.1%})"]
        elif profit_rate >= 0.005:
            return 2, []
        elif profit_rate < 0:
            return -5, [f"손실 중({profit_rate:+.1%}) → 반등 대기"]
        return 0, []

    # =========================================================
    # 최종 매도 판단
    # =========================================================
    def should_sell(self, holding: dict, ohlcv: list) -> dict:
        """
        매도 여부 최종 판단
        holding: {"ticker", "name", "profit_rate"(%), "quantity", ...}
        ohlcv:   최근 OHLCV 리스트
        returns: {"sell": bool, "score": int, "reason": str}
        """
        ticker      = holding["ticker"]
        name        = holding.get("name", ticker)
        profit_rate = holding["profit_rate"] / 100  # % → 소수

        # 1. 무조건 손절
        if profit_rate <= HARD_STOP:
            logger.warning(f"[{name}] 손절 발동 ({profit_rate:+.1%} ≤ {HARD_STOP:.1%})")
            return {
                "sell": True, "score": 100,
                "reason": f"손절 기준 도달({profit_rate:+.1%})",
            }

        # 2. 기술적 분석
        tech = self.tech.analyze(ohlcv)
        if not tech:
            return {"sell": False, "score": 0, "reason": "데이터 부족"}

        tech_score,   tech_reasons   = self._tech_score(tech)
        news_score,   news_reasons   = self._news_score(ticker)
        market_score, market_reasons = self._market_score()
        profit_score, profit_reasons = self._profit_score(profit_rate)

        total_score = tech_score + news_score + market_score + profit_score
        total_score = max(0, min(total_score, 100))

        all_reasons = tech_reasons + news_reasons + market_reasons + profit_reasons
        reason_str  = " | ".join(all_reasons) if all_reasons else "특이사항 없음"

        logger.info(
            f"[{name}] 매도 점수: {total_score}점 "
            f"(기술={tech_score}, 뉴스={news_score}, "
            f"시장={market_score}, 수익={profit_score}) "
            f"| 수익률={profit_rate:+.1%}"
        )
        logger.info(f"  → {reason_str}")

        # 3. 판단
        if total_score >= DEFENSE_SCORE:
            return {
                "sell": True, "score": total_score,
                "reason": f"방어 매도(점수={total_score}) | {reason_str}",
            }

        if total_score >= SELL_SCORE and profit_rate > 0:
            return {
                "sell": True, "score": total_score,
                "reason": f"익절 매도(점수={total_score}, 수익={profit_rate:+.1%}) | {reason_str}",
            }

        return {
            "sell": False, "score": total_score,
            "reason": f"보유 유지(점수={total_score}/{SELL_SCORE}) | {reason_str}",
        }
