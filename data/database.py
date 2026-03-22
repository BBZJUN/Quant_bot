"""
SQLite 데이터베이스 관리
- 거래 기록
- 포트폴리오 스냅샷
- 일일 수익률
"""

import sqlite3
from datetime import datetime
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))
from config.settings import DB_CONFIG
from utils.logger import get_logger

logger = get_logger(__name__)

DB_PATH = Path(__file__).parent.parent / DB_CONFIG["path"]


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """테이블 초기화"""
    with get_conn() as conn:
        conn.executescript("""
        -- 거래 기록
        CREATE TABLE IF NOT EXISTS trades (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT    NOT NULL,
            ticker      TEXT    NOT NULL,
            name        TEXT,
            action      TEXT    NOT NULL,   -- BUY / SELL
            quantity    INTEGER NOT NULL,
            price       INTEGER NOT NULL,
            amount      INTEGER NOT NULL,   -- quantity * price
            order_no    TEXT,
            strategy    TEXT,
            note        TEXT
        );

        -- 포트폴리오 일별 스냅샷
        CREATE TABLE IF NOT EXISTS portfolio_snapshots (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            date            TEXT    NOT NULL UNIQUE,
            total_eval      INTEGER,
            cash            INTEGER,
            stock_eval      INTEGER,
            total_profit    INTEGER,
            profit_rate     REAL,
            holdings_json   TEXT    -- JSON 문자열
        );

        -- 종목별 포지션
        CREATE TABLE IF NOT EXISTS positions (
            ticker      TEXT    PRIMARY KEY,
            name        TEXT,
            quantity    INTEGER,
            avg_price   REAL,
            entry_date  TEXT,
            strategy    TEXT,
            updated_at  TEXT
        );
        """)
    logger.info("DB 초기화 완료")


def record_trade(ticker: str, name: str, action: str,
                 quantity: int, price: int,
                 order_no: str = None, strategy: str = None, note: str = None):
    """거래 기록 저장"""
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO trades
               (timestamp, ticker, name, action, quantity, price, amount, order_no, strategy, note)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (datetime.now().isoformat(), ticker, name, action,
             quantity, price, quantity * price, order_no, strategy, note),
        )
    logger.info(f"거래 기록 [{action}] {ticker} {quantity}주 @{price:,}원")


def save_snapshot(total_eval: int, cash: int, stock_eval: int,
                  total_profit: int, profit_rate: float, holdings: list):
    """일별 포트폴리오 스냅샷 저장"""
    import json
    today = datetime.now().strftime("%Y-%m-%d")
    with get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO portfolio_snapshots
               (date, total_eval, cash, stock_eval, total_profit, profit_rate, holdings_json)
               VALUES (?,?,?,?,?,?,?)""",
            (today, total_eval, cash, stock_eval,
             total_profit, profit_rate, json.dumps(holdings, ensure_ascii=False)),
        )
    logger.info(f"스냅샷 저장 [{today}] 총평가: {total_eval:,}원, 수익률: {profit_rate:.2f}%")


def get_trade_history(days: int = 30) -> list:
    """최근 N일 거래 내역 조회"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?", (days * 10,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_snapshots(days: int = 30) -> list:
    """최근 N일 스냅샷 조회"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM portfolio_snapshots ORDER BY date DESC LIMIT ?", (days,)
        ).fetchall()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    init_db()
    print(f"DB 생성 완료: {DB_PATH}")
