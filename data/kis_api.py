"""
한국투자증권 KIS API 클라이언트
- 토큰 발급 / 갱신
- 시세 조회
- 잔고 / 계좌 조회
- 주문 실행
"""

import requests
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))
from config.settings import KIS_CONFIG, ACTIVE_MODE
from utils.logger import get_logger

logger = get_logger(__name__)


class KISApi:
    def __init__(self, mode: str = ACTIVE_MODE):
        cfg = KIS_CONFIG[mode]
        self.app_key    = cfg["app_key"]
        self.app_secret = cfg["app_secret"]
        self.base_url   = cfg["base_url"]
        self.account_no = cfg["account_no"]
        self.is_mock    = cfg["is_mock"]

        self.access_token     = None
        self.token_expired_at = None

        # 계좌번호 분리 (앞 8자리 / 뒤 2자리)
        parts = self.account_no.replace("-", "")
        self.cano         = parts[:8]
        self.acnt_prdt_cd = parts[8:] if len(parts) > 8 else "01"

    # =========================================================
    # 인증
    # =========================================================
    def get_access_token(self) -> str:
        """액세스 토큰 발급 (만료 전 자동 갱신)"""
        if self.access_token and self.token_expired_at:
            if datetime.now() < self.token_expired_at:
                return self.access_token

        url  = f"{self.base_url}/oauth2/tokenP"
        body = {
            "grant_type": "client_credentials",
            "appkey":     self.app_key,
            "appsecret":  self.app_secret,
        }
        resp = requests.post(url, json=body, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        self.access_token     = data["access_token"]
        self.token_expired_at = datetime.now() + timedelta(hours=1, minutes=50)
        logger.info("KIS 액세스 토큰 발급 완료")
        return self.access_token

    def _headers(self, tr_id: str, extra: dict = None) -> dict:
        headers = {
            "content-type":  "application/json; charset=utf-8",
            "authorization": f"Bearer {self.get_access_token()}",
            "appkey":        self.app_key,
            "appsecret":     self.app_secret,
            "tr_id":         tr_id,
            "custtype":      "P",
        }
        if extra:
            headers.update(extra)
        return headers

    # =========================================================
    # 시세 조회
    # =========================================================
    def get_current_price(self, ticker: str, market: str = "J") -> dict:
        """
        현재가 조회
        market: J=코스피, Q=코스닥
        """
        url    = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
        params = {
            "FID_COND_MRKT_DIV_CODE": market,
            "FID_INPUT_ISCD":         ticker,
        }
        resp = requests.get(url, headers=self._headers("FHKST01010100"),
                            params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("rt_cd") != "0":
            logger.error(f"시세 조회 실패 [{ticker}]: {data.get('msg1')}")
            return {}

        o = data.get("output", {})
        return {
            "ticker":        ticker,
            "current_price": int(o.get("stck_prpr", 0)),
            "open_price":    int(o.get("stck_oprc", 0)),
            "high_price":    int(o.get("stck_hgpr", 0)),
            "low_price":     int(o.get("stck_lwpr", 0)),
            "volume":        int(o.get("acml_vol", 0)),
            "change_rate":   float(o.get("prdy_ctrt", 0)),
            "market_cap":    int(o.get("hts_avls", 0)) * 100_000_000,
            "pbr":           float(o.get("pbr", 0) or 0),
            "per":           float(o.get("per", 0) or 0),
            "eps":           float(o.get("eps", 0) or 0),
            "timestamp":     datetime.now().isoformat(),
        }

    def get_ohlcv(self, ticker: str, period: str = "D",
                  start: str = None, end: str = None,
                  market: str = "J") -> list:
        """
        OHLCV (일/주/월봉)
        period : D=일봉, W=주봉, M=월봉
        start/end : "YYYYMMDD"
        """
        if not end:
            end = datetime.now().strftime("%Y%m%d")
        if not start:
            start = (datetime.now() - timedelta(days=400)).strftime("%Y%m%d")

        url    = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",  # 국내 주식은 KOSPI/KOSDAQ 무관하게 J
            "FID_INPUT_ISCD":         ticker,
            "FID_INPUT_DATE_1":       start,
            "FID_INPUT_DATE_2":       end,
            "FID_PERIOD_DIV_CODE":    period,
            "FID_ORG_ADJ_PRC":        "1",   # 수정주가
        }
        resp = requests.get(url, headers=self._headers("FHKST03010100"),
                            params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("rt_cd") != "0":
            logger.error(f"OHLCV 조회 실패 [{ticker}]: {data.get('msg1')}")
            return []

        result = [
            {
                "date":   r.get("stck_bsop_date"),
                "open":   int(r.get("stck_oprc", 0)),
                "high":   int(r.get("stck_hgpr", 0)),
                "low":    int(r.get("stck_lwpr", 0)),
                "close":  int(r.get("stck_clpr", 0)),
                "volume": int(r.get("acml_vol", 0)),
            }
            for r in data.get("output2", [])
        ]
        return sorted(result, key=lambda x: x["date"])

    # =========================================================
    # 계좌 조회
    # =========================================================
    def get_balance(self) -> dict:
        """잔고 및 보유 종목 조회"""
        tr_id = "VTTC8434R" if self.is_mock else "TTTC8434R"
        url   = f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-balance"
        params = {
            "CANO":                  self.cano,
            "ACNT_PRDT_CD":         self.acnt_prdt_cd,
            "AFHR_FLPR_YN":         "N",
            "OFL_YN":               "",
            "INQR_DVSN":            "02",
            "UNPR_DVSN":            "01",
            "FUND_STTL_ICLD_YN":    "N",
            "FNCG_AMT_AUTO_RDPT_YN":"N",
            "PRCS_DVSN":            "01",
            "CTX_AREA_FK100":       "",
            "CTX_AREA_NK100":       "",
        }
        resp = requests.get(url, headers=self._headers(tr_id),
                            params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("rt_cd") != "0":
            logger.error(f"잔고 조회 실패: {data.get('msg1')}")
            return {}

        holdings = [
            {
                "ticker":        item.get("pdno"),
                "name":          item.get("prdt_name"),
                "quantity":      int(item.get("hldg_qty", 0)),
                "avg_price":     float(item.get("pchs_avg_pric", 0)),
                "current_price": int(item.get("prpr", 0)),
                "eval_amount":   int(item.get("evlu_amt", 0)),
                "profit_rate":   float(item.get("evlu_pfls_rt", 0)),
            }
            for item in data.get("output1", [])
            if int(item.get("hldg_qty", 0)) > 0
        ]

        s = data.get("output2", [{}])[0]
        return {
            "holdings":          holdings,
            "total_eval":        int(s.get("tot_evlu_amt", 0)),
            "cash":              int(s.get("dnca_tot_amt", 0)),
            "total_profit":      int(s.get("evlu_pfls_smtl_amt", 0)),
            "total_profit_rate": float(s.get("asst_icdc_erng_rt", 0)),
        }

    # =========================================================
    # 주문
    # =========================================================
    def get_investor_trend(self, ticker: str, market: str = "J") -> dict:
        """
        기관/외국인/개인 순매수 조회 (최근 5거래일 합산)
        returns: {"institution": int, "foreign": int, "individual": int}
        양수 = 순매수, 음수 = 순매도
        """
        url    = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-investor"
        params = {
            "FID_COND_MRKT_DIV_CODE": market,
            "FID_INPUT_ISCD":         ticker,
        }
        try:
            resp = requests.get(url, headers=self._headers("FHKST01010900"),
                                params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            if data.get("rt_cd") != "0" or not data.get("output"):
                return {"institution": 0, "foreign": 0, "individual": 0}

            institution = 0
            foreign     = 0
            individual  = 0
            for row in data["output"][:5]:  # 최근 5일
                institution += int(row.get("orgn_ntby_qty",  0) or 0)
                foreign     += int(row.get("frgn_ntby_qty",  0) or 0)
                individual  += int(row.get("indv_ntby_qty",  0) or 0)

            logger.debug(
                f"수급 [{ticker}] 기관={institution:+,} 외국인={foreign:+,} 개인={individual:+,}"
            )
            return {
                "institution": institution,
                "foreign":     foreign,
                "individual":  individual,
            }
        except Exception as e:
            logger.warning(f"수급 조회 실패 [{ticker}]: {e}")
            return {"institution": 0, "foreign": 0, "individual": 0}

    def buy_market(self, ticker: str, quantity: int) -> dict:
        """시장가 매수"""
        return self._order(ticker, quantity, order_type="01", is_buy=True)

    def sell_market(self, ticker: str, quantity: int) -> dict:
        """시장가 매도"""
        return self._order(ticker, quantity, order_type="01", is_buy=False)

    def buy_limit(self, ticker: str, quantity: int, price: int) -> dict:
        """지정가 매수"""
        return self._order(ticker, quantity, order_type="00",
                           price=price, is_buy=True)

    def sell_limit(self, ticker: str, quantity: int, price: int) -> dict:
        """지정가 매도"""
        return self._order(ticker, quantity, order_type="00",
                           price=price, is_buy=False)

    def _order(self, ticker: str, quantity: int, order_type: str,
               price: int = 0, is_buy: bool = True) -> dict:
        if self.is_mock:
            tr_id = "VTTC0802U" if is_buy else "VTTC0801U"
        else:
            tr_id = "TTTC0802U" if is_buy else "TTTC0801U"

        url  = f"{self.base_url}/uapi/domestic-stock/v1/trading/order-cash"
        body = {
            "CANO":          self.cano,
            "ACNT_PRDT_CD": self.acnt_prdt_cd,
            "PDNO":          ticker,
            "ORD_DVSN":      order_type,   # 00=지정가, 01=시장가
            "ORD_QTY":       str(quantity),
            "ORD_UNPR":      str(price),
        }
        action = "매수" if is_buy else "매도"
        logger.info(f"주문 요청 [{action}] {ticker} {quantity}주 (가격:{price})")

        resp = requests.post(url, headers=self._headers(tr_id),
                             json=body, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("rt_cd") != "0":
            logger.error(f"주문 실패 [{ticker}]: {data.get('msg1')}")
            return {"success": False, "message": data.get("msg1")}

        output = data.get("output", {})
        logger.info(f"주문 완료 [{action}] {ticker} 주문번호: {output.get('ODNO')}")
        return {
            "success":   True,
            "order_no":  output.get("ODNO"),
            "ticker":    ticker,
            "quantity":  quantity,
            "action":    action,
            "timestamp": datetime.now().isoformat(),
        }
