"""
기술적 지표 분석
- RSI (14일)
- MACD (12/26/9)
- 볼린저 밴드 (20일, 2σ)
- 이동평균선 (5일, 20일)
- 거래량 분석
"""

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))
from utils.logger import get_logger

logger = get_logger(__name__)


class TechnicalAnalyzer:

    # =========================================================
    # RSI
    # =========================================================
    def calc_rsi(self, closes: list, period: int = 14) -> float | None:
        """RSI 계산 (0~100)"""
        if len(closes) < period + 1:
            return None

        gains, losses = [], []
        for i in range(1, period + 1):
            diff = closes[-period + i - 1 + 1] - closes[-period + i - 1]
            (gains if diff > 0 else losses).append(abs(diff))

        # 실제로는 최근 period개 변화분을 써야 함
        diffs = [closes[i] - closes[i - 1] for i in range(len(closes) - period, len(closes))]
        gains  = [d for d in diffs if d > 0]
        losses = [-d for d in diffs if d < 0]

        avg_gain = sum(gains) / period if gains else 0
        avg_loss = sum(losses) / period if losses else 0

        if avg_loss == 0:
            return 100.0

        rs  = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return round(rsi, 2)

    # =========================================================
    # MACD
    # =========================================================
    def _ema(self, closes: list, period: int) -> list:
        """EMA 계산"""
        if len(closes) < period:
            return []
        k = 2 / (period + 1)
        ema = [sum(closes[:period]) / period]
        for price in closes[period:]:
            ema.append(price * k + ema[-1] * (1 - k))
        return ema

    def calc_macd(self, closes: list,
                  fast: int = 12, slow: int = 26, signal: int = 9) -> dict | None:
        """
        MACD 계산
        returns: {"macd": float, "signal": float, "histogram": float, "cross": str}
        cross: "golden"=매수 전환, "dead"=매도 전환, "none"=변화없음
        """
        if len(closes) < slow + signal:
            return None

        ema_fast = self._ema(closes, fast)
        ema_slow = self._ema(closes, slow)

        # ema_fast와 ema_slow 길이 맞추기
        diff = len(ema_fast) - len(ema_slow)
        ema_fast = ema_fast[diff:]

        macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
        signal_line = self._ema(macd_line, signal)

        if len(signal_line) < 2:
            return None

        macd_val   = macd_line[-1]
        signal_val = signal_line[-1]
        hist       = macd_val - signal_val

        # 크로스 판단 (전봉 대비)
        prev_macd   = macd_line[-2]
        prev_signal = signal_line[-2]

        if prev_macd < prev_signal and macd_val >= signal_val:
            cross = "golden"  # 골든크로스 (매수)
        elif prev_macd > prev_signal and macd_val <= signal_val:
            cross = "dead"    # 데드크로스 (매도)
        else:
            cross = "none"

        return {
            "macd":      round(macd_val, 2),
            "signal":    round(signal_val, 2),
            "histogram": round(hist, 2),
            "cross":     cross,
        }

    # =========================================================
    # 볼린저 밴드
    # =========================================================
    def calc_bollinger(self, closes: list, period: int = 20, k: float = 2.0) -> dict | None:
        """볼린저 밴드 계산"""
        if len(closes) < period:
            return None

        recent = closes[-period:]
        ma     = sum(recent) / period
        std    = (sum((p - ma) ** 2 for p in recent) / period) ** 0.5

        upper  = ma + k * std
        lower  = ma - k * std
        width  = (upper - lower) / ma  # 밴드 폭 (변동성 지표)

        current = closes[-1]
        position = (current - lower) / (upper - lower) if upper != lower else 0.5

        return {
            "upper":    round(upper, 0),
            "middle":   round(ma, 0),
            "lower":    round(lower, 0),
            "width":    round(width, 4),
            "position": round(position, 2),  # 0=하단, 0.5=중간, 1=상단
        }

    # =========================================================
    # 이동평균선
    # =========================================================
    def calc_ma(self, closes: list) -> dict:
        """5일, 20일 이동평균 및 크로스 판단"""
        result = {}

        for period in [5, 20]:
            if len(closes) >= period:
                result[f"ma{period}"] = round(sum(closes[-period:]) / period, 0)
            else:
                result[f"ma{period}"] = None

        # 데드/골든 크로스
        if result["ma5"] and result["ma20"]:
            if len(closes) >= 21:
                prev_closes = closes[:-1]
                prev_ma5  = sum(prev_closes[-5:]) / 5
                prev_ma20 = sum(prev_closes[-20:]) / 20

                if prev_ma5 > prev_ma20 and result["ma5"] <= result["ma20"]:
                    result["ma_cross"] = "dead"
                elif prev_ma5 < prev_ma20 and result["ma5"] >= result["ma20"]:
                    result["ma_cross"] = "golden"
                else:
                    result["ma_cross"] = "none"
                    result["ma_trend"] = "up" if result["ma5"] > result["ma20"] else "down"
            else:
                result["ma_cross"] = "none"
        else:
            result["ma_cross"] = "none"

        return result

    # =========================================================
    # 거래량 분석
    # =========================================================
    def calc_volume(self, volumes: list, period: int = 20) -> dict:
        """거래량 분석"""
        if len(volumes) < period:
            return {"ratio": None, "surge": False, "dry": False}

        avg_vol     = sum(volumes[-period:-1]) / (period - 1)
        current_vol = volumes[-1]
        ratio       = current_vol / avg_vol if avg_vol > 0 else 1.0

        return {
            "avg":    int(avg_vol),
            "current": current_vol,
            "ratio":  round(ratio, 2),
            "surge":  ratio >= 1.5,   # 거래량 급증 (평균 1.5배 이상)
            "dry":    ratio <= 0.5,   # 거래량 급감 (평균 50% 이하)
        }

    # =========================================================
    # 통합 분석
    # =========================================================
    def analyze(self, ohlcv: list) -> dict:
        """
        OHLCV 데이터로 전체 기술적 지표 계산
        ohlcv: [{"open", "high", "low", "close", "volume"}, ...]
        """
        if len(ohlcv) < 30:
            logger.warning("데이터 부족 (30봉 이상 필요)")
            return {}

        closes  = [r["close"] for r in ohlcv]
        volumes = [r["volume"] for r in ohlcv]

        rsi      = self.calc_rsi(closes)
        macd     = self.calc_macd(closes)
        bollinger = self.calc_bollinger(closes)
        ma       = self.calc_ma(closes)
        volume   = self.calc_volume(volumes)

        result = {
            "rsi":       rsi,
            "macd":      macd,
            "bollinger": bollinger,
            "ma":        ma,
            "volume":    volume,
            "price":     closes[-1],
        }

        logger.debug(
            f"기술적 분석 완료 | RSI={rsi} | "
            f"MACD={macd['cross'] if macd else 'N/A'} | "
            f"BB position={bollinger['position'] if bollinger else 'N/A'} | "
            f"MA cross={ma.get('ma_cross')} | "
            f"Vol ratio={volume['ratio']}"
        )
        return result
