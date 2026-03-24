"""
뉴스 수집 및 감성 분석
- 한국경제 / 연합뉴스 RSS 피드 수집 (네이버 금융 JS 렌더링 우회)
- 종목명 기반 필터링
- 긍정/부정 키워드 감성 점수 반환
"""

import requests
import xml.etree.ElementTree as ET
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))
from utils.logger import get_logger

logger = get_logger(__name__)

RSS_FEEDS = [
    "https://www.hankyung.com/feed/finance",
    "https://www.yna.co.kr/rss/economy.xml",
    "https://www.mk.co.kr/rss/30000001/",
]

NEGATIVE_KEYWORDS = [
    "하락", "급락", "폭락", "매도", "손실", "악재", "위기", "우려", "불안", "리스크",
    "소송", "제재", "조사", "횡령", "분식", "경고", "하향", "적자", "부진", "침체",
    "매도세", "하향조정", "목표가 하향", "실적 쇼크", "어닝 쇼크", "관리종목",
    "상장폐지", "주의", "경영 위기", "유동성 위기",
]

POSITIVE_KEYWORDS = [
    "상승", "급등", "호재", "매수", "수익", "성장", "기대", "긍정", "강세",
    "신고가", "상향", "흑자", "호실적", "수주", "계약", "신제품", "수출",
    "매수세", "상향조정", "목표가 상향", "어닝 서프라이즈", "실적 개선",
    "배당", "자사주", "바이백",
]

# 종목 코드 → 회사명 캐시 (외부에서 주입 가능)
_NAME_CACHE: dict = {}


def register_name(ticker: str, name: str):
    """종목 코드-회사명 매핑 등록"""
    _NAME_CACHE[ticker] = name


class NewsCollector:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        })

    def _fetch_rss(self, url: str) -> list[str]:
        """RSS 피드에서 기사 제목 수집"""
        try:
            resp = self.session.get(url, timeout=8)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            titles = []
            for item in root.findall(".//item"):
                title_el = item.find("title")
                if title_el is not None and title_el.text:
                    try:
                        titles.append(title_el.text.encode("latin1").decode("utf-8"))
                    except Exception:
                        titles.append(title_el.text)
            return titles
        except Exception as e:
            logger.warning(f"RSS 수집 실패 [{url}]: {e}")
            return []

    def get_news(self, ticker: str, max_articles: int = 10) -> list:
        """
        RSS 피드에서 종목 관련 기사 필터링
        returns: [{"title": str}, ...]
        """
        company_name = _NAME_CACHE.get(ticker, "")

        all_titles = []
        for feed_url in RSS_FEEDS:
            all_titles.extend(self._fetch_rss(feed_url))

        # 종목 코드 또는 회사명이 제목에 포함된 기사만 필터
        filtered = []
        for title in all_titles:
            if ticker in title or (company_name and company_name in title):
                filtered.append({"title": title})
            if len(filtered) >= max_articles:
                break

        logger.info(f"뉴스 수집 [{ticker}({company_name})]: {len(filtered)}건")
        return filtered

    def get_market_news(self, max_articles: int = 15) -> list:
        """시장 전체 뉴스 수집 (종목 필터 없음)"""
        all_titles = []
        for feed_url in RSS_FEEDS:
            all_titles.extend(self._fetch_rss(feed_url))

        articles = [{"title": t} for t in all_titles[:max_articles]]
        logger.info(f"시장 뉴스 수집: {len(articles)}건")
        return articles

    def sentiment_score(self, articles: list) -> float:
        """
        뉴스 감성 점수
        returns: -1.0 (매우 부정) ~ +1.0 (매우 긍정)
        """
        if not articles:
            return 0.0

        total_neg = 0
        total_pos = 0
        for article in articles:
            title = article.get("title", "")
            total_neg += sum(1 for kw in NEGATIVE_KEYWORDS if kw in title)
            total_pos += sum(1 for kw in POSITIVE_KEYWORDS if kw in title)

        total = total_neg + total_pos
        if total == 0:
            return 0.0

        score = (total_pos - total_neg) / total
        logger.debug(f"감성 점수: {score:.2f} (긍정 {total_pos}, 부정 {total_neg})")
        return round(score, 2)

    def analyze(self, ticker: str) -> dict:
        """
        종목 뉴스 수집 + 감성 분석 통합
        returns: {"articles": list, "sentiment": float, "signal": str}
        """
        articles  = self.get_news(ticker)
        sentiment = self.sentiment_score(articles)

        if sentiment <= -0.3:
            signal = "negative"
        elif sentiment >= 0.3:
            signal = "positive"
        else:
            signal = "neutral"

        return {
            "ticker":    ticker,
            "articles":  articles,
            "sentiment": sentiment,
            "signal":    signal,
        }
