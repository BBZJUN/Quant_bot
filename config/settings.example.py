# ============================================================
# settings.py 예시 파일 (깃허브 공유용)
# 실제 settings.py 는 절대 공유하지 마세요!
# ============================================================

KIS_CONFIG = {
    "mock": {
        "app_key":    "PSxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "app_secret": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "base_url":   "https://openapivts.koreainvestment.com:29443",
        "account_no": "50123456-01",
        "is_mock":    True,
    },
    "real": {
        "app_key":    "PSxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "app_secret": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "base_url":   "https://openapi.koreainvestment.com:9443",
        "account_no": "12345678-01",
        "is_mock":    False,
    },
}

ACTIVE_MODE = "mock"
