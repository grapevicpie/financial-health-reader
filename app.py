
import io
import re
from html import escape
from quality_checks import (
    dart_request_signature,
    matching_saved_analysis,
    missing_score_fields,
    verify_dart_rows,
)
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime

import numpy as np
import pandas as pd
import requests
import streamlit as st


# ============================================================
# Page setup
# ============================================================

st.set_page_config(
    page_title="기업 재무 건강검진",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root {
        --bg: #f7f8fb;
        --card: rgba(255, 255, 255, 0.92);
        --ink: #1f2937;
        --muted: #667085;
        --line: rgba(31, 41, 55, 0.10);
        --good: #0f8a5f;
        --warn: #c77700;
        --risk: #cf2e2e;
        --blue: #3366ff;
        --purple: #7c3aed;
    }

    .block-container {
        padding-top: 1.1rem;
        padding-bottom: 4.2rem;
        max-width: 1180px;
    }

    header[data-testid="stHeader"] {
        background: rgba(255, 255, 255, 0);
    }

    .app-hero {
        border-radius: 28px;
        padding: 1.45rem 1.55rem;
        background:
            radial-gradient(circle at top left, rgba(51, 102, 255, 0.20), transparent 34%),
            radial-gradient(circle at bottom right, rgba(124, 58, 237, 0.18), transparent 38%),
            linear-gradient(135deg, #ffffff 0%, #f5f7ff 52%, #f9f6ff 100%);
        border: 1px solid rgba(51, 102, 255, 0.12);
        box-shadow: 0 18px 50px rgba(31, 41, 55, 0.07);
        margin-bottom: 1.05rem;
    }

    .hero-pill {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        border-radius: 999px;
        padding: 0.28rem 0.62rem;
        font-size: 0.83rem;
        font-weight: 700;
        color: #2543b8;
        background: rgba(51, 102, 255, 0.10);
        border: 1px solid rgba(51, 102, 255, 0.12);
        margin-bottom: 0.65rem;
    }

    .main-title {
        font-size: 2.08rem;
        line-height: 1.2;
        font-weight: 900;
        letter-spacing: -0.04em;
        color: var(--ink);
        margin: 0;
    }

    .sub-title {
        color: var(--muted);
        font-size: 1.01rem;
        line-height: 1.65;
        max-width: 850px;
        margin-top: 0.62rem;
    }

    .hero-mini-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 0.65rem;
        margin-top: 1.0rem;
    }

    .mini-card {
        border-radius: 18px;
        background: rgba(255,255,255,0.76);
        border: 1px solid rgba(31,41,55,0.08);
        padding: 0.78rem 0.84rem;
    }

    .mini-icon {
        font-size: 1.3rem;
        margin-bottom: 0.22rem;
    }

    .mini-title {
        font-weight: 800;
        font-size: 0.92rem;
        color: #202939;
    }

    .mini-desc {
        margin-top: 0.16rem;
        color: #667085;
        font-size: 0.82rem;
        line-height: 1.35;
    }

    .section-title {
        font-size: 1.18rem;
        font-weight: 850;
        letter-spacing: -0.02em;
        margin: 0.8rem 0 0.4rem 0;
        color: #202939;
    }

    .soft-card {
        border-radius: 24px;
        padding: 1.05rem 1.1rem;
        background: var(--card);
        border: 1px solid var(--line);
        box-shadow: 0 10px 28px rgba(31, 41, 55, 0.055);
        margin-bottom: 0.86rem;
    }

    .result-card {
        border-radius: 26px;
        padding: 1.1rem 1.15rem;
        background:
            linear-gradient(135deg, rgba(255,255,255,0.96), rgba(247,250,255,0.95));
        border: 1px solid rgba(51, 102, 255, 0.13);
        box-shadow: 0 16px 44px rgba(31, 41, 55, 0.08);
        margin: 0.8rem 0 1rem 0;
    }

    .summary-title {
        font-size: 0.92rem;
        font-weight: 800;
        color: #3366ff;
        margin-bottom: 0.38rem;
    }

    .summary-text {
        font-size: 1.04rem;
        line-height: 1.72;
        color: #202939;
        font-weight: 520;
    }

    .badge {
        display: inline-flex;
        align-items: center;
        gap: 0.25rem;
        border-radius: 999px;
        padding: 0.28rem 0.62rem;
        font-size: 0.83rem;
        font-weight: 800;
        margin-right: 0.26rem;
        margin-bottom: 0.26rem;
        border: 1px solid rgba(31,41,55,0.08);
    }
    .badge-good { background: #eaf8f1; color: #08724d; }
    .badge-warn { background: #fff7e6; color: #9a5b00; }
    .badge-risk { background: #fff0f0; color: #b42318; }
    .badge-info { background: #edf3ff; color: #2543b8; }

    .gauge-wrap {
        width: 100%;
        height: 13px;
        background: #eceff5;
        border-radius: 999px;
        overflow: hidden;
        margin-top: 0.55rem;
    }
    .gauge-fill {
        height: 13px;
        border-radius: 999px;
        background: linear-gradient(90deg, #ff6b6b 0%, #ffc857 45%, #22c55e 100%);
    }

    .signal-item {
        display: flex;
        gap: 0.62rem;
        align-items: flex-start;
        padding: 0.72rem 0.74rem;
        border: 1px solid rgba(31,41,55,0.08);
        border-radius: 18px;
        background: rgba(255,255,255,0.74);
        margin-bottom: 0.5rem;
    }
    .signal-icon {
        font-size: 1.08rem;
        line-height: 1.35;
    }
    .signal-text {
        color: #344054;
        font-size: 0.94rem;
        line-height: 1.55;
    }

    .legal-box {
        border-radius: 20px;
        padding: 0.95rem 1.0rem;
        background: #fbfcff;
        border: 1px dashed rgba(51,102,255,0.24);
        color: #475467;
        line-height: 1.6;
        font-size: 0.92rem;
    }

    .small-caption {
        color: #667085;
        font-size: 0.86rem;
        line-height: 1.55;
    }

    div.stButton > button {
        width: 100%;
        min-height: 3.05rem;
        border-radius: 16px;
        font-weight: 850;
        border: 1px solid rgba(51,102,255,0.18);
        box-shadow: 0 8px 20px rgba(51,102,255,0.08);
    }

    div.stDownloadButton > button {
        width: 100%;
        min-height: 3.0rem;
        border-radius: 16px;
        font-weight: 800;
    }

    div[data-testid="stMetric"] {
        background: rgba(255,255,255,0.88);
        border: 1px solid rgba(31,41,55,0.08);
        border-radius: 20px;
        padding: 0.9rem 0.95rem;
        box-shadow: 0 8px 22px rgba(31, 41, 55, 0.055);
    }

    div[data-testid="stMetricValue"] {
        font-size: 1.45rem;
        font-weight: 900;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 0.42rem;
        overflow-x: auto;
        padding-bottom: 0.25rem;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 999px;
        padding: 0.55rem 0.88rem;
        background: rgba(255,255,255,0.76);
        border: 1px solid rgba(31,41,55,0.08);
        font-weight: 750;
        white-space: nowrap;
    }

    .stTabs [aria-selected="true"] {
        background: #edf3ff;
        color: #2543b8;
        border-color: rgba(51,102,255,0.25);
    }

    div[data-testid="stDataFrame"] {
        border-radius: 18px;
        overflow: hidden;
    }

    .footer-space {
        height: 2.0rem;
    }

    @media (max-width: 800px) {
        .block-container {
            padding-left: 0.78rem;
            padding-right: 0.78rem;
            padding-top: 0.72rem;
        }
        .app-hero {
            border-radius: 22px;
            padding: 1.05rem 1.0rem;
        }
        .main-title {
            font-size: 1.55rem;
        }
        .sub-title {
            font-size: 0.92rem;
            line-height: 1.55;
        }
        .hero-mini-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.55rem;
        }
        .mini-card {
            border-radius: 16px;
            padding: 0.7rem 0.72rem;
        }
        .mini-title {
            font-size: 0.86rem;
        }
        .mini-desc {
            font-size: 0.78rem;
        }
        .soft-card, .result-card {
            border-radius: 20px;
            padding: 0.9rem 0.88rem;
        }
        div[data-testid="stMetric"] {
            padding: 0.72rem 0.72rem;
        }
        div[data-testid="stMetricValue"] {
            font-size: 1.22rem;
        }
        div.stButton > button {
            min-height: 3.2rem;
            border-radius: 15px;
        }
        textarea {
            font-size: 0.92rem !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# Data definitions
# ============================================================

ACCOUNT_ALIASES = {
    "revenue": ["매출액", "매출", "수익(매출액)", "영업수익", "수익", "sales", "revenue", "total revenue"],
    "gross_profit": ["매출총이익", "gross profit"],
    "operating_income": ["영업이익", "영업손실", "영업이익(손실)", "operating income", "operating profit", "income from operations"],
    "net_income": ["당기순이익", "당기순손실", "당기순이익(손실)", "분기순이익", "반기순이익", "연결당기순이익", "net income", "profit for the period", "profit"],
    "total_assets": ["자산총계", "총자산", "total assets"],
    "total_liabilities": ["부채총계", "총부채", "total liabilities"],
    "total_equity": ["자본총계", "총자본", "자본총계(지배기업 소유주지분)", "equity", "total equity", "shareholders equity"],
    "current_assets": ["유동자산", "current assets"],
    "current_liabilities": ["유동부채", "current liabilities"],
    "cash": ["현금및현금성자산", "현금 및 현금성자산", "cash and cash equivalents", "cash"],
    "inventory": ["재고자산", "inventories", "inventory"],
    "accounts_receivable": ["매출채권", "매출채권 및 기타채권", "매출채권및기타채권", "trade receivables", "accounts receivable", "receivables"],
    "borrowings": ["차입금", "단기차입금", "장기차입금", "사채", "유동성장기부채", "borrowings", "short-term borrowings", "long-term borrowings", "bonds payable"],
    "interest_expense": ["이자비용", "finance costs", "interest expense"],
    "operating_cf": ["영업활동현금흐름", "영업활동으로 인한 현금흐름", "영업활동 현금흐름", "net cash from operating activities", "cash flows from operating activities"],
    "investing_cf": ["투자활동현금흐름", "투자활동으로 인한 현금흐름", "투자활동 현금흐름", "net cash used in investing activities", "cash flows from investing activities"],
    "financing_cf": ["재무활동현금흐름", "재무활동으로 인한 현금흐름", "재무활동 현금흐름", "net cash from financing activities", "cash flows from financing activities"],
    "capex": ["유형자산의 취득", "유형자산 취득", "유형자산의 증가", "purchase of property", "acquisition of property", "capital expenditures", "capex"],
    "dividends": ["배당금", "배당금지급", "dividends paid"],
    "eps": ["주당순이익", "기본주당순이익", "희석주당순이익", "eps", "basic earnings per share"],
    "bps": ["주당순자산", "bps", "book value per share"],
}

STATEMENT_NAME_MAP = {
    "BS": "재무상태표",
    "IS": "손익계산서",
    "CIS": "포괄손익계산서",
    "CF": "현금흐름표",
    "SCE": "자본변동표",
}

REPORT_CODES = {
    "사업보고서": "11011",
    "반기보고서": "11012",
    "1분기보고서": "11013",
    "3분기보고서": "11014",
}

# 사용자가 회사명을 여러 방식으로 입력해도 찾을 수 있도록 자주 쓰는 별칭을 먼저 정리합니다.
# OpenDART 자동 조회에는 최종적으로 OpenDART API 키가 필요하지만,
# 검색어 보정은 앱 안에서 먼저 수행합니다.
COMPANY_ALIASES = {
    "삼성전자": {
        "stock_code": "005930",
        "canonical_name": "삼성전자",
        "aliases": ["삼성전자", "삼전", "samsung electronics", "samsung", "005930"],
    },
    "SK하이닉스": {
        "stock_code": "000660",
        "canonical_name": "SK하이닉스",
        "aliases": [
            "SK하이닉스", "sk하이닉스", "에스케이하이닉스", "에스케이 하이닉스",
            "하이닉스", "sk hynix", "skhynix", "hynix", "000660"
        ],
    },
    "NAVER": {
        "stock_code": "035420",
        "canonical_name": "NAVER",
        "aliases": ["NAVER", "네이버", "naver", "035420"],
    },
    "카카오": {
        "stock_code": "035720",
        "canonical_name": "카카오",
        "aliases": ["카카오", "kakao", "035720"],
    },
    "현대차": {
        "stock_code": "005380",
        "canonical_name": "현대자동차",
        "aliases": ["현대차", "현대자동차", "hyundai motor", "hyundai", "005380"],
    },
    "기아": {
        "stock_code": "000270",
        "canonical_name": "기아",
        "aliases": ["기아", "kia", "kia motors", "000270"],
    },
    "LG에너지솔루션": {
        "stock_code": "373220",
        "canonical_name": "LG에너지솔루션",
        "aliases": ["LG에너지솔루션", "엘지에너지솔루션", "lg energy solution", "lges", "373220"],
    },
    "LG전자": {
        "stock_code": "066570",
        "canonical_name": "LG전자",
        "aliases": ["LG전자", "엘지전자", "lg electronics", "066570"],
    },
    "삼성SDI": {
        "stock_code": "006400",
        "canonical_name": "삼성SDI",
        "aliases": ["삼성SDI", "삼성 sdi", "samsung sdi", "006400"],
    },
    "셀트리온": {
        "stock_code": "068270",
        "canonical_name": "셀트리온",
        "aliases": ["셀트리온", "celltrion", "068270"],
    },
    "포스코홀딩스": {
        "stock_code": "005490",
        "canonical_name": "POSCO홀딩스",
        "aliases": ["포스코", "포스코홀딩스", "posco", "posco holdings", "005490"],
    },
    "한화에어로스페이스": {
        "stock_code": "012450",
        "canonical_name": "한화에어로스페이스",
        "aliases": ["한화에어로스페이스", "한화 에어로스페이스", "hanwha aerospace", "012450"],
    },
    "두산에너빌리티": {
        "stock_code": "034020",
        "canonical_name": "두산에너빌리티",
        "aliases": ["두산에너빌리티", "두산 에너빌리티", "doosan energi", "doosan enerbility", "034020"],
    },
    "삼성바이오로직스": {
        "stock_code": "207940",
        "canonical_name": "삼성바이오로직스",
        "aliases": ["삼성바이오로직스", "삼바", "samsung biologics", "207940"],
    },
}

UNIT_MULTIPLIER = {"원": 1, "천원": 1_000, "백만원": 1_000_000, "억원": 100_000_000}

SAMPLE_TABLES = {
    "손익계산서": """항목\t2022\t2023\t2024
매출액\t120000\t138000\t155000
매출총이익\t42000\t47000\t55000
영업이익\t13000\t11500\t18500
당기순이익\t9000\t8200\t14000""",
    "재무상태표": """항목\t2022\t2023\t2024
자산총계\t260000\t285000\t320000
부채총계\t105000\t128000\t150000
자본총계\t155000\t157000\t170000
유동자산\t88000\t91000\t103000
유동부채\t52000\t63000\t70000
현금및현금성자산\t18000\t16000\t22000
재고자산\t21000\t29000\t37000
매출채권\t16000\t21000\t30000
차입금\t38000\t52000\t65000""",
    "현금흐름표": """항목\t2022\t2023\t2024
영업활동현금흐름\t11000\t6500\t9000
투자활동현금흐름\t-18000\t-21000\t-26000
재무활동현금흐름\t6000\t12000\t9000
유형자산의 취득\t-15000\t-19000\t-23000
배당금지급\t-1500\t-1800\t-2000""",
    "자본변동표": """항목\t2022\t2023\t2024
자본금\t5000\t5000\t5000
이익잉여금\t90000\t96000\t108000
기타자본항목\t60000\t56000\t57000
자본총계\t155000\t157000\t170000""",
    "주석": """주석 예시:
- 회사는 주요 생산설비 증설을 위해 장기차입금을 신규 조달하였습니다.
- 일부 거래처에 대한 매출채권 회수 기간이 길어져 대손충당금을 추가 설정하였습니다.
- 재고자산 평가손실이 전기 대비 증가했습니다.
- 계류 중인 소송이 있으나 회사는 재무제표에 미치는 영향이 제한적이라고 판단하고 있습니다."""
}


# ============================================================
# Helpers
# ============================================================

def clean_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def normalize_key(text: str) -> str:
    text = clean_text(text).lower()
    text = re.sub(r"[\s\(\)\[\]\{\},·ㆍ/_\-:;'\"“”‘’]", "", text)
    return text


def resolve_company_alias(query: str):
    """회사명/별칭/종목코드를 표준 회사명과 종목코드로 보정합니다."""
    q = normalize_key(query)
    if not q:
        return None

    for _, info in COMPANY_ALIASES.items():
        aliases = info.get("aliases", [])
        alias_keys = [normalize_key(a) for a in aliases]
        stock_code = str(info.get("stock_code", "")).strip()

        if q == normalize_key(stock_code):
            return info

        for ak in alias_keys:
            if not ak:
                continue
            if q == ak or q in ak or ak in q:
                return info

    return None


def make_company_badge(company_info: dict | None):
    if not company_info:
        return "분석 기업: 직접 입력 자료"
    name = company_info.get("corp_name") or company_info.get("canonical_name") or company_info.get("query") or "직접 입력 자료"
    stock_code = company_info.get("stock_code") or ""
    report = company_info.get("report") or ""
    year = company_info.get("year") or ""
    suffix_parts = []
    if stock_code:
        suffix_parts.append(f"종목코드 {stock_code}")
    if year:
        suffix_parts.append(f"{year}년")
    if report:
        suffix_parts.append(report)
    suffix = " · ".join(suffix_parts)
    return f"분석 기업: {name}" + (f" ({suffix})" if suffix else "")


def parse_amount(value, multiplier=1):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return np.nan
    raw = str(value).strip()
    if raw == "" or raw in {"-", "—", "–", "N/A", "nan", "None"}:
        return np.nan

    negative = False
    if raw.startswith("(") and raw.endswith(")"):
        negative = True
        raw = raw[1:-1]
    if "△" in raw or "▲" in raw:
        negative = True

    raw = raw.replace(",", "")
    raw = raw.replace("원", "").replace("천", "").replace("백만", "").replace("억원", "")
    raw = raw.replace("△", "").replace("▲", "")
    raw = re.sub(r"[^0-9.\-]", "", raw)

    if raw in {"", "-", "."}:
        return np.nan

    try:
        num = float(raw)
        if negative and num > 0:
            num = -num
        return num * multiplier
    except ValueError:
        return np.nan


def fmt_amount(x):
    if x is None or pd.isna(x):
        return "확인 필요"
    x = float(x)
    sign = "-" if x < 0 else ""
    ax = abs(x)
    if ax >= 1_000_000_000_000:
        return f"{sign}{ax / 1_000_000_000_000:,.1f}조원"
    if ax >= 100_000_000:
        return f"{sign}{ax / 100_000_000:,.1f}억원"
    if ax >= 10_000:
        return f"{sign}{ax / 10_000:,.1f}만원"
    return f"{x:,.0f}원"


def fmt_pct(x):
    if x is None or pd.isna(x) or np.isinf(x):
        return "확인 필요"
    return f"{x * 100:.1f}%"


def safe_div(a, b):
    if a is None or b is None or pd.isna(a) or pd.isna(b) or b == 0:
        return np.nan
    return a / b


def growth_rate(now, prev):
    if now is None or prev is None or pd.isna(now) or pd.isna(prev) or prev == 0:
        return np.nan
    return (now - prev) / abs(prev)


def infer_period_sort(period):
    s = str(period)
    m = re.search(r"(20\d{2}|19\d{2})", s)
    if m:
        return int(m.group(1))
    order = {"당기": 3000, "당기금액": 3000, "당기누적": 3000, "전기": 2999, "전기금액": 2999, "전기누적": 2999, "전전기": 2998}
    for k, v in order.items():
        if k in s:
            return v
    nums = re.findall(r"\d+", s)
    return int(nums[0]) if nums else 0


def find_account_value(long_df: pd.DataFrame, metric: str, period: str | None = None):
    if long_df.empty:
        return np.nan
    aliases = ACCOUNT_ALIASES.get(metric, [])
    if not aliases:
        return np.nan

    alias_keys = [normalize_key(x) for x in aliases]
    candidates = long_df.copy()
    candidates["account_key"] = candidates["account"].map(normalize_key)

    mask = pd.Series(False, index=candidates.index)
    for key in alias_keys:
        mask = mask | candidates["account_key"].str.contains(re.escape(key), na=False)

    candidates = candidates[mask]
    if period is not None:
        candidates = candidates[candidates["period"].astype(str) == str(period)]
    candidates = candidates.dropna(subset=["amount"])

    if candidates.empty:
        return np.nan

    candidates["name_len"] = candidates["account"].astype(str).str.len()
    candidates = candidates.sort_values(["period_sort", "name_len"], ascending=[False, True])
    return float(candidates.iloc[0]["amount"])


def guess_statement_name(name: str):
    s = str(name)
    if any(k in s for k in ["손익", "Income", "IS", "PL", "P/L"]):
        return "손익계산서"
    if any(k in s for k in ["상태", "Balance", "BS", "재무상태"]):
        return "재무상태표"
    if any(k in s for k in ["현금", "Cash", "CF"]):
        return "현금흐름표"
    if any(k in s for k in ["자본", "Equity", "SCE"]):
        return "자본변동표"
    return s or "재무표"


def wide_to_long(df: pd.DataFrame, statement_name: str, multiplier=1, source="입력") -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["statement", "account", "period", "amount", "raw_value", "source", "period_sort"])

    df = df.copy()
    df = df.dropna(how="all")
    df.columns = [str(c).strip() for c in df.columns]

    if df.empty or df.shape[1] < 2:
        return pd.DataFrame(columns=["statement", "account", "period", "amount", "raw_value", "source", "period_sort"])

    account_col = None
    for col in df.columns:
        key = normalize_key(col)
        if any(k in key for k in ["항목", "계정", "account", "과목", "구분", "item"]):
            account_col = col
            break

    if account_col is None:
        best_col = df.columns[0]
        best_score = -1
        for col in df.columns:
            vals = df[col].astype(str)
            non_numeric_score = vals.map(lambda x: pd.isna(parse_amount(x)) if x.strip() else True).mean()
            if non_numeric_score > best_score:
                best_score = non_numeric_score
                best_col = col
        account_col = best_col

    rows = []
    for _, r in df.iterrows():
        account = clean_text(r.get(account_col))
        if not account:
            continue
        for col in df.columns:
            if col == account_col:
                continue
            raw = r.get(col)
            amt = parse_amount(raw, multiplier=multiplier)
            if pd.isna(amt):
                continue
            period = str(col).strip()
            rows.append({
                "statement": statement_name,
                "account": account,
                "period": period,
                "amount": amt,
                "raw_value": raw,
                "source": source,
                "period_sort": infer_period_sort(period),
            })

    return pd.DataFrame(rows)


def parse_pasted_table(text: str, statement_name: str, multiplier=1) -> pd.DataFrame:
    text = text.strip()
    if not text:
        return pd.DataFrame(columns=["statement", "account", "period", "amount", "raw_value", "source", "period_sort"])

    attempts = []
    for sep in [None, "\t", ",", ";", r"\s{2,}", r"\s+"]:
        try:
            df = pd.read_csv(io.StringIO(text), sep=sep, engine="python")
            if df.shape[1] >= 2:
                attempts.append(df)
        except Exception:
            pass

    if attempts:
        df = sorted(attempts, key=lambda x: (x.shape[1], x.shape[0]), reverse=True)[0]
    else:
        rows = []
        for line in text.splitlines():
            parts = re.split(r"\t|,|\s{2,}", line.strip())
            if len(parts) >= 2:
                rows.append(parts)
        if not rows:
            return pd.DataFrame(columns=["statement", "account", "period", "amount", "raw_value", "source", "period_sort"])
        max_len = max(len(r) for r in rows)
        rows = [r + [""] * (max_len - len(r)) for r in rows]
        df = pd.DataFrame(rows[1:], columns=rows[0])

    return wide_to_long(df, statement_name=statement_name, multiplier=multiplier, source="붙여넣기")


def read_uploaded_file(uploaded_file, multiplier=1):
    if uploaded_file is None:
        return pd.DataFrame(columns=["statement", "account", "period", "amount", "raw_value", "source", "period_sort"]), {}

    name = uploaded_file.name.lower()
    tables = {}
    long_parts = []

    try:
        if name.endswith(".xlsx") or name.endswith(".xls"):
            excel = pd.ExcelFile(uploaded_file)
            for sheet in excel.sheet_names:
                df = pd.read_excel(excel, sheet_name=sheet)
                tables[sheet] = df
                long_parts.append(wide_to_long(df, statement_name=guess_statement_name(sheet), multiplier=multiplier, source=f"업로드:{sheet}"))
        else:
            df = pd.read_csv(uploaded_file, sep=None, engine="python")
            tables[uploaded_file.name] = df
            long_parts.append(wide_to_long(df, statement_name="업로드 재무표", multiplier=multiplier, source="업로드"))
    except Exception:
        # 사용자 파일명이나 내부 예외 등 민감한 정보는 화면에 그대로 출력하지 않습니다.
        st.error("파일을 읽지 못했습니다. 형식과 인코딩을 확인해 주세요.")
        return pd.DataFrame(columns=["statement", "account", "period", "amount", "raw_value", "source", "period_sort"]), {}

    if long_parts:
        return pd.concat(long_parts, ignore_index=True), tables
    return pd.DataFrame(columns=["statement", "account", "period", "amount", "raw_value", "source", "period_sort"]), tables


def dart_rows_to_long(rows):
    if not rows:
        return pd.DataFrame(columns=["statement", "account", "period", "amount", "raw_value", "source", "period_sort"])

    out = []
    for r in rows:
        statement = STATEMENT_NAME_MAP.get(r.get("sj_div", ""), r.get("sj_nm", "DART 재무표"))
        account = r.get("account_nm", "")

        period_fields = [
            ("당기", "thstrm_amount"),
            ("당기누적", "thstrm_add_amount"),
            ("전기", "frmtrm_amount"),
            ("전기누적", "frmtrm_add_amount"),
            ("전전기", "bfefrmtrm_amount"),
        ]

        for period, field in period_fields:
            raw = r.get(field)
            amount = parse_amount(raw, multiplier=1)
            if pd.isna(amount):
                continue
            out.append({
                "statement": statement,
                "account": account,
                "period": period,
                "amount": amount,
                "raw_value": raw,
                "source": "OpenDART",
                "period_sort": infer_period_sort(period),
                "rcept_no": r.get("rcept_no", ""),
                "currency": r.get("currency", "KRW"),
            })

    return pd.DataFrame(out)


@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def fetch_corp_codes(api_key):
    url = "https://opendart.fss.or.kr/api/corpCode.xml"
    try:
        res = requests.get(url, params={"crtfc_key": api_key}, timeout=20)
        res.raise_for_status()
    except requests.RequestException:
        # requests 예외에는 crtfc_key가 담긴 전체 URL이 포함될 수 있습니다.
        raise ConnectionError("OpenDART 기업목록 통신 오류") from None

    zf = zipfile.ZipFile(io.BytesIO(res.content))
    xml_name = zf.namelist()[0]
    xml_bytes = zf.read(xml_name)
    root = ET.fromstring(xml_bytes)

    rows = []
    for item in root.findall("list"):
        rows.append({
            "corp_code": item.findtext("corp_code", default=""),
            "corp_name": item.findtext("corp_name", default=""),
            "corp_eng_name": item.findtext("corp_eng_name", default=""),
            "stock_code": item.findtext("stock_code", default=""),
            "modify_date": item.findtext("modify_date", default=""),
        })
    return pd.DataFrame(rows)


def search_corp(corp_df, query):
    if corp_df is None or corp_df.empty or not query:
        return pd.DataFrame()

    q_original = str(query).strip()
    q = normalize_key(q_original)
    alias = resolve_company_alias(q_original)

    df = corp_df.copy()
    df["corp_key"] = df["corp_name"].map(normalize_key)
    df["eng_key"] = df["corp_eng_name"].map(normalize_key)
    df["stock_code_str"] = df["stock_code"].astype(str).str.strip()
    df["is_listed"] = df["stock_code_str"].str.len() == 6
    df["score"] = 0

    # 1순위: 별칭에서 종목코드가 확인되면 종목코드 정확 매칭
    if alias and alias.get("stock_code"):
        stock = str(alias["stock_code"]).strip()
        df.loc[df["stock_code_str"] == stock, "score"] += 1000

        canonical = normalize_key(alias.get("canonical_name", ""))
        if canonical:
            df.loc[df["corp_key"].str.contains(canonical, na=False), "score"] += 200

        for a in alias.get("aliases", []):
            ak = normalize_key(a)
            if ak:
                df.loc[df["corp_key"].str.contains(ak, na=False) | df["eng_key"].str.contains(ak, na=False), "score"] += 60

    # 2순위: 사용자가 입력한 원문 자체로 폭넓게 검색
    if q:
        df.loc[df["corp_key"] == q, "score"] += 500
        df.loc[df["corp_key"].str.contains(q, na=False), "score"] += 160
        df.loc[df["eng_key"].str.contains(q, na=False), "score"] += 130
        df.loc[df["stock_code_str"].str.contains(q_original, na=False), "score"] += 300

        # 띄어쓰기/영문 표기 차이에 대비한 부분일치
        for token in re.split(r"\s+", q_original):
            tk = normalize_key(token)
            if len(tk) >= 2:
                df.loc[df["corp_key"].str.contains(tk, na=False) | df["eng_key"].str.contains(tk, na=False), "score"] += 20

    result = df[df["score"] > 0].copy()

    if result.empty and q:
        # 마지막 보정: 너무 엄격해서 못 찾는 경우 일부 글자 포함 검색
        result = df[
            df["corp_key"].str.contains(q[: max(2, min(4, len(q)))], na=False)
            | df["eng_key"].str.contains(q[: max(2, min(4, len(q)))], na=False)
        ].copy()
        result["score"] = 10

    result = result.sort_values(["score", "is_listed", "corp_name"], ascending=[False, False, True])
    return result.head(20)


def fetch_dart_financials(api_key, corp_code, year, report_code, fs_div):
    url = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
    params = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bsns_year": str(year),
        "reprt_code": report_code,
        "fs_div": fs_div,
    }
    try:
        res = requests.get(url, params=params, timeout=25)
        res.raise_for_status()
        data = res.json()
    except (requests.RequestException, ValueError):
        # 원본 예외의 URL과 쿼리스트링은 인증키를 포함할 수 있어 폐기합니다.
        raise ConnectionError("OpenDART 재무제표 통신 오류") from None
    if data.get("status") != "000":
        # 원문 오류 메시지에 요청 정보가 포함되더라도 화면에 전달하지 않습니다.
        raise LookupError("OpenDART 재무제표 조회 결과가 없습니다.")
    return data.get("list", [])


def build_metrics(long_df: pd.DataFrame, stock_price=None, shares=None):
    if long_df.empty:
        return {}, [], [], pd.DataFrame()

    df = long_df.copy()
    if "period_sort" not in df.columns:
        df["period_sort"] = df["period"].map(infer_period_sort)

    periods = (
        df[["period", "period_sort"]]
        .drop_duplicates()
        .sort_values("period_sort", ascending=False)["period"]
        .astype(str)
        .tolist()
    )
    latest = periods[0] if periods else None
    previous = periods[1] if len(periods) > 1 else None

    def val(metric, period=latest):
        return find_account_value(df, metric, period)

    m = {}
    for metric in ACCOUNT_ALIASES:
        m[metric] = val(metric)

    prev = {}
    if previous:
        for metric in ACCOUNT_ALIASES:
            prev[metric] = val(metric, previous)

    m["revenue_growth"] = growth_rate(m.get("revenue"), prev.get("revenue", np.nan))
    m["op_income_growth"] = growth_rate(m.get("operating_income"), prev.get("operating_income", np.nan))
    m["net_income_growth"] = growth_rate(m.get("net_income"), prev.get("net_income", np.nan))
    m["op_margin"] = safe_div(m.get("operating_income"), m.get("revenue"))
    m["net_margin"] = safe_div(m.get("net_income"), m.get("revenue"))
    m["gross_margin"] = safe_div(m.get("gross_profit"), m.get("revenue"))
    m["debt_ratio"] = safe_div(m.get("total_liabilities"), m.get("total_equity"))
    m["equity_ratio"] = safe_div(m.get("total_equity"), m.get("total_assets"))
    m["current_ratio"] = safe_div(m.get("current_assets"), m.get("current_liabilities"))
    m["roe"] = safe_div(m.get("net_income"), m.get("total_equity"))
    m["roa"] = safe_div(m.get("net_income"), m.get("total_assets"))
    m["ocf_to_net_income"] = safe_div(m.get("operating_cf"), m.get("net_income"))

    capex = m.get("capex")
    if pd.isna(capex):
        m["fcf"] = np.nan
    else:
        m["fcf"] = m.get("operating_cf", np.nan) - abs(capex)

    m["inventory_growth"] = growth_rate(m.get("inventory"), prev.get("inventory", np.nan))
    m["ar_growth"] = growth_rate(m.get("accounts_receivable"), prev.get("accounts_receivable", np.nan))
    m["borrowings_growth"] = growth_rate(m.get("borrowings"), prev.get("borrowings", np.nan))

    if shares and shares > 0:
        m["eps_calc"] = m.get("net_income") / shares if not pd.isna(m.get("net_income")) else np.nan
        m["bps_calc"] = m.get("total_equity") / shares if not pd.isna(m.get("total_equity")) else np.nan
    else:
        m["eps_calc"] = m.get("eps", np.nan)
        m["bps_calc"] = m.get("bps", np.nan)

    if stock_price and stock_price > 0:
        m["per_calc"] = safe_div(stock_price, m.get("eps_calc"))
        m["pbr_calc"] = safe_div(stock_price, m.get("bps_calc"))
    else:
        m["per_calc"] = np.nan
        m["pbr_calc"] = np.nan

    strengths, warnings = generate_signal_lists(m)
    metric_table = build_metric_table(m, latest, previous)
    m["latest_period"] = latest
    m["previous_period"] = previous
    return m, strengths, warnings, metric_table


def build_metric_table(m, latest, previous):
    rows = [
        ("매출액", fmt_amount(m.get("revenue")), "회사가 벌어들인 전체 수익 규모"),
        ("매출 증가율", fmt_pct(m.get("revenue_growth")), f"{previous} 대비 {latest} 매출 변화"),
        ("영업이익", fmt_amount(m.get("operating_income")), "본업에서 남긴 이익"),
        ("영업이익률", fmt_pct(m.get("op_margin")), "매출에서 본업 이익으로 남는 비율"),
        ("당기순이익", fmt_amount(m.get("net_income")), "비용·세금 등을 반영한 최종 이익"),
        ("순이익률", fmt_pct(m.get("net_margin")), "매출에서 최종 이익으로 남는 비율"),
        ("부채비율", fmt_pct(m.get("debt_ratio")), "자본 대비 부채 규모"),
        ("유동비율", fmt_pct(m.get("current_ratio")), "단기부채를 단기자산으로 감당할 여력"),
        ("ROE", fmt_pct(m.get("roe")), "자본을 활용해 이익을 내는 효율"),
        ("영업현금흐름", fmt_amount(m.get("operating_cf")), "본업에서 실제로 들어온 현금"),
        ("잉여현금흐름", fmt_amount(m.get("fcf")), "영업현금흐름에서 설비투자 부담을 뺀 현금"),
        ("재고자산 증가율", fmt_pct(m.get("inventory_growth")), "재고가 전기 대비 얼마나 늘었는지"),
        ("매출채권 증가율", fmt_pct(m.get("ar_growth")), "아직 회수하지 못한 매출채권 변화"),
        ("EPS", f"{m.get('eps_calc'):,.0f}원" if not pd.isna(m.get("eps_calc")) else "확인 필요", "주식 1주당 순이익"),
        ("PER", f"{m.get('per_calc'):,.1f}배" if not pd.isna(m.get("per_calc")) else "주가/주식수 입력 시 계산", "주가가 EPS의 몇 배인지"),
        ("PBR", f"{m.get('pbr_calc'):,.1f}배" if not pd.isna(m.get("pbr_calc")) else "주가/주식수 입력 시 계산", "주가가 BPS의 몇 배인지"),
    ]
    return pd.DataFrame(rows, columns=["항목", "값", "쉬운 설명"])


def generate_signal_lists(m):
    strengths = []
    warnings = []

    if not pd.isna(m.get("revenue_growth")):
        if m["revenue_growth"] > 0.1:
            strengths.append("매출이 뚜렷하게 증가해 외형 성장 흐름이 있습니다.")
        elif m["revenue_growth"] > 0:
            strengths.append("매출이 전기 대비 증가했습니다.")
        elif m["revenue_growth"] < -0.05:
            warnings.append("매출이 감소해 수요 둔화나 사업 축소 가능성을 확인해야 합니다.")

    if not pd.isna(m.get("op_margin")):
        if m["op_margin"] > 0.1:
            strengths.append("영업이익률이 양호해 본업에서 돈을 남기는 힘이 있습니다.")
        elif m["op_margin"] > 0:
            strengths.append("영업이익이 흑자입니다.")
        else:
            warnings.append("영업손실이 발생했을 가능성이 있어 본업 수익성을 확인해야 합니다.")

    if not pd.isna(m.get("net_income")):
        if m["net_income"] > 0:
            strengths.append("최종 순이익이 흑자입니다.")
        else:
            warnings.append("최종 순손실이 발생해 비용·금융손익·세금 영향을 확인해야 합니다.")

    if not pd.isna(m.get("operating_cf")):
        if m["operating_cf"] > 0:
            strengths.append("영업활동현금흐름이 플러스라 본업에서 현금이 유입되고 있습니다.")
        else:
            warnings.append("영업활동현금흐름이 마이너스라 장부상 이익과 실제 현금 유입을 구분해 봐야 합니다.")

    if not pd.isna(m.get("ocf_to_net_income")) and not pd.isna(m.get("net_income")) and m.get("net_income") > 0:
        if m["ocf_to_net_income"] >= 1:
            strengths.append("영업현금흐름이 순이익 이상으로 나와 이익의 질이 양호해 보입니다.")
        elif m["ocf_to_net_income"] < 0.6:
            warnings.append("순이익 대비 영업현금흐름이 약해 이익의 질을 추가 확인해야 합니다.")

    if not pd.isna(m.get("debt_ratio")):
        if m["debt_ratio"] < 1.0:
            strengths.append("부채비율이 낮은 편이라 재무 안정성이 비교적 좋아 보입니다.")
        elif m["debt_ratio"] > 2.0:
            warnings.append("부채비율이 높은 편이라 차입금 만기와 이자비용을 확인해야 합니다.")

    if not pd.isna(m.get("current_ratio")):
        if m["current_ratio"] >= 1.2:
            strengths.append("유동비율이 100%를 넘어 단기 지급 여력이 있습니다.")
        elif m["current_ratio"] < 1:
            warnings.append("유동비율이 100% 미만이라 단기부채 대응 여력을 점검해야 합니다.")

    if not pd.isna(m.get("inventory_growth")) and not pd.isna(m.get("revenue_growth")):
        if m["inventory_growth"] > m["revenue_growth"] + 0.15:
            warnings.append("재고 증가율이 매출 증가율보다 높아 재고 부담 가능성을 확인해야 합니다.")

    if not pd.isna(m.get("ar_growth")) and not pd.isna(m.get("revenue_growth")):
        if m["ar_growth"] > m["revenue_growth"] + 0.15:
            warnings.append("매출채권 증가율이 매출 증가율보다 높아 현금 회수 속도를 확인해야 합니다.")

    if not pd.isna(m.get("fcf")):
        if m["fcf"] > 0:
            strengths.append("설비투자 이후에도 잉여현금흐름이 플러스입니다.")
        else:
            warnings.append("잉여현금흐름이 마이너스라 투자 부담이나 현금 소진을 확인해야 합니다.")

    return strengths, warnings


def analyze_footnotes(text: str):
    text = text or ""
    rules = [
        ("소송·분쟁", ["소송", "분쟁", "중재", "계류"], "소송이나 분쟁은 결과에 따라 비용이 발생할 수 있어 규모와 진행 상황 확인이 필요합니다."),
        ("우발부채·보증", ["우발부채", "지급보증", "보증채무", "담보제공"], "재무제표 숫자에 바로 드러나지 않는 잠재 부담이 있을 수 있습니다."),
        ("특수관계자 거래", ["특수관계자", "관계기업", "종속기업", "최대주주"], "특수관계자 거래는 거래 조건이 일반 거래와 다른지 확인할 필요가 있습니다."),
        ("손상차손", ["손상차손", "손상", "impairment"], "자산 가치가 낮아졌다는 의미일 수 있어 일회성인지 반복되는지 확인해야 합니다."),
        ("재고 평가손실", ["재고자산평가손실", "재고 평가손실", "재고자산 평가"], "재고 가치가 낮아졌다면 판매 부진이나 가격 하락 가능성을 볼 수 있습니다."),
        ("대손충당금", ["대손충당금", "대손상각", "대손"], "매출채권 회수 위험이 커졌을 가능성이 있습니다."),
        ("계속기업 불확실성", ["계속기업", "존속능력", "going concern"], "회사의 지속 가능성에 대한 중요한 경고 문구일 수 있습니다."),
        ("감사의견 특이사항", ["한정의견", "부적정", "의견거절", "강조사항", "핵심감사사항"], "감사보고서의 특이사항은 반드시 원문 확인이 필요합니다."),
        ("차입금·금리 위험", ["차입금", "이자율", "금리위험", "만기", "유동성위험"], "차입금 구조와 금리 상승 부담을 확인해야 합니다."),
        ("파생상품·환율 위험", ["파생상품", "환위험", "외환위험", "환율", "통화선도"], "환율이나 파생상품 손익이 실적 변동성을 키울 수 있습니다."),
        ("회계정책 변경", ["회계정책 변경", "회계추정", "재작성", "정정"], "비교 가능성이 낮아질 수 있어 전기 수치와 변경 사유를 확인해야 합니다."),
    ]

    findings = []
    norm = normalize_key(text)
    for title, keywords, explanation in rules:
        matched = [k for k in keywords if normalize_key(k) in norm]
        if matched:
            findings.append({
                "특이사항": title,
                "발견 키워드": ", ".join(matched),
                "쉬운 해석": explanation,
                "중요도": "높음" if title in ["계속기업 불확실성", "감사의견 특이사항", "우발부채·보증"] else "중간",
            })
    return pd.DataFrame(findings)


def calculate_health_score(m, warnings, footnote_findings):
    score = 50

    if not pd.isna(m.get("revenue_growth")):
        score += 10 if m["revenue_growth"] > 0.1 else 5 if m["revenue_growth"] > 0 else -10
    if not pd.isna(m.get("op_margin")):
        score += 10 if m["op_margin"] > 0.08 else 5 if m["op_margin"] > 0 else -15
    if not pd.isna(m.get("net_income")):
        score += 6 if m["net_income"] > 0 else -12
    if not pd.isna(m.get("operating_cf")):
        score += 12 if m["operating_cf"] > 0 else -15
    if not pd.isna(m.get("ocf_to_net_income")) and not pd.isna(m.get("net_income")) and m["net_income"] > 0:
        score += 8 if m["ocf_to_net_income"] >= 1 else -8 if m["ocf_to_net_income"] < 0.6 else 0
    if not pd.isna(m.get("debt_ratio")):
        score += 8 if m["debt_ratio"] < 1.0 else -10 if m["debt_ratio"] > 2.0 else 0
    if not pd.isna(m.get("current_ratio")):
        score += 6 if m["current_ratio"] >= 1.2 else -8 if m["current_ratio"] < 1.0 else 0
    if not pd.isna(m.get("fcf")):
        score += 5 if m["fcf"] > 0 else -7

    score -= min(len(warnings) * 2, 16)
    if not footnote_findings.empty:
        high_count = (footnote_findings["중요도"] == "높음").sum()
        mid_count = (footnote_findings["중요도"] == "중간").sum()
        score -= high_count * 7 + mid_count * 4

    score = max(0, min(100, round(score)))

    if score >= 80:
        grade = "매우 양호"
        grade_desc = "핵심 재무지표가 전반적으로 안정적입니다."
        badge_class = "badge-good"
    elif score >= 65:
        grade = "양호"
        grade_desc = "큰 위험 신호는 적지만 일부 항목은 추가 확인이 필요합니다."
        badge_class = "badge-good"
    elif score >= 50:
        grade = "보통 / 추가 확인"
        grade_desc = "좋은 점과 주의할 점이 함께 있어 원문 확인이 필요합니다."
        badge_class = "badge-warn"
    elif score >= 35:
        grade = "주의 필요"
        grade_desc = "현금흐름, 부채, 수익성 중 일부에서 주의 신호가 보입니다."
        badge_class = "badge-warn"
    else:
        grade = "위험 신호 많음"
        grade_desc = "여러 지표에서 위험 신호가 보여 전문가 검토와 원문 확인이 필요합니다."
        badge_class = "badge-risk"

    return score, grade, grade_desc, badge_class


def make_plain_summary(m, strengths, warnings, footnote_findings, grade):
    lines = []
    if not pd.isna(m.get("revenue")):
        lines.append(f"최근 기간 기준 매출은 {fmt_amount(m.get('revenue'))}입니다.")
    if not pd.isna(m.get("operating_income")):
        lines.append(f"본업에서 남긴 영업이익은 {fmt_amount(m.get('operating_income'))}이며, 영업이익률은 {fmt_pct(m.get('op_margin'))}입니다.")
    if not pd.isna(m.get("net_income")):
        lines.append(f"최종 순이익은 {fmt_amount(m.get('net_income'))}입니다.")
    if not pd.isna(m.get("operating_cf")):
        lines.append(f"영업활동현금흐름은 {fmt_amount(m.get('operating_cf'))}입니다.")

    if not lines:
        lines.append("입력된 표에서 핵심 계정이 충분히 인식되지 않았습니다. 항목명을 매출액, 영업이익, 자산총계처럼 표준적으로 입력하면 분석 정확도가 올라갑니다.")

    if grade == "자료 부족":
        conclusion = "필수 재무자료가 부족해 종합적인 재무 상태를 평가할 수 없습니다."
    elif grade in ["매우 양호", "양호"]:
        conclusion = "전반적으로 재무 상태는 비교적 안정적으로 보입니다."
    elif grade == "보통 / 추가 확인":
        conclusion = "일부 지표는 긍정적이지만, 숫자만으로 단정하기보다 원문과 주석 확인이 필요합니다."
    elif grade == "주의 필요":
        conclusion = "주의해야 할 신호가 있으므로 현금흐름, 부채, 주석을 함께 확인해야 합니다."
    else:
        conclusion = "여러 위험 신호가 나타나므로 단순 요약만으로 판단하지 말고 원문 공시와 전문가 검토가 필요합니다."

    note_line = ""
    if not footnote_findings.empty:
        note_line = f" 주석/감사의견에서 {len(footnote_findings)}개의 특이 키워드가 발견되었습니다."

    return " ".join(lines) + " " + conclusion + note_line


def make_questions(m, warnings, footnote_findings):
    questions = []
    if any("현금" in w for w in warnings) or (not pd.isna(m.get("ocf_to_net_income")) and m.get("ocf_to_net_income") < 0.6):
        questions.append("순이익은 났는데 실제 현금은 충분히 들어오고 있는가?")
    if any("재고" in w for w in warnings):
        questions.append("재고가 늘어난 이유가 수요 둔화 때문인가, 미래 판매를 위한 선제적 확보인가?")
    if any("매출채권" in w for w in warnings):
        questions.append("매출채권 회수 기간이 길어지고 있지는 않은가?")
    if not pd.isna(m.get("debt_ratio")) and m.get("debt_ratio") > 2:
        questions.append("차입금 만기와 이자비용을 회사가 감당할 수 있는가?")
    if not footnote_findings.empty:
        questions.append("주석과 감사보고서 원문에서 특이사항의 금액 규모와 실제 영향을 확인했는가?")
    if not questions:
        questions = [
            "이번 실적 개선이 반복 가능한 본업 성장 때문인가?",
            "경쟁사나 업종 평균과 비교했을 때 수익성과 부채 수준은 어떤가?",
            "최근 공시 정정이나 감사보고서 특이사항은 없는가?",
        ]
    return questions


def render_signal_list(items, icon, empty_msg):
    if items:
        for item in items:
            st.markdown(
                f"""
                <div class="signal-item">
                    <div class="signal-icon">{icon}</div>
                    <div class="signal-text">{item}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.info(empty_msg)


def render_statement_tables(long_df):
    if long_df.empty:
        st.info("표시할 재무제표 데이터가 없습니다.")
        return

    for statement in long_df["statement"].dropna().unique():
        part = long_df[long_df["statement"] == statement].copy()
        if part.empty:
            continue
        pivot = part.pivot_table(index="account", columns="period", values="amount", aggfunc="first").reset_index()
        period_order = part[["period", "period_sort"]].drop_duplicates().sort_values("period_sort", ascending=False)["period"].tolist()
        cols = ["account"] + [p for p in period_order if p in pivot.columns]
        pivot = pivot[cols]
        display = pivot.copy()
        for c in display.columns:
            if c != "account":
                display[c] = display[c].map(fmt_amount)

        st.markdown(f"#### {statement}")
        st.dataframe(display, use_container_width=True, hide_index=True)


# ============================================================
# Hero
# ============================================================

st.markdown(
    """
    <div class="app-hero">
        <div class="hero-pill">🩺 모바일 재무 건강검진 MVP</div>
        <div class="main-title">기업 재무제표를 쉽게 읽어주는 앱</div>
        <div class="sub-title">
            어려운 재무상태표·손익계산서·현금흐름표·주석을 일반인용 언어로 바꿔드립니다.
            좋은 점, 주의할 점, 특이사항, 최종 결론을 한 화면에서 확인하세요.
        </div>
        <div class="hero-mini-grid">
            <div class="mini-card"><div class="mini-icon">📋</div><div class="mini-title">표 붙여넣기</div><div class="mini-desc">DART·엑셀 표를 그대로 분석</div></div>
            <div class="mini-card"><div class="mini-icon">📊</div><div class="mini-title">재무표 보기</div><div class="mini-desc">원문 숫자를 표로 확인</div></div>
            <div class="mini-card"><div class="mini-icon">⚠️</div><div class="mini-title">특이사항 탐지</div><div class="mini-desc">주석·감사의견 위험 키워드</div></div>
            <div class="mini-card"><div class="mini-icon">✅</div><div class="mini-title">쉬운 결론</div><div class="mini-desc">건강 점수와 최종 요약</div></div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# Sidebar + input
# ============================================================

with st.sidebar:
    st.markdown("## 🧭 분석 메뉴")
    input_mode = st.radio(
        "입력 방식",
        ["샘플로 체험", "표 붙여넣기", "엑셀/CSV 업로드", "OpenDART 자동 조회"],
        index=0,
        help="처음에는 샘플로 체험해보고, 실제 분석은 표 붙여넣기 또는 업로드를 추천합니다.",
    )

    st.markdown("---")
    st.markdown("### ⚙️ 계산 설정")
    unit = st.selectbox("금액 단위", list(UNIT_MULTIPLIER.keys()), index=2, help="붙여넣기/업로드 자료의 단위입니다. OpenDART는 원 단위입니다.")
    multiplier = UNIT_MULTIPLIER[unit]

    st.markdown("### ➕ 선택 입력")
    stock_price = st.number_input("주가", min_value=0.0, value=0.0, step=100.0, help="PER/PBR 계산에만 사용됩니다.")
    shares = st.number_input("발행주식수", min_value=0.0, value=0.0, step=1000.0, help="EPS/BPS 계산에만 사용됩니다.")
    st.caption("주가와 주식수를 입력하지 않아도 재무 건강 분석은 가능합니다.")

    st.markdown("---")
    st.markdown("---")
    manual_company_name = st.text_input(
        "분석 기업명 표시(선택)",
        value="",
        placeholder="예: SK하이닉스, 삼성전자",
        help="표 붙여넣기/업로드/샘플 분석 결과 상단에 표시할 기업명입니다.",
    )
    st.caption("투자추천이 아닌 재무정보 이해 보조 앱입니다.")


long_df = pd.DataFrame(columns=["statement", "account", "period", "amount", "raw_value", "source", "period_sort"])
raw_tables = {}
footnote_text = ""
current_company_info = {
    "query": manual_company_name.strip() or ("샘플 기업" if input_mode == "샘플로 체험" else "직접 입력 자료"),
    "canonical_name": manual_company_name.strip() or ("샘플 기업" if input_mode == "샘플로 체험" else "직접 입력 자료"),
}


if input_mode == "샘플로 체험":
    st.markdown('<div class="section-title">✨ 샘플 데이터로 먼저 체험하기</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="soft-card">
            <b>바로 결과 화면을 확인할 수 있는 체험 모드입니다.</b><br>
            실제 기업 분석은 표 붙여넣기, 엑셀/CSV 업로드, OpenDART 자동 조회를 사용하세요.
        </div>
        """,
        unsafe_allow_html=True,
    )
    parts = []
    for stmt in ["손익계산서", "재무상태표", "현금흐름표", "자본변동표"]:
        parts.append(parse_pasted_table(SAMPLE_TABLES[stmt], stmt, multiplier=1_000_000))
    long_df = pd.concat(parts, ignore_index=True)
    footnote_text = SAMPLE_TABLES["주석"]

elif input_mode == "표 붙여넣기":
    st.markdown('<div class="section-title">📋 재무제표 표 붙여넣기</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="soft-card">
            DART, 회사 IR 자료, 엑셀에서 표를 복사해 그대로 붙여넣으세요.
            처음에는 <b>손익계산서·재무상태표·현금흐름표</b>만 넣어도 분석할 수 있습니다.
        </div>
        """,
        unsafe_allow_html=True,
    )

    tabs = st.tabs(["손익계산서", "재무상태표", "현금흐름표", "자본변동표", "주석/감사의견"])
    pasted = {}
    with tabs[0]:
        pasted["손익계산서"] = st.text_area("손익계산서 표", height=220, placeholder=SAMPLE_TABLES["손익계산서"])
    with tabs[1]:
        pasted["재무상태표"] = st.text_area("재무상태표 표", height=240, placeholder=SAMPLE_TABLES["재무상태표"])
    with tabs[2]:
        pasted["현금흐름표"] = st.text_area("현금흐름표 표", height=220, placeholder=SAMPLE_TABLES["현금흐름표"])
    with tabs[3]:
        pasted["자본변동표"] = st.text_area("자본변동표 표", height=190, placeholder=SAMPLE_TABLES["자본변동표"])
    with tabs[4]:
        footnote_text = st.text_area("주석, 감사의견, 특이사항 텍스트", height=260, placeholder=SAMPLE_TABLES["주석"])

    # 입력값이 달라지면 이전에 분석한 표를 새 표의 결과로 보여주지 않습니다.
    paste_signature = (
        tuple((statement, pasted[statement]) for statement in pasted),
        multiplier,
    )
    if st.button("🔍 재무제표 분석 실행", type="primary"):
        st.session_state.pop("pasted_analysis", None)
        parts = []
        for stmt, text in pasted.items():
            if text.strip():
                parts.append(parse_pasted_table(text, stmt, multiplier=multiplier))
        parts = [part for part in parts if not part.empty]
        if parts:
            long_df = pd.concat(parts, ignore_index=True)
            st.session_state["pasted_analysis"] = {
                "signature": paste_signature,
                "data": long_df.copy(),
            }
        else:
            st.warning("인식할 수 있는 표가 없습니다. 계정명과 숫자 열을 확인해 주세요.")
    else:
        saved_paste = st.session_state.get("pasted_analysis")
        if saved_paste and saved_paste.get("signature") == paste_signature:
            long_df = saved_paste["data"].copy()
        elif saved_paste:
            st.session_state.pop("pasted_analysis", None)

elif input_mode == "엑셀/CSV 업로드":
    st.markdown('<div class="section-title">📁 엑셀/CSV 업로드</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="soft-card">
            엑셀은 여러 시트를 한 번에 읽습니다. 시트명에 손익/상태/현금/자본이 들어가면 자동으로 구분합니다.
        </div>
        """,
        unsafe_allow_html=True,
    )
    uploaded = st.file_uploader("재무제표 파일 업로드", type=["xlsx", "xls", "csv"])
    footnote_text = st.text_area("주석/감사의견 텍스트 붙여넣기(선택)", height=220, placeholder=SAMPLE_TABLES["주석"])
    if uploaded is not None:
        long_df, raw_tables = read_uploaded_file(uploaded, multiplier=multiplier)

elif input_mode == "OpenDART 자동 조회":
    st.markdown('<div class="section-title">🏛️ OpenDART 자동 조회</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="soft-card">
            기업명을 입력하면 OpenDART API로 재무제표를 불러옵니다.
            <b>OpenDART 자동 조회는 공식 API 키가 필요</b>합니다. 키가 없으면 이 화면의 자동 조회만 제한되고,
            샘플·표 붙여넣기·엑셀 업로드 분석은 그대로 사용할 수 있습니다.
        </div>
        """,
        unsafe_allow_html=True,
    )

    default_key = ""
    try:
        default_key = st.secrets.get("OPENDART_API_KEY", "")
    except Exception:
        default_key = ""

    # 키가 노출되었던 서비스의 안전한 기본값: 관리자가 명시적으로 재개할 때만 API를 호출합니다.
    try:
        opendart_enabled = st.secrets.get("OPENDART_ENABLED", False) is True
    except Exception:
        opendart_enabled = False
    with st.expander("🔐 OpenDART 조회 상태", expanded=not opendart_enabled):
        if not opendart_enabled:
            st.warning("현재 자동 조회는 보안점검을 위해 일시 중지했습니다. 샘플·붙여넣기·CSV 분석은 정상 이용할 수 있습니다.")
        elif default_key:
            st.success("OpenDART 자동 조회가 설정되어 있습니다.")
        else:
            st.info("OpenDART 인증키가 등록되지 않았습니다.")
        st.caption("인증키는 입력창이나 오류 메시지에 표시하지 않고 Streamlit Secrets에서만 관리합니다.")

    api_key = default_key if opendart_enabled else ""

    col1, col2 = st.columns([1.25, 1])
    with col1:
        corp_query = st.text_input("기업명 또는 종목코드", value="삼성전자", placeholder="예: SK하이닉스, sk hynix, 에스케이하이닉스, 000660")
        resolved_alias = resolve_company_alias(corp_query)
        if resolved_alias:
            st.caption(f"인식된 기업: {resolved_alias['canonical_name']} · 종목코드 {resolved_alias['stock_code']}")
        else:
            st.caption("회사명, 영문명, 종목코드로 검색할 수 있습니다.")
    with col2:
        year = st.number_input("사업연도", min_value=2015, max_value=datetime.now().year, value=max(2015, datetime.now().year - 1), step=1)

    col3, col4 = st.columns(2)
    with col3:
        report_name = st.selectbox("보고서", list(REPORT_CODES.keys()), index=0)
    with col4:
        fs_div_label = st.selectbox("재무제표 구분", ["연결재무제표(CFS)", "별도재무제표(OFS)"], index=0)

    footnote_text = st.text_area("주석/감사의견 텍스트 붙여넣기(선택)", height=170, placeholder="OpenDART 주석 자동 조회는 추후 확장 영역입니다. 지금은 중요한 주석 문구를 붙여넣으면 특이사항을 탐지합니다.")

    # 자동 조회 중지 시 이전에 조회한 결과도 화면에서 제거합니다.
    if not opendart_enabled:
        st.session_state.pop("dart_analysis", None)
    # 성공했던 검색과 현재 검색 조건이 정확히 같을 때만 결과를 복원합니다.
    # 이전 기업·이전 사업연도 결과가 새 조회에 섞이는 문제를 예방합니다.
    request_signature = dart_request_signature(corp_query, year, report_name, fs_div_label)
    saved_dart = matching_saved_analysis(st.session_state.get("dart_analysis"), request_signature)
    if saved_dart is None:
        st.session_state.pop("dart_analysis", None)

    if st.button("🏛️ OpenDART에서 조회하고 분석", type="primary", disabled=not opendart_enabled):
        # 새 조회가 시작되는 순간 과거 검색 결과를 삭제합니다.
        st.session_state.pop("dart_analysis", None)
        if not api_key:
            st.warning("OpenDART 자동 조회에는 API 키가 필요합니다. 표 붙여넣기/업로드 분석은 키 없이 사용할 수 있습니다.")
        elif not corp_query.strip():
            st.warning("조회할 기업명이나 종목코드를 입력해 주세요.")
        else:
            try:
                with st.spinner("기업 고유번호를 찾는 중입니다..."):
                    corp_df = fetch_corp_codes(api_key)
                    matches = search_corp(corp_df, corp_query)
                if matches.empty:
                    st.error("기업을 찾지 못했습니다. 회사명 또는 종목코드를 다시 입력해 주세요.")
                else:
                    selected = matches.iloc[0]
                    with st.spinner("OpenDART 재무제표를 불러오는 중입니다..."):
                        rows = fetch_dart_financials(
                            api_key=api_key,
                            corp_code=selected["corp_code"],
                            year=int(year),
                            report_code=REPORT_CODES[report_name],
                            fs_div="CFS" if fs_div_label.startswith("연결") else "OFS",
                        )
                        verified, reason = verify_dart_rows(rows, year)
                        if not verified:
                            if reason == "year_mismatch":
                                st.warning(f"{year}년과 다른 사업연도의 자료가 반환되어 분석을 중단했습니다.")
                            else:
                                st.warning(f"{year}년 {report_name}에 해당하는 재무자료가 없습니다.")
                        else:
                            candidate_df = dart_rows_to_long(rows)
                            if candidate_df.empty:
                                st.warning(f"{year}년 재무자료를 해석할 수 없습니다. 다른 보고서나 사업연도를 선택해 주세요.")
                            else:
                                company_info = {
                                    "query": corp_query,
                                    "corp_name": selected["corp_name"],
                                    "canonical_name": selected["corp_name"],
                                    "stock_code": selected["stock_code"] or "",
                                    "year": int(year),  # 성공한 요청의 사업연도만 결과에 표시
                                    "report": report_name,
                                    "fs_div": fs_div_label,
                                }
                                st.session_state["dart_analysis"] = {
                                    "signature": request_signature,
                                    "data": candidate_df.copy(),
                                    "company_info": company_info,
                                }
                                long_df = candidate_df
                                current_company_info = company_info
                                st.success(f"조회 기업: {selected['corp_name']} / 종목코드: {selected['stock_code'] or '비상장'}")
                                if "rcept_no" in long_df.columns and long_df["rcept_no"].notna().any():
                                    rcp_no = str(long_df["rcept_no"].dropna().iloc[0])
                                    if re.fullmatch(r"\d{14}", rcp_no):
                                        st.markdown(f"[DART 원문 공시 열기](https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcp_no})")
            except (requests.RequestException, ConnectionError, ValueError, LookupError):
                # 요청 URL에 인증키가 포함될 수 있으므로 원본 예외 메시지는 보여주지 않습니다.
                st.error("OpenDART 조회에 실패했습니다. 통신 상태·사업연도·보고서 종류를 확인해 주세요.")
            except Exception:
                st.error("OpenDART 조회에 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.")
    elif saved_dart is not None:
        long_df = saved_dart["data"].copy()
        current_company_info = saved_dart["company_info"]

# 다른 입력 방식이나 과거 버전의 캐시를 현재 조회 결과로 복원하지 않습니다.
for legacy_key in ("last_long_df", "last_footnote_text", "last_company_info", "current_company_info"):
    st.session_state.pop(legacy_key, None)


# ============================================================
# Output
# ============================================================

if long_df.empty:
    st.markdown('<div class="section-title">🚀 사용 방법</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="soft-card">
            <b>1.</b> 샘플로 체험으로 결과 화면을 먼저 확인합니다.<br>
            <b>2.</b> 실제 분석은 표 붙여넣기 또는 엑셀/CSV 업로드를 사용합니다.<br>
            <b>3.</b> OpenDART API 키를 연결하면 기업명만으로 재무제표를 바로 조회할 수 있습니다.<br>
            <b>4.</b> Streamlit Cloud에 배포하면 핸드폰 데이터나 다른 와이파이에서도 앱처럼 사용할 수 있습니다.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()


metrics, strengths, warnings, metric_table = build_metrics(
    long_df,
    stock_price=stock_price if stock_price > 0 else None,
    shares=shares if shares > 0 else None,
)
footnote_findings = analyze_footnotes(footnote_text)
missing_fields = missing_score_fields(metrics)
if missing_fields:
    score = None
    grade = "자료 부족"
    grade_desc = "손익·재무상태·현금흐름의 필수 항목이 갖춰져야 종합점수를 계산할 수 있습니다."
    badge_class = "badge-warn"
else:
    score, grade, grade_desc, badge_class = calculate_health_score(metrics, warnings, footnote_findings)
summary = make_plain_summary(metrics, strengths, warnings, footnote_findings, grade)
questions = make_questions(metrics, warnings, footnote_findings)

st.markdown('<div class="section-title">📌 분석 결과</div>', unsafe_allow_html=True)
if missing_fields:
    st.warning("종합 평가 보류: " + ", ".join(missing_fields) + " 자료가 부족합니다. 확인 가능한 지표만 아래에 표시합니다.")
else:
    st.caption("재무 건강점수는 자체 규칙에 따른 참고용 지표이며, 투자판단·신용등급·회계감사 결과를 의미하지 않습니다.")
if not footnote_findings.empty and (footnote_findings["중요도"] == "높음").any():
    st.warning("입력된 주석·감사의견에서 확인이 필요한 표현이 감지되었습니다. 건강점수가 높더라도 원문 문맥을 반드시 확인해 주세요.")
st.caption("주석·감사의견의 키워드 탐지는 사용자가 입력한 텍스트에만 적용되며, 공시 주석을 자동 수집하거나 감사의견을 판정하지 않습니다.")
st.markdown(
    f"""
    <div class="soft-card" style="margin-bottom:0.7rem;">
        <span class="badge badge-info">🏢 {escape(make_company_badge(current_company_info))}</span>
    </div>
    """,
    unsafe_allow_html=True,
)

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("종합 등급", grade)
with c2:
    st.metric("참고용 재무 건강점수", f"{score}/100" if score is not None else "평가 보류")
with c3:
    st.metric("좋은 신호", f"{len(strengths)}개")
with c4:
    st.metric("주의 신호", f"{len(warnings) + len(footnote_findings)}개")

st.markdown(
    f"""
    <div class="result-card">
        <span class="badge {badge_class}">🩺 {grade}</span>
        <span class="badge badge-info">🏢 {escape(make_company_badge(current_company_info))}</span>
        <span class="badge badge-info">📄 재무제표 규칙 기반 해석</span>
        {f'<div class="gauge-wrap"><div class="gauge-fill" style="width:{score}%;"></div></div>' if score is not None else '<div class="small-caption">종합점수는 필수 재무자료 확보 후 표시합니다.</div>'}
        <div style="height:0.82rem;"></div>
        <div class="summary-title">한 줄 결론</div>
        <div class="summary-text">{escape(summary)}</div>
        <div class="small-caption" style="margin-top:0.66rem;">{grade_desc}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

tabs = st.tabs(["🏠 쉬운 요약", "📊 핵심 지표", "📋 재무표 보기", "⚠️ 특이사항", "📝 주석/감사의견", "⚖️ 원문·고지"])

with tabs[0]:
    st.markdown('<div class="section-title">일반인용 쉬운 해석</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="soft-card">{escape(summary)}</div>', unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### ✅ 좋은 점")
        render_signal_list(strengths[:8], "✅", "입력된 자료에서 뚜렷한 긍정 신호를 충분히 찾지 못했습니다.")
    with col_b:
        st.markdown("#### ⚠️ 주의할 점")
        render_signal_list(warnings[:8], "⚠️", "핵심 지표 기준의 큰 주의 신호는 제한적입니다. 그래도 원문 공시와 주석은 확인하세요.")

    st.markdown("#### 🔎 추가로 확인하면 좋은 질문")
    for q in questions:
        st.markdown(
            f"""
            <div class="signal-item">
                <div class="signal-icon">🔎</div>
                <div class="signal-text">{q}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

with tabs[1]:
    st.markdown('<div class="section-title">핵심 지표</div>', unsafe_allow_html=True)
    st.dataframe(metric_table, use_container_width=True, hide_index=True)

    chart_metrics = []
    for metric_key, label in [("revenue", "매출액"), ("operating_income", "영업이익"), ("net_income", "순이익"), ("operating_cf", "영업현금흐름")]:
        for p in sorted(long_df["period"].astype(str).unique(), key=infer_period_sort):
            v = find_account_value(long_df, metric_key, p)
            if not pd.isna(v):
                chart_metrics.append({"기간": p, "항목": label, "금액": v})

    if chart_metrics:
        chart_df = pd.DataFrame(chart_metrics)
        pivot_chart = chart_df.pivot_table(index="기간", columns="항목", values="금액", aggfunc="first")
        st.markdown("#### 📈 주요 항목 추세")
        st.line_chart(pivot_chart)

with tabs[2]:
    st.markdown('<div class="section-title">재무제표 원문 표 보기</div>', unsafe_allow_html=True)
    st.caption("앱이 인식한 표를 그대로 보여줍니다. 분석 결과가 이상하면 이 표에서 항목명과 금액 단위를 확인하세요.")
    render_statement_tables(long_df)

with tabs[3]:
    st.markdown('<div class="section-title">숫자 기반 특이사항</div>', unsafe_allow_html=True)
    render_signal_list(warnings, "⚠️", "핵심 숫자 기준으로는 큰 특이사항이 많지 않습니다.")
    st.markdown(
        """
        <div class="legal-box">
        <b>자동 판단 기준</b><br>
        매출은 늘었는데 재고나 매출채권이 더 빠르게 늘면 주의 신호로 봅니다.<br>
        순이익이 흑자인데 영업현금흐름이 약하면 이익의 질을 확인합니다.<br>
        부채비율이 높거나 유동비율이 낮으면 단기 안정성을 확인합니다.<br>
        잉여현금흐름이 계속 마이너스면 투자 부담 또는 현금 소진 가능성을 확인합니다.
        </div>
        """,
        unsafe_allow_html=True,
    )

with tabs[4]:
    st.markdown('<div class="section-title">주석/감사의견 특이사항</div>', unsafe_allow_html=True)
    if footnote_text.strip():
        with st.expander("입력한 주석/감사의견 보기"):
            st.write(footnote_text)
    else:
        st.info("주석이나 감사의견 텍스트를 넣으면 소송, 우발부채, 특수관계자 거래, 계속기업 불확실성 등을 탐지합니다.")

    if not footnote_findings.empty:
        st.dataframe(footnote_findings, use_container_width=True, hide_index=True)
    else:
        st.success("입력된 주석 텍스트에서 주요 위험 키워드는 발견되지 않았습니다.")

with tabs[5]:
    st.markdown('<div class="section-title">원문·출처·법률 고지</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="legal-box">
        <b>이 앱의 목적</b><br>
        이 서비스는 재무제표와 공시자료를 일반 사용자가 쉽게 이해하도록 돕는 정보 제공형 도구입니다.<br><br>

        <b>제공하지 않는 것</b><br>
        이 서비스는 특정 주식의 매수·매도·보유를 권유하지 않으며, 투자자문·회계감사·세무자문·법률자문을 제공하지 않습니다.<br><br>

        <b>사용자 확인 사항</b><br>
        자동 분석 결과는 입력 데이터의 품질, 항목명, 단위, 공시 정정 여부에 따라 달라질 수 있습니다.
        중요한 의사결정 전에는 원문 공시자료, 감사보고서, 전문가 검토를 함께 확인해야 합니다.<br><br>

        <b>저작권·데이터 처리 원칙</b><br>
        업로드 파일은 앱 실행 세션에서 분석에만 사용하며, 이 코드에서는 서버 저장 기능을 두지 않았습니다.
        유료 리포트, 뉴스 전문, 제3자 저작물을 무단 복제해 표시하지 않는 것을 원칙으로 합니다.
        공시자료를 사용할 때는 출처와 공시일자를 표시하고 원문 링크를 제공합니다.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if "source" in long_df.columns:
        sources = ", ".join(sorted(set(long_df["source"].dropna().astype(str))))
        st.caption(f"현재 분석 데이터 출처: {sources}")

st.markdown('<div class="footer-space"></div>', unsafe_allow_html=True)
st.caption("© Financial Health Reader MVP — 일반인용 재무제표 해석 보조 도구")
