"""
API 연동 확인용 테스트
계좌 연동 후 가장 먼저 실행할 파일

실행: python tests/test_connection.py
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from data.kis_api import KISApi
from config.settings import ACTIVE_MODE
from utils.logger import get_logger

logger = get_logger("test_connection")


def test_token():
    """토큰 발급 테스트"""
    print("\n[1] 토큰 발급 테스트")
    try:
        api   = KISApi(ACTIVE_MODE)
        token = api.get_access_token()
        print(f"  ✅ 성공: {token[:20]}...")
        return api
    except Exception as e:
        print(f"  ❌ 실패: {e}")
        return None


def test_balance(api):
    """잔고 조회 테스트"""
    print("\n[2] 잔고 조회 테스트")
    try:
        balance = api.get_balance()
        print(f"  ✅ 총 평가금액 : {balance['total_eval']:,}원")
        print(f"     현금        : {balance['cash']:,}원")
        print(f"     보유 종목 수 : {len(balance['holdings'])}개")
    except Exception as e:
        print(f"  ❌ 실패: {e}")


def test_price(api):
    """현재가 조회 테스트 (삼성전자)"""
    print("\n[3] 현재가 조회 테스트 (삼성전자 005930)")
    try:
        data = api.get_current_price("005930", market="J")
        print(f"  ✅ 삼성전자 현재가: {data['current_price']:,}원")
        print(f"     등락률: {data['change_rate']:+.2f}%")
    except Exception as e:
        print(f"  ❌ 실패: {e}")


def test_ohlcv(api):
    """OHLCV 조회 테스트"""
    print("\n[4] OHLCV 조회 테스트 (삼성전자 최근 5일)")
    try:
        data = api.get_ohlcv("005930", period="D", market="J")[-5:]
        for row in data:
            print(f"  {row['date']}  종가: {row['close']:,}원  거래량: {row['volume']:,}")
        print("  ✅ 성공")
    except Exception as e:
        print(f"  ❌ 실패: {e}")


if __name__ == "__main__":
    print("=" * 50)
    print(f"  KIS API 연동 테스트  (모드: {ACTIVE_MODE})")
    print("=" * 50)

    api = test_token()
    if api:
        test_balance(api)
        test_price(api)
        test_ohlcv(api)

    print("\n" + "=" * 50)
    print("  테스트 완료")
    print("=" * 50)
