"""기업 재무 건강검진 v3 — 근거 중심 대시보드. 원자료와 계산 가정을 명시합니다."""
from __future__ import annotations

import hashlib
import io
import re
from datetime import date, datetime

import pandas as pd
import streamlit as st

from dart_api import DartClient, DartError, REPORT_CODES, resolve_direct, search_company_list
from finance import (
    UNITS, empty_data, from_dart, parse_paste, parse_uploaded,
    account_value, compute_metrics, metrics_table, fmt_won, fmt_pct,
    is_num
)
from insights import (
    yearly_matrix, integrity_checks, interpret, notes_in_context,
    schedule_preview, schedule_example
)

st.set_page_config(page_title="기업 재무 건강검진", page_icon="📊", layout="wide")
st.markdown("""
<style>
.block-container {max-width:1260px; padding-top:1.5rem; padding-bottom:3.5rem}
.hero-v3 {
 background: linear-gradient(115deg,#12253d 0%,#174b57 58%,#167d82 100%);
 padding:1.8rem 2rem; border-radius:20px; margin-bottom:1.15rem;
 color:white; box-shadow:0 9px 25px rgba(11,47,65,.12);
}
.hero-v3 .eyebrow {font-size:.78rem;letter-spacing:.08em;opacity:.83;margin-bottom:.55rem}
.hero-v3 h1 {font-size:2rem;letter-spacing:-.03em;line-height:1.25;color:white;margin:0}
.hero-v3 p {font-size:.95rem;color:#dbf4f1;margin:.65rem 0 0;line-height:1.6}
.soft-note {border-left:3px solid #20a5a2;padding:.6rem 1rem;background:#eef8f7;
 border-radius:0 10px 10px 0;color:#184f50;font-size:.87rem;line-height:1.5;margin: .75rem 0}
.micro-tag {background:#e7f4f3;border-radius:22px;padding:.18rem .55rem;font-weight:600;
 color:#14706c;font-size:.76rem}
@media(max-width:800px) {.hero-v3{padding:1.3rem 1rem;border-radius:14px}
 .hero-v3 h1{font-size:1.55rem}.block-container{padding-left:.65rem;padding-right:.65rem}}
</style>
""", unsafe_allow_html=True)
st.markdown("""
<div class="hero-v3"><div class="eyebrow">FINANCIAL HEALTH READER · V3</div>
<h1>기업 재무 건강검진</h1>
<p>숫자만 보여주지 않고, 근거와 다음에 확인할 질문까지 연결합니다.<br>
공시 재무제표 · 현금흐름 · 운전자본 · 검증 · 자금 일정</p></div>
""", unsafe_allow_html=True)

def read_setting(name, fallback=""):
    try:
        return st.secrets.get(name, fallback)
    except Exception:
        return fallback


api_key = str(read_setting("OPENDART_API_KEY", "")).strip()
flag = read_setting("OPENDART_ENABLED", False)
api_enabled = (flag is True or str(flag).strip().lower() == "true") and bool(api_key)


@st.cache_data(ttl=86400, show_spinner=False)
def cached_corp_list(key):
    return DartClient(key).fetch_corp_codes()


@st.cache_data(ttl=900, show_spinner=False)
def cached_financials(key, code, year, report, fs_div):
    return DartClient(key).fetch_financials(code, year, report, fs_div)


def signed(*parts):
    return hashlib.sha256(repr(parts).encode("utf-8")).hexdigest()


with st.sidebar:
    st.markdown("### 자료 불러오기")
    mode = st.radio(
        "자료 입력 방식",
        ["샘플 체험", "OpenDART 자동 조회", "표 붙여넣기", "엑셀·CSV 업로드"],
    )
    st.divider()
    unit, period_type = "백만원", "연간"
    if mode in ("표 붙여넣기", "엑셀·CSV 업로드"):
        unit = st.selectbox("자료의 금액 단위", list(UNITS), index=2)
        period_type = st.selectbox("입력 자료의 기간", ["연간", "반기/분기 누적"])
    st.caption("OpenDART 금액은 원 단위입니다. 직접 입력 시 반드시 표의 금액 단위를 확인하세요.")
    st.divider()
    st.caption("회계정보 학습·점검용 도구이며 감사·투자자문을 대신하지 않습니다.")

data = empty_data()
company = ""
notes = ""
annual = period_type == "연간"
receipt = ""

# ─── 모드 전환시 타 모드의 자료가 나타나지 않도록 표시 조건을 분리 ───
if mode == "샘플 체험":
    st.subheader("샘플로 체험하기")
    st.info("아래 금액은 가상 예시입니다. 실제 기업 실적으로 해석하지 마세요.")
    sample = {
        "손익계산서": "항목\t2023\t2024\t2025\n매출액\t9500\t11000\t11600\n영업이익\t960\t1050\t920\n당기순이익\t780\t850\t690",
        "재무상태표": "항목\t2023\t2024\t2025\n자산총계\t18000\t19800\t21000\n부채총계\t9000\t10000\t10500\n자본총계\t9000\t9800\t10500\n유동자산\t8200\t9000\t9100\n유동부채\t5300\t5500\t6000\n현금및현금성자산\t1700\t1800\t1400\n매출채권\t2200\t2450\t3000",
        "현금흐름표": "항목\t2023\t2024\t2025\n영업활동현금흐름\t900\t800\t400\n투자활동현금흐름\t-600\t-1100\t-850\n재무활동현금흐름\t-200\t300\t50",
    }
    sample_parts = [parse_paste(text, stmt, 1000000) for stmt, text in sample.items()]
    data = pd.concat(sample_parts, ignore_index=True)
    company = "가상 샘플 기업"
    notes = "지급보증 관련 주석이 있다면 약정 규모와 기간을 확인해야 합니다."
    annual = True

elif mode == "OpenDART 자동 조회":
    st.subheader("🏛️ OpenDART 재무제표 자동 조회")
    if not api_key:
        st.warning("API 인증키가 등록되지 않았습니다. Streamlit App settings → Secrets의 OPENDART_API_KEY를 확인하세요.")
    elif not api_enabled:
        st.warning("OpenDART 자동조회가 비활성화되어 있습니다. Secrets에 OPENDART_ENABLED = true가 필요합니다.")
    else:
        st.success("인증키가 등록되고 조회가 활성화됐습니다. 실제 API 응답 성공 여부는 별도 확인이 필요합니다.")

    with st.expander("🔧 OpenDART 연결 진단"):
        st.caption("인증키를 출력하지 않습니다. 회사개황(삼성전자)의 단일 API를 호출해 통신·인증 오류를 구분합니다.")
        if st.button("API 연결 확인", disabled=not api_enabled):
            try:
                with st.spinner("OpenDART 서버 응답 확인 중..."):
                    info = DartClient(api_key).company_info("00126380")
                st.success(f"API 연결 성공 · 상태 000 · 회사명 {info.get('corp_name','확인됨')}")
            except DartError as err:
                st.error(str(err))
                st.info("연결 시간 초과라면 인증키 오류라고 단정할 수 없습니다. Streamlit 서버와 OpenDART 간 통신을 먼저 확인하세요.")

    col_a, col_b = st.columns([2, 1])
    with col_a:
        query = st.text_input("기업명 · 6자리 종목코드 · 8자리 공시 고유번호",
                              value="삼성전자", help="공시 고유번호를 입력하면 기업목록 전체 다운로드를 생략합니다.")
    with col_b:
        year = st.number_input("사업연도", min_value=2015, max_value=datetime.now().year,
                               value=datetime.now().year - 1, step=1)
    c3, c4 = st.columns(2)
    with c3:
        report = st.selectbox("보고서", list(REPORT_CODES))
    with c4:
        fs_label = st.selectbox("재무제표 구분", ["연결재무제표", "별도재무제표"])
    fs_div = "CFS" if fs_label == "연결재무제표" else "OFS"
    annual = report == "사업보고서"
    notes = st.text_area(
        "주석·감사의견 원문 텍스트(선택)",
        placeholder="전체 재무제표 API는 주석의 전문을 제공하지 않습니다. 필요한 문장을 직접 붙여넣으세요.",
        height=95,
    )
    # 검색어가 바뀌면 검색 후보도 재사용하지 않습니다.
    match_state = st.session_state.get("candidate_search")
    if match_state and match_state.get("query") != query.strip():
        st.session_state.pop("candidate_search", None)
        match_state = None

    direct = resolve_direct(query)
    chosen = direct
    if direct:
        st.caption("기업목록 파일을 내려받지 않고 공시 고유번호로 바로 조회합니다.")
    else:
        if st.button("기업 찾기", disabled=not api_enabled):
            st.session_state.pop("candidate_search", None)
            try:
                with st.spinner("기업목록 조회 중..."):
                    matches = search_company_list(cached_corp_list(api_key), query)
                if matches.empty:
                    st.warning("일치하는 기업이 없습니다. 8자리 공시 고유번호를 입력하는 방법도 있습니다.")
                else:
                    st.session_state["candidate_search"] = {
                        "query": query.strip(), "matches": matches.to_dict("records"),
                    }
            except DartError as err:
                st.error(str(err))
                st.info("전체 기업목록 조회가 실패했더라도 공시 고유번호를 알면 직접 조회를 시도할 수 있습니다.")
        match_state = st.session_state.get("candidate_search")
        if match_state and match_state.get("query") == query.strip():
            opts = match_state["matches"]
            if opts:
                chosen_index = st.selectbox(
                    "조회할 법인을 직접 선택하세요",
                    range(len(opts)),
                    format_func=lambda i: f"{opts[i]['corp_name']} ({opts[i]['stock_code'] or '비상장'} / {opts[i]['corp_code']})",
                )
                chosen = opts[chosen_index]

    # 조회 기업 선택이 바뀌면 동일 검색어라도 이전 결과를 표시하지 않습니다.
    sig = signed(query.strip(), int(year), report, fs_div,
                 chosen.get("corp_code", "") if chosen else "")
    saved = st.session_state.get("dart_result")
    if saved and saved.get("sig") != sig:
        st.session_state.pop("dart_result", None)

    if st.button("🏛️ OpenDART에서 조회하고 분석", type="primary", disabled=not api_enabled):
        st.session_state.pop("dart_result", None)  # 실패 이전 자료는 절대 표시하지 않습니다.
        if not chosen:
            st.warning("먼저 기업을 찾고 해당 법인을 선택해 주세요.")
        else:
            try:
                with st.spinner("공식 재무정보 조회 중..."):
                    rows = cached_financials(api_key, chosen["corp_code"], int(year), report, fs_div)
                    received = from_dart(rows, int(year), report)
                if received.empty:
                    st.warning("조회 응답에서 인식 가능한 재무표가 없습니다. 연도·보고서·연결/별도를 다시 확인하세요.")
                else:
                    st.session_state["dart_result"] = {
                        "sig": sig,
                        "data": received,
                        "company": chosen.get("corp_name") or "조회 기업",
                    }
                    st.success(f"{chosen.get('corp_name', '기업')} 조회 완료. 재무제표를 아래에 표시합니다.")
            except DartError as err:
                st.error(str(err))
                st.info("API 장애일 때는 표 붙여넣기 또는 파일 업로드로 분석을 계속할 수 있습니다.")
            except (ValueError, TypeError):
                st.error("조회된 재무자료의 변환에 실패했습니다. 다른 보고서 조건을 확인해 주세요.")
    saved = st.session_state.get("dart_result")
    if saved and saved["sig"] == sig and api_enabled:
        data = saved["data"].copy()
        company = saved["company"]
        nums = data["rcept_no"].dropna()
        for val in nums:
            if re.fullmatch(r"\d{14}", str(val)):
                receipt = str(val)
                break

elif mode == "표 붙여넣기":
    st.subheader("📋 표 붙여넣기")
    st.caption("첫 줄을 `항목 / 2024 / 2025` 등으로 작성하고, 아래 행에 계정명과 수치를 넣으세요.")
    with st.form("paste_form"):
        pasted = {}
        tab_names = ["손익계산서", "재무상태표", "현금흐름표", "자본변동표"]
        tabs = st.tabs(tab_names)
        for tab, stmt in zip(tabs, tab_names):
            with tab:
                pasted[stmt] = st.text_area(f"{stmt} 표", height=200, key="paste_" + stmt)
        notes = st.text_area("주석·감사의견 원문(선택)", height=130, key="pasted_notes")
        company = st.text_input("기업명(선택)", value="", key="paste_company")
        submit = st.form_submit_button("표 분석 실행", type="primary")
    sig = signed(pasted, unit, company)
    if submit:
        st.session_state.pop("paste_result", None)
        try:
            parts = [
                parse_paste(t, stmt, UNITS[unit])
                for stmt, t in pasted.items() if str(t).strip()
            ]
            nonempty = [p for p in parts if not p.empty]
            if nonempty:
                st.session_state["paste_result"] = {
                    "sig": sig, "data": pd.concat(nonempty, ignore_index=True),
                }
            else:
                st.warning("읽을 수 있는 표가 없습니다.")
        except ValueError as err:
            st.warning(str(err))
    saved = st.session_state.get("paste_result")
    if saved and saved["sig"] == sig:
        data = saved["data"].copy()
    elif saved:
        st.session_state.pop("paste_result", None)

elif mode == "엑셀·CSV 업로드":
    st.subheader("📁 엑셀·CSV 업로드")
    st.caption("엑셀 파일은 시트 이름에 손익·재무상태·현금흐름·자본변동 중 하나가 있어야 합니다. CSV는 아래 표 종류를 선택하세요.")
    uploaded = st.file_uploader("재무제표 파일", type=["xlsx", "xls", "csv"])
    csv_stmt = st.selectbox("CSV에 담긴 재무제표 종류", ["손익계산서", "재무상태표", "현금흐름표", "자본변동표"])
    company = st.text_input("기업명(선택)", value="", key="file_company")
    notes = st.text_area("주석·감사의견 원문(선택)", height=120, key="file_notes")
    if uploaded is not None:
        try:
            if uploaded.size > 15 * 1024 * 1024:
                raise ValueError("15MB 이하의 파일을 사용해 주세요.")
            data = parse_uploaded(uploaded, UNITS[unit], csv_stmt)
            if data.empty:
                st.warning("해석 가능한 계정과 금액을 찾지 못했습니다.")
        except (ValueError, pd.errors.ParserError, OSError) as err:
            st.warning("파일 내용을 확인해 주세요. CSV/XLSX 열과 시트 구성을 점검하세요.")
        except Exception:
            st.warning("파일을 읽지 못했습니다. 파일 형식과 인코딩을 확인해 주세요.")


# ─── 공통 검증 및 분석: 실제로 조회된 입력에 대해서만 계산 ───
if data.empty:
    st.info("분석할 자료가 아직 없습니다. 기업 조회가 실패했다면 왼쪽에서 '샘플 체험', '표 붙여넣기', '엑셀·CSV 업로드'를 사용할 수 있습니다.")
    st.stop()

m, evidence, basic_quality = compute_metrics(data, annual=annual)
audits = integrity_checks(data, annual=annual)
history = yearly_matrix(data)
insights = interpret(m, history, annual)
note_hits = notes_in_context(notes)

st.markdown(f"### {company or '직접 입력한 자료'}")
st.caption(f"최근 분석기간: {m.get('period','-')} · {'연간' if annual else '중간기간 누적'} · "
           f"입력 계정 {len(data):,}건 · 자동 조회는 재무제표 본문만 제공하며 주석 전문은 별도 입력이 필요합니다.")
if receipt:
    st.markdown(f"[전자공시시스템의 원문 열기](https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt})")
if mode == "샘플 체험":
    st.warning("현재 값은 가상의 샘플입니다. 특정 기업의 실제 재무상태가 아닙니다.")
if not annual:
    st.info("중간기간 손익 및 현금흐름은 누적치입니다. 연간 수익성과 단순 비교하지 않습니다.")

k1,k2,k3,k4=st.columns(4)
with k1:
    st.metric("매출액", fmt_won(m.get("revenue")))
with k2:
    st.metric("영업이익", fmt_won(m.get("op_income")))
with k3:
    st.metric("영업현금흐름", fmt_won(m.get("op_cf")))
with k4:
    st.metric("기말 현금및현금성자산", fmt_won(m.get("cash")))

st.markdown('<div class="soft-note">분석 결과의 경고 표시는 확정된 부실 판정이 아닙니다. 수치가 변한 이유는 계약 조건, 회계정책, 원문 주석과 실제 자금 일정을 대조해 확인해야 합니다.</div>',unsafe_allow_html=True)

overview_tab, profit_tab, cash_tab, assets_tab, proof_tab, schedule_tab, export_tab = st.tabs([
    "종합 진단", "손익·수익성", "현금흐름·운전자본", "자산·부채", "원본·주석·검증", "자금 일정", "내보내기"
])

with overview_tab:
    st.markdown("#### 지금 가장 먼저 볼 부분")
    st.caption("확인된 수치 → 가능한 해석 → 다음 질문 순서로 읽으세요. 업종과 기업의 상황을 단정하지 않습니다.")
    for item in insights[:6]:
        with st.container(border=True):
            kind = {"watch":"⚠️ 추가 확인", "check":"🔎 검토", "missing":"◻️ 자료 필요"}.get(item["kind"],"🔎 검토")
            st.markdown(f"**{kind} · {item['title']}**")
            st.write(item["evidence"])
            st.caption(f"다음 질문: {item['question']}")
    serious = [a for a in audits if a["level"] == "error"]
    missing = [a for a in audits if a["level"] == "missing"]
    st.divider()
    if serious:
        st.error(f"데이터 일관성 확인 필요: {len(serious)}건. 상세 내용은 '원본·주석·검증'에서 확인하세요.")
    elif missing:
        st.warning(f"식별되지 않은 핵심 계정 {len(missing)}건. 누락 계정은 0원으로 계산하지 않았습니다.")
    else:
        st.success("기본 합계·필수 항목 검토 완료. 감사의견을 대신하지 않습니다.")

with profit_tab:
    st.markdown("#### 매출과 이익의 흐름")
    st.caption("금액 단위: 억원. 제공된 기간의 수치만 표시합니다.")
    show = history[["기간", "revenue", "op_income", "net_income"]].set_index("기간").rename(
        columns={"revenue":"매출액","op_income":"영업이익","net_income":"당기순이익"}
    ) / 100_000_000
    if show.notna().any().any():
        st.line_chart(show)
    else:
        st.info("손익 계정이 없어 추이 차트를 생성할 수 없습니다.")
    left,right=st.columns(2)
    with left:
        st.metric("영업이익률", fmt_pct(m.get("op_margin")))
        st.metric("순이익률", fmt_pct(m.get("net_margin")))
    with right:
        if annual:
            st.metric("매출 증가율", fmt_pct(m.get("revenue_growth")))
            st.metric("영업이익 증감률", fmt_pct(m.get("op_income_growth")))
        else:
            st.info("반기·분기 수치로 연간 성장률을 계산하지 않습니다.")
    if history["op_margin"].notna().any():
        st.markdown("**영업이익률 변화(%)**")
        series = history.set_index("기간")["op_margin"].mul(100)
        st.line_chart(series.to_frame("영업이익률(%)"))
    st.markdown("**추가로 확인할 항목**")
    st.write("매출총이익률과 판매관리비 증감, 프로젝트별 수익성, 일회성 손익을 감사보고서와 주석에서 대조하세요.")
    st.caption("매출액 증가만으로 프로젝트의 수익성이 좋아졌다고 판단하지 않습니다.")

with cash_tab:
    st.markdown("#### 손익과 현금흐름은 다르게 움직일 수 있습니다")
    if all(is_num(m.get(k)) for k in ("net_income","op_cf")):
        diff = m["op_cf"] - m["net_income"]
        col1,col2,col3=st.columns(3)
        col1.metric("순이익",fmt_won(m["net_income"]))
        col2.metric("영업활동 현금흐름",fmt_won(m["op_cf"]))
        col3.metric("현금흐름 - 순이익",fmt_won(diff))
    st.caption("두 금액의 차이만으로 회수 지연이나 분식회계를 단정할 수 없습니다. 운전자본 변동과 비현금 조정을 확인해야 합니다.")
    cf = history[["기간","op_cf","inv_cf","fin_cf"]].set_index("기간").rename(
        columns={"op_cf":"영업활동","inv_cf":"투자활동","fin_cf":"재무활동"}
    ) / 100_000_000
    if cf.notna().any().any():
        st.markdown("**활동별 현금흐름(억원)**")
        st.bar_chart(cf)
    st.divider()
    st.markdown("#### 매출채권과 매출의 방향 비교")
    rev_growth = m.get("revenue_growth")
    ar_growth = m.get("receivables_growth")
    a,b=st.columns(2)
    a.metric("매출 증가율",fmt_pct(rev_growth) if annual else "연간 비교 제외")
    b.metric("매출채권 계정 증감률",fmt_pct(ar_growth) if annual else "연간 비교 제외")
    st.caption("계정명에 따라 매출채권에 기타채권이 포함될 수 있습니다. 증가가 곧 대금 미회수 또는 부실을 의미하지 않습니다.")
    if history["receivables"].notna().any():
        st.line_chart(history.set_index("기간")[["receivables","cash"]].div(100_000_000).rename(
            columns={"receivables":"매출채권 계정","cash":"현금및현금성자산"}
        ))
    st.markdown("**감사보고서에서 확인할 질문**")
    st.write("① 주요 고객사별 지급 조건은? ② 계약상 정산일과 실제 회수일은? ③ 매출채권 손실충당금은 어떻게 변했는가?")
    st.write("④ 영업현금흐름과 순이익의 차이를 만든 가장 큰 운전자본 항목은 무엇인가?")
    if is_num(m.get("capex")) and is_num(m.get("op_cf")):
        st.metric("영업현금흐름 - 유형자산 취득액(참고)",fmt_won(m["op_cf"]-abs(m["capex"])))
        st.caption("무형자산 취득·사업결합 등 다른 투자 현금흐름은 포함하지 않은 간이 계산입니다.")

with assets_tab:
    st.markdown("#### 단기 지급 여력과 자본구조")
    x1,x2,x3=st.columns(3)
    x1.metric("유동비율", fmt_pct(m.get("current_ratio")))
    x2.metric("부채비율", fmt_pct(m.get("debt_ratio")))
    x3.metric("현금및현금성자산", fmt_won(m.get("cash")))
    if history["working_capital"].notna().any():
        st.markdown("**순운전자본(유동자산-유동부채)**")
        st.bar_chart(history.set_index("기간")["working_capital"].div(100_000_000).to_frame("순운전자본(억원)"))
    st.markdown("#### 자금 담당자가 주석에서 확인할 항목")
    for title, detail in [
        ("① 차입금의 만기와 상환 계획", "유동성장기차입금, 만기일, 담보, 차환계획은 본문의 총부채만으로는 알 수 없습니다."),
        ("② 지급보증과 법인카드 약정", "보증 한도와 실제 사용액 또는 현재 부채는 다를 수 있습니다."),
        ("③ 특수관계자 대여금", "개별 재무제표의 거래와 연결 내부거래 제거를 구분하고 회수 조건을 확인해야 합니다."),
        ("④ 우발부채와 계속기업", "감사의견과 주석의 문맥을 함께 읽어야 하며 키워드 검색만으로 판정하지 않습니다."),
    ]:
        with st.expander(title):
            st.write(detail)
    st.info("차입금 만기별 합계는 제공된 재무제표 API만으로 검증하기 어려워 자동 산출하지 않습니다. 만기 주석을 별도로 확인하세요.")

with proof_tab:
    st.markdown("#### 기본 검증")
    for audit in audits:
        label=f"**{audit['title']}** — {audit['detail']}"
        if audit["level"]=="error":
            st.error(label)
        elif audit["level"]=="missing":
            st.warning(label)
        elif audit["level"]=="ok":
            st.success(label)
        else:
            st.info(label)
    if basic_quality:
        with st.expander("기존 기초 계산 검사 결과"):
            for line in basic_quality:
                st.write("•",line)
    st.divider()
    st.markdown("#### 계산에 사용한 계정의 출처")
    if evidence:
        st.dataframe(pd.DataFrame(evidence),use_container_width=True,hide_index=True)
    else:
        st.info("계산에 사용한 계정 정보가 없습니다.")
    st.divider()
    st.markdown("#### 원본 재무표")
    st.caption("자동 추출한 값은 원문과 대조하세요. 계정명 중복은 임의 합산하지 않습니다.")
    statements = list(data.statement.unique())
    chosen_stmt=st.selectbox("재무표 선택",statements)
    subset=data[data.statement==chosen_stmt]
    pivot=subset.pivot_table(index="account",columns="period",values="amount",aggfunc="first")
    formatted=pivot.copy()
    for col in formatted:
        formatted[col]=formatted[col].map(fmt_won)
    st.dataframe(formatted.reset_index(),hide_index=True,use_container_width=True)
    st.divider()
    st.markdown("#### 주석·감사의견 문맥 확인")
    st.caption("주석 문장은 상단의 입력 영역에 직접 붙여넣은 것만 검사합니다. 재무제표 API만으로 주석을 자동 분석한 것이 아닙니다.")
    if not notes.strip():
        st.info("주석 원문이 입력되지 않아 주석 검토는 수행하지 않았습니다.")
    elif note_hits:
        st.dataframe(pd.DataFrame(note_hits),hide_index=True,use_container_width=True)
    else:
        st.info("등록된 키워드를 찾지 못했습니다. 위험이 없다는 뜻은 아닙니다.")

with schedule_tab:
    st.markdown("#### 자금 일정 시뮬레이터")
    st.info("실제 기업의 자금계획을 자동 예측하지 않습니다. 아래 값은 사용자가 입력한 예정 현금흐름을 계산한 결과입니다.")
    initial=st.number_input("기초 현금(원)",min_value=0,value=15_000_000,step=1_000_000,format="%d")
    if "cash_schedule" not in st.session_state:
        st.session_state["cash_schedule"]=schedule_example()
    edited=st.data_editor(
        st.session_state["cash_schedule"],
        num_rows="dynamic", hide_index=True, use_container_width=True,
        column_config={
            "일자":st.column_config.DateColumn("일자",format="YYYY-MM-DD",required=True),
            "구분":st.column_config.SelectboxColumn("구분",options=["입금","출금"],required=True),
            "내용":st.column_config.TextColumn("내용"),
            "금액(원)":st.column_config.NumberColumn("금액(원)",min_value=0,step=100_000,format="%d",required=True)
        },
        key="cash_editor_v3"
    )
    try:
        future,min_cash=schedule_preview(edited,float(initial))
        if not future.empty:
            total_in=future.loc[future["구분"]=="입금","금액(원)"].sum()
            total_out=future.loc[future["구분"]=="출금","금액(원)"].sum()
            a,b,c=st.columns(3)
            a.metric("예정 입금",fmt_won(total_in))
            b.metric("예정 출금",fmt_won(total_out))
            c.metric("최저 예상 잔액",fmt_won(min_cash))
            st.line_chart(future.set_index("일자")["예상 잔액(원)"].to_frame("잔액(원)"))
            if min_cash < 0:
                st.warning("입력한 계획에서는 일시적인 자금 부족이 예상됩니다. 지급 우선순위나 입금 일정을 검토하세요.")
            else:
                st.caption("입력된 일정 내에서만 계산했습니다. 누락 거래, 수수료, 세금 등은 자동 반영되지 않습니다.")
            safe_events=future.copy()
            for c in ["내용","구분"]:
                safe_events[c]=safe_events[c].astype(str).map(lambda s: "'"+s if s.lstrip().startswith(("=","+","-","@")) else s)
            st.download_button("입출금 시뮬레이션 CSV",
                               safe_events.to_csv(index=False).encode("utf-8-sig"),
                               file_name="cash_schedule_example.csv",mime="text/csv")
        else:
            st.caption("입출금 일정을 한 줄 이상 입력하면 결과를 볼 수 있습니다.")
    except (ValueError,TypeError) as error:
        st.warning(str(error))
    st.caption("보안상 실제 회사의 내부 계좌정보·고객정보·비공개 자료를 공용 앱에 입력하지 마세요.")

with export_tab:
    st.markdown("#### 분석 자료 내보내기")
    st.caption("CSV는 엑셀에서 열 수 있습니다. 외부 입력 텍스트의 수식 실행 가능성을 줄이는 이스케이프를 적용합니다.")
    export = data.copy()
    for col in ["statement","account","account_id","source","rcept_no","period"]:
        export[col] = export[col].astype(str).map(
            lambda x: "'"+x if x.lstrip().startswith(("=", "+", "-", "@")) else x)
    st.download_button("정규화된 재무 계정 CSV", export.to_csv(index=False).encode("utf-8-sig"),
                       file_name="financial_data_v3.csv",mime="text/csv")
    report_lines = [
        f"기업: {company or '직접 입력'}", f"기준기간: {m.get('period','')}", "",
        "핵심 수치",
        *[f"{label}: {fmt_won(m.get(k))}" for label,k in [
            ("매출액","revenue"),("영업이익","op_income"),("순이익","net_income"),
            ("영업활동 현금흐름","op_cf"),("현금및현금성자산","cash")]],
        "", "다음 확인할 질문",
        *[f"- {x['title']}: {x['question']}" for x in insights],
        "", "중요: 입력자료 기준의 참고용 분석입니다. 감사/투자/신용 판단을 대신하지 않습니다."
    ]
    st.download_button("검토 질문 포함 요약 TXT", "\n".join(report_lines).encode("utf-8"),
                       file_name="financial_review_v3.txt", mime="text/plain")

st.divider()
st.caption("출처: [전자공시시스템(DART)](https://dart.fss.or.kr/) · "
           "[OpenDART API](https://opendart.fss.or.kr/) · "
           "공시 원문·감사보고서 주석과 비교해 검증해야 합니다.")
