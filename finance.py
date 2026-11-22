"""재무데이터 정리·검증·설명. 재무 판단을 대체하지 않는 보수적인 점검 모듈."""
from __future__ import annotations

import io
import re
from math import isfinite
from typing import Iterable

import pandas as pd

COLUMNS = ["statement", "account", "account_id", "period", "amount", "source", "rcept_no", "unit"]
UNITS = {"원": 1, "천원": 1000, "백만원": 1000000, "억원": 100000000}
STATEMENTS = {
    "BS": "재무상태표",
    "IS": "손익계산서",
    "CIS": "손익계산서",
    "CF": "현금흐름표",
    "SCE": "자본변동표",
}
METRICS = {
    "revenue": ("손익계산서", ["매출액", "영업수익", "매출", "수익(매출액)", "Revenue"], ["ifrs-full_Revenue", "ifrs_Revenue", "ifrs-full_RevenueFromContractsWithCustomers"]),
    "op_income": ("손익계산서", ["영업이익", "영업이익(손실)", "영업손실", "OperatingProfitLoss"], ["dart_OperatingIncomeLoss"]),
    "net_income": ("손익계산서", ["당기순이익", "당기순이익(손실)", "당기순손실", "연결당기순이익", "ProfitLoss"], ["ifrs-full_ProfitLoss", "ifrs_ProfitLoss"]),
    "gross_profit": ("손익계산서", ["매출총이익", "매출총손익", "GrossProfit"], ["ifrs-full_GrossProfit"]),
    "assets": ("재무상태표", ["자산총계", "총자산", "Assets"], ["ifrs-full_Assets", "ifrs_Assets"]),
    "liabilities": ("재무상태표", ["부채총계", "총부채", "Liabilities"], ["ifrs-full_Liabilities", "ifrs_Liabilities"]),
    "equity": ("재무상태표", ["자본총계", "총자본", "Equity"], ["ifrs-full_Equity", "ifrs_Equity"]),
    "current_assets": ("재무상태표", ["유동자산", "CurrentAssets"], ["ifrs-full_CurrentAssets"]),
    "current_liabilities": ("재무상태표", ["유동부채", "CurrentLiabilities"], ["ifrs-full_CurrentLiabilities"]),
    "cash": ("재무상태표", ["현금및현금성자산", "현금 및 현금성자산", "CashAndCashEquivalents"], ["ifrs-full_CashAndCashEquivalents"]),
    "receivables": ("재무상태표", ["매출채권", "매출채권및기타채권", "매출채권 및 기타채권", "TradeAndOtherCurrentReceivables"], ["ifrs-full_TradeAndOtherCurrentReceivables", "ifrs-full_TradeReceivables"]),
    "inventory": ("재무상태표", ["재고자산", "Inventories"], ["ifrs-full_Inventories"]),
    "op_cf": ("현금흐름표", ["영업활동현금흐름", "영업활동으로인한현금흐름", "영업활동으로 인한 현금흐름", "CashFlowsFromUsedInOperatingActivities"], ["ifrs-full_CashFlowsFromUsedInOperatingActivities"]),
    "inv_cf": ("현금흐름표", ["투자활동현금흐름", "투자활동으로인한현금흐름", "CashFlowsFromUsedInInvestingActivities"], ["ifrs-full_CashFlowsFromUsedInInvestingActivities"]),
    "fin_cf": ("현금흐름표", ["재무활동현금흐름", "재무활동으로인한현금흐름", "CashFlowsFromUsedInFinancingActivities"], ["ifrs-full_CashFlowsFromUsedInFinancingActivities"]),
    "capex": ("현금흐름표", ["유형자산의취득", "유형자산의 취득", "PurchaseOfPropertyPlantAndEquipment"], ["ifrs-full_PurchaseOfPropertyPlantAndEquipment"]),
    "eps": ("손익계산서", ["기본주당이익", "기본주당순이익", "주당순이익", "BasicEarningsLossPerShare"], ["ifrs-full_BasicEarningsLossPerShare"]),
}
METRIC_LABELS = {
    "revenue": "매출액", "op_income": "영업이익", "net_income": "당기순이익",
    "gross_profit": "매출총이익", "assets": "자산총계", "liabilities": "부채총계",
    "equity": "자본총계", "current_assets": "유동자산", "current_liabilities": "유동부채",
    "cash": "현금및현금성자산", "receivables": "매출채권(또는 기타채권 포함)",
    "inventory": "재고자산", "op_cf": "영업현금흐름", "inv_cf": "투자현금흐름",
    "fin_cf": "재무현금흐름", "capex": "유형자산 취득", "eps": "기본주당이익",
}


def empty_data():
    return pd.DataFrame(columns=COLUMNS)


def normal(text):
    return re.sub(r"[\s\(\)\[\]/,·_\-]", "", str(text or "")).casefold()


def amount(value):
    if value is None:
        return None
    t = str(value).strip()
    if not t or t in {"-", "—", "nan", "NaN", "None", "N/A"}:
        return None
    is_neg = t.startswith("(") and t.endswith(")") or t.startswith(("△", "▲"))
    t = t.strip("()").lstrip("△▲").replace(",", "")
    t = re.sub(r"[^0-9.\-]", "", t)
    try:
        x = float(t)
    except ValueError:
        return None
    return -abs(x) if is_neg else x


def is_num(v):
    try:
        return v is not None and isfinite(float(v))
    except (ValueError, TypeError):
        return False


def div(a, b):
    return (float(a) / float(b)) if is_num(a) and is_num(b) and b != 0 else None


def growth(a, b):
    return (a - b) / abs(b) if is_num(a) and is_num(b) and b != 0 else None


def fmt_won(x):
    if not is_num(x):
        return "자료 없음"
    x = float(x)
    if abs(x) >= 1e12:
        return f"{x / 1e12:,.2f}조 원"
    if abs(x) >= 1e8:
        return f"{x / 1e8:,.2f}억 원"
    if abs(x) >= 1e4:
        return f"{x / 1e4:,.1f}만 원"
    return f"{x:,.0f}원"


def fmt_pct(x):
    return f"{x * 100:.1f}%" if is_num(x) else "자료 없음"


def from_dart(rows: list[dict], year: int, report: str):
    """보고서 종류에 따라 분기 흐름은 누적 금액을 우선 사용합니다.
    반기/분기 자료의 회전일수·연간 성장률은 자동 산출하지 않습니다.
    """
    records = []
    annual = report == "사업보고서"
    for row in rows:
        currency = str(row.get("currency", "KRW") or "KRW").strip().upper()
        if currency not in ("KRW", "원"):
            raise ValueError("OpenDART 재무 금액의 통화가 원화가 아닙니다. 통화와 단위를 확인하세요.")
        kind = str(row.get("sj_div", ""))
        stmt = STATEMENTS.get(kind)
        if not stmt:
            continue
        if kind == "SCE" and row.get("account_detail") not in (None, "", "-", "연결재무제표 [member]"):
            # 자본변동표 상세구성원은 합산 중복을 막기 위해 제외.
            continue
        account_name = str(row.get("account_nm", "")).strip()
        if not account_name:
            continue
        if kind in ("IS", "CIS", "CF") and not annual:
            pairs = [
                (str(year), row.get("thstrm_add_amount") or row.get("thstrm_amount")),
                (str(year - 1), row.get("frmtrm_add_amount") or row.get("frmtrm_amount")),
            ]
        else:
            pairs = [
                (str(year), row.get("thstrm_amount")),
                (str(year - 1), row.get("frmtrm_amount")),
            ]
            if annual:
                pairs.append((str(year - 2), row.get("bfefrmtrm_amount")))
        for period, raw in pairs:
            num = amount(raw)
            if num is not None:
                records.append({
                    "statement": stmt,
                    "account": account_name,
                    "account_id": str(row.get("account_id", "")).strip(),
                    "period": period,
                    "amount": num,
                    "source": "OpenDART",
                    "rcept_no": str(row.get("rcept_no", "")).strip(),
                    "unit": "원",
                })
    if not records:
        return empty_data()
    df = pd.DataFrame(records, columns=COLUMNS)
    # 같은 IS/CIS 계정이 반복될 때 첫 번째만 남기고 숫자를 합산하지 않습니다.
    return df.drop_duplicates(subset=["statement", "account", "account_id", "period"], keep="first").reset_index(drop=True)


def from_wide(df: pd.DataFrame, statement: str, multiplier: int, source: str):
    if df is None or df.empty or len(df.columns) < 2:
        return empty_data()
    cols = list(df.columns)
    account_col = next((c for c in cols if normal(c) in ("항목", "계정", "계정과목", "과목", "account", "item")), cols[0])
    records = []
    for _, line in df.iterrows():
        acct = str(line[account_col]).strip()
        if not acct or acct.casefold() == "nan":
            continue
        for col in cols:
            if col == account_col:
                continue
            num = amount(line[col])
            if num is None:
                continue
            records.append({
                "statement": statement,
                "account": acct, "account_id": "",
                "period": str(col).strip(),
                "amount": num * multiplier,
                "source": source, "rcept_no": "", "unit": "원",
            })
    return pd.DataFrame(records, columns=COLUMNS) if records else empty_data()


def parse_paste(text: str, statement: str, multiplier: int):
    if not str(text).strip():
        return empty_data()
    for sep in ("\t", ",", ";", r"\s{2,}"):
        try:
            data = pd.read_csv(io.StringIO(text), sep=sep, engine="python")
            if len(data.columns) >= 2:
                return from_wide(data, statement, multiplier, "붙여넣기")
        except (ValueError, pd.errors.ParserError):
            pass
    raise ValueError("표의 첫 줄에 항목명과 연도가 있는지 확인해 주세요.")


def guess_statement(sheet_name: str):
    name = normal(sheet_name)
    for mark, stmt in (
        ("현금흐름", "현금흐름표"), ("cashflow", "현금흐름표"),
        ("손익", "손익계산서"), ("income", "손익계산서"),
        ("재무상태", "재무상태표"), ("balance", "재무상태표"),
        ("자본변동", "자본변동표"), ("equity", "자본변동표"),
    ):
        if mark in name:
            return stmt
    return None


def parse_uploaded(uploaded, multiplier: int, csv_statement: str):
    name = uploaded.name.lower()
    if name.endswith((".xlsx", ".xls")):
        frames = pd.read_excel(uploaded, sheet_name=None)
        parsed = [
            from_wide(frame, stmt, multiplier, f"파일:{sheet}")
            for sheet, frame in frames.items()
            if (stmt := guess_statement(sheet)) is not None
        ]
        if not parsed:
            raise ValueError("엑셀 시트 이름에 '손익', '재무상태', '현금흐름', '자본변동'을 넣어주세요.")
    elif name.endswith(".csv"):
        payload = uploaded.getvalue()
        try:
            data = pd.read_csv(io.BytesIO(payload), encoding="utf-8-sig", sep=None, engine="python")
        except UnicodeDecodeError:
            data = pd.read_csv(io.BytesIO(payload), encoding="cp949", sep=None, engine="python")
        parsed = [from_wide(data, csv_statement, multiplier, f"파일:{uploaded.name}")]
    else:
        raise ValueError("CSV, XLSX 또는 XLS만 지원합니다.")
    good = [part for part in parsed if not part.empty]
    return pd.concat(good, ignore_index=True) if good else empty_data()


def account_value(data: pd.DataFrame, key: str, period: str):
    if data.empty or key not in METRICS:
        return None, None
    stmt, names, ids = METRICS[key]
    table = data[(data.statement == stmt) & (data.period.astype(str) == str(period))].copy()
    if table.empty:
        return None, None
    normalized_ids = {normal(x) for x in ids}
    normalized_names = {normal(x) for x in names}
    # 1. 공시 표준계정 ID, 2. 이름의 정확 일치. 부분 일치는 사용하지 않습니다.
    # 주석·합계·부분계정 오인식을 피하기 위한 보수적인 정책입니다.
    for mode in ("id", "name"):
        for _, r in table.iterrows():
            if mode == "id" and normal(r["account_id"]) in normalized_ids:
                return float(r["amount"]), r
            if mode == "name" and normal(r["account"]) in normalized_names:
                return float(r["amount"]), r
    return None, None


def compute_metrics(data: pd.DataFrame, price: float | None = None, shares: float | None = None,
                    annual=True):
    if data.empty:
        return {}, [], []
    periods = sorted(set(data.period.astype(str)), reverse=True)
    cur = periods[0]
    prev = periods[1] if len(periods) > 1 else None
    m = {"period": cur, "previous_period": prev, "annual": annual}
    evidence = []
    for key in METRICS:
        val, record = account_value(data, key, cur)
        m[key] = val
        if record is not None:
            evidence.append({"지표": METRIC_LABELS[key], "계정과목": record["account"],
                             "기간": cur, "자료원": record["source"], "금액(원)": val})
    for key in ("revenue", "op_income", "net_income", "receivables", "inventory"):
        past, _ = account_value(data, key, prev) if prev else (None, None)
        m[key + "_prev"] = past
        m[key + "_growth"] = growth(m.get(key), past) if annual else None
    m["op_margin"] = div(m.get("op_income"), m.get("revenue"))
    m["net_margin"] = div(m.get("net_income"), m.get("revenue"))
    m["debt_ratio"] = div(m.get("liabilities"), m.get("equity"))
    m["current_ratio"] = div(m.get("current_assets"), m.get("current_liabilities"))
    m["ocf_to_earnings"] = div(m.get("op_cf"), m.get("net_income")) if annual else None
    # ROE / ROA는 기간 평균 자본/자산이 없으면 계산하지 않습니다.
    past_equity, _ = account_value(data, "equity", prev) if prev else (None, None)
    past_assets, _ = account_value(data, "assets", prev) if prev else (None, None)
    m["roe"] = div(m.get("net_income"), (m["equity"] + past_equity) / 2) if annual and is_num(m.get("equity")) and is_num(past_equity) else None
    m["roa"] = div(m.get("net_income"), (m["assets"] + past_assets) / 2) if annual and is_num(m.get("assets")) and is_num(past_assets) else None
    m["fcf"] = (m["op_cf"] - abs(m["capex"])) if is_num(m.get("op_cf")) and is_num(m.get("capex")) else None
    # PER: 주당이익이 양수일 때만, PBR: 발행주식수·자기자본이 유효할 때만.
    # EPS는 가중평균주식수와 지배기업귀속 이익이 필요하므로 공시 계정이 있을 때만 표시합니다.
    eps = m.get("eps")
    m["eps_calculated"] = eps
    # 단순 PBR 참고값: 연결 자본총계에 비지배지분이 있을 수 있어 원문과 대조해야 합니다.
    m["bps"] = m["equity"] / shares if is_num(shares) and shares > 0 and is_num(m.get("equity")) else None
    m["per"] = price / eps if is_num(price) and price > 0 and is_num(eps) and eps > 0 else None
    m["pbr"] = price / m["bps"] if is_num(price) and price > 0 and is_num(m["bps"]) and m["bps"] > 0 else None
    quality = []
    if all(is_num(m.get(k)) for k in ("assets", "liabilities", "equity")):
        diff = m["assets"] - m["liabilities"] - m["equity"]
        tolerance = max(10000, abs(m["assets"]) * 0.005)
        if abs(diff) > tolerance:
            quality.append(f"자산총계와 부채·자본총계가 약 {fmt_won(abs(diff))} 차이 납니다. 원본/계정 매칭을 확인하세요.")
    for key in ("revenue", "op_income", "net_income", "assets", "liabilities", "equity", "op_cf"):
        if not is_num(m.get(key)):
            quality.append(f"{METRIC_LABELS[key]} 값을 식별하지 못했습니다. 해당 지표의 판단은 보류합니다.")
    if not annual:
        quality.append("반기·분기 금액은 누적 기준이며 연간 성장률·ROE·ROA를 계산하지 않습니다.")
    return m, evidence, quality


def signals(m: dict):
    pos, caution, questions = [], [], []
    if is_num(m.get("op_income")):
        if m["op_income"] >= 0:
            pos.append("영업이익이 흑자입니다. 영업현금흐름도 함께 확인하세요.")
        else:
            caution.append("영업손실이 발생했습니다. 비용 구조와 일회성 요인을 확인하세요.")
    if is_num(m.get("op_cf")):
        if m["op_cf"] >= 0:
            pos.append("영업활동에서 순현금이 유입되었습니다.")
        else:
            caution.append("영업활동 현금흐름이 마이너스입니다. 운전자본 변화를 살펴보세요.")
    if is_num(m.get("net_income")) and m["net_income"] > 0 and is_num(m.get("op_cf")) and m["op_cf"] < 0:
        caution.append("순이익 흑자와 영업현금흐름 유출이 함께 나타납니다.")
        questions.append("매출채권, 매입채무, 선수금 등 운전자본이 어떻게 변했나요?")
    if is_num(m.get("debt_ratio")) and m["debt_ratio"] > 2:
        caution.append("부채비율이 200%를 넘습니다. 차입금 구성과 만기를 살펴보세요.")
    if is_num(m.get("current_ratio")) and m["current_ratio"] < 1:
        caution.append("유동비율이 100% 미만입니다. 현금과 단기 지급일정을 함께 확인하세요.")
    if is_num(m.get("receivables_growth")) and is_num(m.get("revenue_growth")) and m["receivables_growth"] > m["revenue_growth"] + .15:
        caution.append("매출채권 증가율이 매출 증가율보다 높습니다. 계약상 정산 시점과 회수 상태를 확인하세요.")
    if is_num(m.get("op_cf")) and is_num(m.get("fcf")) and m["fcf"] < 0:
        caution.append("유형자산 투자 이후 잉여현금흐름이 마이너스입니다. 투자 목적과 조달 계획을 확인하세요.")
    if not questions:
        questions = [
            "회계상 이익과 실제 입금 시점 사이에 차이가 있나요?",
            "지표 변화가 사업구조·회계정책 변경의 영향인가요?",
            "감사보고서 주석과 원문에 추가 위험 요인이 있나요?",
        ]
    return pos, caution, questions


def note_matches(text: str):
    if not str(text).strip():
        return []
    groups = {
        "우발부채·담보": ("우발부채", "지급보증", "담보제공"),
        "관계사 거래": ("특수관계자", "종속기업", "관계기업"),
        "감사·계속기업": ("계속기업", "한정의견", "의견거절", "부적정의견"),
        "손상": ("손상차손", "손실충당금", "대손충당금"),
        "분쟁": ("계류중인 소송", "소송", "중재"),
    }
    found = []
    for label, terms in groups.items():
        matches = [x for x in terms if x in text]
        if matches:
            found.append({"분류": label, "발견한 표현": ", ".join(matches),
                          "판단": "키워드 탐지 결과일 뿐 위험 발생을 확정하지 않습니다. 원문 문맥 확인 필요"})
    return found


def health_screening_score(m: dict, quality: list):
    """임의적 참고 지수: 분석 자료 충분할 때만 표시. 투자/신용평가용이 아님."""
    essentials = ("revenue", "op_income", "net_income", "assets", "liabilities", "equity", "op_cf")
    if any(not is_num(m.get(k)) for k in essentials):
        return None
    if any("차이" in item for item in quality):
        return None
    score = 50
    score += 15 if m["op_income"] > 0 else -15
    score += 15 if m["op_cf"] > 0 else -15
    dr = m.get("debt_ratio")
    if is_num(dr):
        score += 10 if dr < 1 else -10 if dr > 2 else 0
    cr = m.get("current_ratio")
    if is_num(cr):
        score += 10 if cr > 1.2 else -10 if cr < 1 else 0
    return max(0, min(100, score))


def metrics_table(m):
    ordered = [
        ("매출액", "revenue", "won"), ("영업이익", "op_income", "won"),
        ("당기순이익", "net_income", "won"), ("영업현금흐름", "op_cf", "won"),
        ("기말 현금", "cash", "won"), ("자산총계", "assets", "won"),
        ("부채총계", "liabilities", "won"), ("자본총계", "equity", "won"),
        ("매출 증가율", "revenue_growth", "pct"),
        ("영업이익률", "op_margin", "pct"), ("순이익률", "net_margin", "pct"),
        ("부채비율", "debt_ratio", "pct"), ("유동비율", "current_ratio", "pct"),
        ("ROE(평균자본)", "roe", "pct"), ("ROA(평균자산)", "roa", "pct"),
        ("잉여현금흐름(참고)", "fcf", "won"),
        ("매출채권 증가율", "receivables_growth", "pct"),
        ("기본주당이익(EPS)", "eps_calculated", "won"),
        ("PER(공시 EPS 기준)", "per", "ratio"), ("단순 PBR(참고)", "pbr", "ratio"),
    ]
    result = []
    for label, key, fmt in ordered:
        value = m.get(key)
        display = fmt_won(value) if fmt == "won" else fmt_pct(value) if fmt == "pct" else f"{value:.2f}배" if is_num(value) else "자료 없음"
        result.append({"지표": label, "계산값": display, "원값": value})
    return pd.DataFrame(result)
