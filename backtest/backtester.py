"""
간단한 백테스트 엔진
- 과거 데이터로 전략 검증
- 연도별 수익률, MDD 계산
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))
from utils.logger import get_logger

logger = get_logger(__name__)


class Backtester:
    def __init__(self, initial_capital: int = 10_000_000):
        self.capital = initial_capital

    def run(self, price_df: pd.DataFrame, signals: pd.Series) -> pd.DataFrame:
        """
        price_df: DataFrame(index=date, columns=tickers)
        signals : Series(index=date, values= list of tickers to hold)
        Returns : DataFrame with daily portfolio values
        """
        portfolio_values = []
        cash    = self.capital
        holdings = {}   # {ticker: quantity}

        dates = price_df.index.tolist()

        for i, date in enumerate(dates):
            target_tickers = signals.get(date, [])

            if target_tickers is not None:
                # 전량 매도
                for ticker, qty in list(holdings.items()):
                    price = price_df.loc[date, ticker] if ticker in price_df.columns else 0
                    cash += qty * price * 0.9975  # 매도 수수료 0.25%
                holdings = {}

                # 목표 종목 매수
                if target_tickers:
                    weight    = 1.0 / len(target_tickers)
                    per_stock = cash * weight
                    for ticker in target_tickers:
                        if ticker not in price_df.columns:
                            continue
                        price = price_df.loc[date, ticker]
                        if price <= 0:
                            continue
                        qty  = int(per_stock // price)
                        cost = qty * price * 1.00015  # 매수 수수료 0.015%
                        if cost <= cash:
                            holdings[ticker] = qty
                            cash -= cost

            # 평가금액 계산
            stock_eval = sum(
                holdings.get(t, 0) * price_df.loc[date, t]
                for t in holdings
                if t in price_df.columns
            )
            total_eval = cash + stock_eval
            portfolio_values.append({
                "date":       date,
                "total_eval": total_eval,
                "cash":       cash,
                "stock_eval": stock_eval,
            })

        result = pd.DataFrame(portfolio_values).set_index("date")
        return result

    def calc_metrics(self, result: pd.DataFrame) -> dict:
        """성과 지표 계산"""
        values = result["total_eval"]
        returns = values.pct_change().dropna()

        total_return = (values.iloc[-1] / values.iloc[0]) - 1
        days         = (result.index[-1] - result.index[0]).days
        annual_return = (1 + total_return) ** (365 / days) - 1 if days > 0 else 0

        rolling_max  = values.cummax()
        drawdown     = (values - rolling_max) / rolling_max
        mdd          = drawdown.min()

        sharpe = (returns.mean() / returns.std() * np.sqrt(252)) if returns.std() > 0 else 0

        metrics = {
            "total_return":  f"{total_return:.2%}",
            "annual_return": f"{annual_return:.2%}",
            "mdd":           f"{mdd:.2%}",
            "sharpe":        f"{sharpe:.2f}",
            "start_capital": f"{values.iloc[0]:,.0f}원",
            "end_capital":   f"{values.iloc[-1]:,.0f}원",
        }

        logger.info("=" * 40)
        logger.info("백테스트 결과")
        for k, v in metrics.items():
            logger.info(f"  {k}: {v}")
        logger.info("=" * 40)

        return metrics
