"""OpenDART 조회 상태 및 종합점수의 최소 검증 규칙.

인증키 자체를 저장하거나 로그에 기록하지 않습니다.
"""
import pandas as pd

REQUIRED_SCORE_FIELDS = {
    "revenue": "매출액",
    "operating_income": "영업이익",
    "net_income": "당기순이익",
    "total_assets": "자산총계",
    "total_liabilities": "부채총계",
    "total_equity": "자본총계",
    "operating_cf": "영업활동현금흐름",
}

def missing_score_fields(metrics):
    """종합점수에 필요한 재무상태표·손익계산서·현금흐름표 항목 검사."""
    missing = []
    for key, name in REQUIRED_SCORE_FIELDS.items():
        value = metrics.get(key)
        if value is None or pd.isna(value):
            missing.append(name)
    return missing

def dart_request_signature(company_query, year, report_name, fs_div_label):
    """검색 조건 서명. API 키 등 비밀정보는 절대 포함하지 않습니다."""
    return (
        str(company_query).strip().casefold(),
        int(year),
        str(report_name),
        str(fs_div_label),
    )

def verify_dart_rows(rows, requested_year):
    """조회 결과가 비어 있거나 요청한 연도와 다르면 실패로 처리."""
    if not rows:
        return False, "no_data"
    years = {
        str(row.get("bsns_year", "")).strip()
        for row in rows
        if str(row.get("bsns_year", "")).strip()
    }
    if years and years != {str(requested_year)}:
        return False, "year_mismatch"
    return True, "ok"

def matching_saved_analysis(saved, signature):
    """검색조건과 완전히 일치하는 성공 데이터만 복원."""
    if not saved or saved.get("signature") != signature:
        return None
    df = saved.get("data")
    if not isinstance(df, pd.DataFrame) or df.empty:
        return None
    return saved
