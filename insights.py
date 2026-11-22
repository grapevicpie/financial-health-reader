"""근거를 동반한 재무지표 진단 및 사용자가 직접 설정하는 자금 일정 분석.

계산 결과와 해석/가설을 분리합니다.
실제 법인의 회수일·차입금 만기·주석은 자동으로 추정하지 않습니다.
"""
from __future__ import annotations

from datetime import date, timedelta
import re

import pandas as pd

from finance import account_value, div, fmt_pct, fmt_won, growth, is_num

SECTION_KEYS = {
    "손익": ("revenue", "gross_profit", "op_income", "net_income"),
    "재무상태": ("assets", "liabilities", "equity", "current_assets", "current_liabilities", "cash", "receivables"),
    "현금흐름": ("op_cf", "inv_cf", "fin_cf", "capex"),
}


def yearly_matrix(data: pd.DataFrame) -> pd.DataFrame:
    """대상 자료의 같은 정의를 사용해 시계열을 만들되 조회한 데이터 밖으로 외삽하지 않습니다."""
    if data.empty:
        return pd.DataFrame()
    periods = sorted(data.period.astype(str).unique())
    rows = []
    for year in periods:
        rec = {"기간": year}
        for keys in SECTION_KEYS.values():
            for key in keys:
                rec[key] = account_value(data, key, year)[0]
        rec["op_margin"] = div(rec.get("op_income"), rec.get("revenue"))
        rec["net_margin"] = div(rec.get("net_income"), rec.get("revenue"))
        rec["current_ratio"] = div(rec.get("current_assets"), rec.get("current_liabilities"))
        rec["working_capital"] = (
            rec["current_assets"] - rec["current_liabilities"]
            if is_num(rec.get("current_assets")) and is_num(rec.get("current_liabilities"))
            else None
        )
        rec["cash_to_cl"] = div(rec.get("cash"), rec.get("current_liabilities"))
        rec["ocf_minus_income"] = (
            rec["op_cf"] - rec["net_income"]
            if is_num(rec.get("op_cf")) and is_num(rec.get("net_income"))
            else None
        )
        rows.append(rec)
    return pd.DataFrame(rows)


def integrity_checks(data: pd.DataFrame, annual: bool = True) -> list[dict]:
    """의심 신호와 정확한 불일치를 구분하는 데이터 점검."""
    alerts = []
    if data.empty:
        return [{"level": "error", "title": "자료가 없습니다", "detail": "재무제표 표 또는 파일이 필요합니다."}]
    recent = sorted(data.period.astype(str).unique())[-1]
    counts = data.groupby(["statement", "account_id", "account", "period"], dropna=False)["amount"].agg(["count", "nunique"])
    inconsistent = counts[(counts["count"] > 1) & (counts["nunique"] > 1)]
    if not inconsistent.empty:
        alerts.append({
            "level": "error", "title": "동일 계정·기간에 서로 다른 금액",
            "detail": f"{len(inconsistent)}개 조합에서 금액이 다릅니다. 어느 값이 정답인지 원문에서 확인할 때까지 해석을 보류하세요.",
        })
    for key, label in [
        ("assets", "자산총계"), ("liabilities", "부채총계"), ("equity", "자본총계"),
        ("revenue", "매출액"), ("op_income", "영업이익"), ("net_income", "순이익"),
        ("op_cf", "영업현금흐름")
    ]:
        v, _ = account_value(data, key, recent)
        if not is_num(v):
            alerts.append({"level": "missing", "title": f"{label} 식별 불가", "detail": "원문에서 계정명과 범위를 직접 확인하세요. 누락값을 0으로 취급하지 않습니다."})
    vals = [account_value(data, k, recent)[0] for k in ("assets", "liabilities", "equity")]
    if all(is_num(v) for v in vals):
        assets, liabilities, equity = vals
        difference = assets - (liabilities + equity)
        tolerance = max(1000.0, abs(assets)*.001)
        if abs(difference) > tolerance:
            alerts.append({"level": "error", "title": "재무상태표 합계 불일치",
                           "detail": f"자산과 부채+자본의 차이는 {fmt_won(abs(difference))}입니다. 누락 또는 잘못된 계정 매칭을 확인하세요."})
        else:
            alerts.append({"level": "ok", "title": "재무상태표 기본 합계 확인",
                           "detail": "자산과 부채+자본의 차이가 설정한 허용범위 내입니다. 감사 의견이나 전체 데이터 정확성을 보증하는 뜻은 아닙니다."})
    if not annual:
        alerts.append({"level": "info", "title": "중간보고서 누적 기준",
                       "detail": "손익 및 현금흐름은 해당 중간기간 누적 수치입니다. 연간 회전율이나 연간 성장률로 표시하지 않습니다."})
    if not alerts:
        alerts.append({"level": "ok", "title": "기초 검사 완료",
                       "detail": "기본 항목에서 명백한 문제를 발견하지 못했습니다. 원문과 주석을 별도로 검토하세요."})
    return alerts


def interpret(m: dict, history: pd.DataFrame, annual: bool) -> list[dict]:
    """검증 가능한 계산과 확인을 권하는 질문. 문제 발생을 단정하지 않습니다."""
    out = []
    def add(kind, title, evidence, question):
        out.append({"kind":kind, "title":title, "evidence":evidence, "question":question})
    ni, cfo = m.get("net_income"), m.get("op_cf")
    if is_num(ni) and is_num(cfo):
        gap = cfo - ni
        add(
            "watch" if ni > 0 and cfo < 0 else "check",
            "이익과 영업현금흐름을 따로 확인",
            f"순이익 {fmt_won(ni)}, 영업현금흐름 {fmt_won(cfo)} (현금흐름-순이익: {fmt_won(gap)}).",
            "매출채권·매입채무·선수금 등 운전자본과 비현금 손익의 조정 내역은 무엇인가요?"
        )
    op = m.get("op_income")
    rev = m.get("revenue")
    if annual and all(is_num(v) for v in (op,rev,m.get("op_income_prev"),m.get("revenue_prev"))):
        old_margin = div(m["op_income_prev"],m["revenue_prev"])
        new_margin = div(op,rev)
        if is_num(old_margin) and is_num(new_margin):
            delta = (new_margin-old_margin)*100
            add("watch" if delta < -1 else "check", "매출과 영업이익률의 방향 비교",
                f"매출 증감 {fmt_pct(m.get('revenue_growth'))}, 영업이익률 {fmt_pct(old_margin)} → {fmt_pct(new_margin)} ({delta:+.1f}%p).",
                "프로젝트별 매출총이익과 인건비·외주비·판매관리비의 변화가 있었나요?")
    ar = m.get("receivables")
    ar_prev = m.get("receivables_prev")
    if annual and all(is_num(v) for v in (ar,ar_prev,rev,m.get("revenue_prev"))) and rev > 0:
        g = growth(ar,ar_prev)
        rg = m.get("revenue_growth")
        add("watch" if is_num(g) and is_num(rg) and g > rg + .15 else "check",
            "매출채권 계정과 매출 증가의 차이",
            f"채권 계정 증감 {fmt_pct(g)}, 매출 증감 {fmt_pct(rg)}. 채권 계정에 기타채권이 포함될 수 있습니다.",
            "정산조건·기말 집중매출·회수 예정일·손실충당금을 원문 주석에서 확인했나요?")
    ca, cl = m.get("current_assets"), m.get("current_liabilities")
    if all(is_num(v) for v in (ca, cl)):
        wc=ca-cl
        add("watch" if cl > 0 and ca/cl < 1 else "check", "단기 지급 여력의 구성",
            f"유동자산-유동부채 {fmt_won(wc)}; 유동비율 {fmt_pct(div(ca,cl))}.",
            "유동자산 중 실제 현금화 시점과 유동부채 중 만기 차입금의 일정은 어떻게 다른가요?")
    if is_num(cfo) and is_num(m.get("capex")):
        proxy = cfo - abs(m["capex"])
        add("watch" if proxy < 0 else "check", "투자지출 이후 현금흐름",
            f"영업현금흐름-유형자산 취득액(간이): {fmt_won(proxy)}.",
            "무형자산 투자·사업결합·리스·기타 투자 현금흐름이 제외되어 있습니다. 주석을 확인했나요?")
    if not out:
        add("missing", "분석 자료 부족", "현재 핵심 계정을 충분히 식별하지 못했습니다.",
            "원본 재무상태표·손익계산서·현금흐름표 자료가 모두 들어왔나요?")
    return out


def notes_in_context(text: str, window: int = 55, limit: int = 3) -> list[dict]:
    """키워드 존재만으로 위험 결론을 내리지 않고 주변 문맥을 보여줍니다."""
    if not str(text).strip():
        return []
    groups = {
        "차입금·유동성": ("단기차입금", "장기차입금", "유동성위험", "만기분석", "차환"),
        "현금회수": ("대손충당금", "손실충당금", "회수가능성", "매출채권"),
        "특수관계자": ("특수관계자", "단기대여금", "자금대여", "지급보증"),
        "우발부채·담보": ("우발부채", "담보", "계류중인 소송"),
        "감사의견": ("한정의견", "부적정의견", "의견거절", "계속기업"),
        "회계정책": ("수익인식", "총액인식", "순액인식", "회계정책의 변경"),
    }
    clean = re.sub(r"\s+", " ", str(text))
    found = []
    for label, keywords in groups.items():
        snippets = []
        for keyword in keywords:
            for match in re.finditer(re.escape(keyword), clean):
                start = max(0, match.start() - window)
                end = min(len(clean), match.end() + window)
                snippets.append("…" + clean[start:end] + "…")
                if len(snippets) >= limit:
                    break
            if len(snippets) >= limit:
                break
        if snippets:
            found.append({
                "분류": label, "인용 주변 문맥": "\n".join(snippets),
                "추가 확인": "키워드가 등장했다는 사실만으로 위험이 발생했다고 판단하지 않습니다."
            })
    return found


def schedule_preview(frame: pd.DataFrame, initial_cash: float, date_from: date | None = None):
    """수기 입력 자금 일정(원 단위)에서 기말 잔액을 계산합니다."""
    if not is_num(initial_cash) or initial_cash < 0:
        raise ValueError("기초 현금은 0원 이상이어야 합니다.")
    if frame is None or frame.empty:
        return pd.DataFrame(), float(initial_cash)
    required = {"일자", "구분", "금액(원)"}
    if not required.issubset(frame.columns):
        raise ValueError("입력 표에 일자, 구분, 금액(원) 열이 필요합니다.")
    frame=frame.copy()
    frame["일자"] = pd.to_datetime(frame["일자"], errors="coerce")
    frame["금액(원)"] = pd.to_numeric(frame["금액(원)"], errors="coerce")
    frame = frame.dropna(how="all")
    frame = frame[frame["일자"].notna() | frame["금액(원)"].notna() | frame["구분"].notna()]
    if frame.empty:
        return pd.DataFrame(), float(initial_cash)
    if frame["일자"].isna().any() or frame["금액(원)"].isna().any():
        raise ValueError("입출금 예정일과 금액은 모두 채워야 합니다.")
    if not frame["구분"].isin(["입금", "출금"]).all():
        raise ValueError("구분은 입금 또는 출금 중에서 선택하세요.")
    if (frame["금액(원)"] < 0).any():
        raise ValueError("금액은 양수로 입력하고 방향은 입금/출금으로 선택하세요.")
    frame["현금변동"] = frame["금액(원)"].where(frame["구분"] == "입금", -frame["금액(원)"])
    frame = frame.sort_values("일자", kind="stable")
    frame["예상 잔액(원)"] = float(initial_cash) + frame["현금변동"].cumsum()
    return frame, float(min(float(initial_cash), frame["예상 잔액(원)"].min()))


def schedule_example(today: date | None = None) -> pd.DataFrame:
    base = today or date.today()
    return pd.DataFrame({
        "일자": [base + timedelta(days=2), base + timedelta(days=4), base + timedelta(days=7)],
        "구분": ["출금", "입금", "출금"],
        "내용": ["가상 예시: 외주비", "가상 예시: 매출대금", "가상 예시: 운영비"],
        "금액(원)": [7_000_000, 12_000_000, 5_000_000],
    })
