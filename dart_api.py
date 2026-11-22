"""OpenDART 통신 계층. 인증키/요청 URL이 오류 메시지에 절대 포함되지 않도록 설계."""
from __future__ import annotations

import io
import re
import time
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Callable

import pandas as pd
import requests

# 금융감독원이 공식 문서에 기재한 두 API 주소입니다.
# 한국어 API가 연결 시간 초과일 때 영어 API 호스트로 한 번 자동 전환합니다.
API_ENDPOINTS = (
    ("https://opendart.fss.or.kr", "/api"),
    ("https://engopendart.fss.or.kr", "/engapi"),
)
BASE_URL = API_ENDPOINTS[0][0]
REPORT_CODES = {
    "사업보고서": "11011",
    "반기보고서": "11012",
    "1분기보고서": "11013",
    "3분기보고서": "11014",
}

STATUS_MESSAGES = {
    "010": "인증키가 등록되어 있지 않습니다. Secrets의 키 값을 확인하세요.",
    "011": "사용할 수 없는 인증키입니다. OpenDART 사용 가능 여부를 확인하세요.",
    "012": "접근 IP가 허용되지 않았습니다. OpenDART의 IP 제한을 확인하세요.",
    "013": "해당 조건에 재무자료가 없습니다. 연도·보고서·연결/별도를 확인하세요.",
    "014": "요청한 파일이 없습니다.",
    "020": "API 호출 횟수 제한입니다.",
    "021": "허용된 조회 회사 수를 초과했습니다.",
    "100": "요청 파라미터가 올바르지 않습니다.",
    "101": "허용되지 않은 접근입니다.",
    "800": "OpenDART 시스템 점검 중입니다.",
    "900": "OpenDART 서버 오류입니다.",
    "901": "인증키의 개인정보 보유기간이 만료되었습니다.",
}


@dataclass
class DartError(Exception):
    stage: str
    kind: str
    code: str = ""

    def __str__(self):
        if self.kind == "api":
            hint = STATUS_MESSAGES.get(self.code, "응답코드를 확인할 수 없습니다.")
            return f"{self.stage}: OpenDART 상태 {self.code or '확인 불가'} — {hint}"
        hints = {
            "connect_timeout": "서버 연결 시간이 초과됐습니다.",
            "read_timeout": "연결 후 응답 수신 시간이 초과됐습니다.",
            "ssl": "SSL 인증서 검증에 실패했습니다.",
            "proxy": "네트워크 프록시 연결에 실패했습니다.",
            "connection": "서버에 연결할 수 없습니다(DNS/IP/네트워크 확인).",
            "http": f"HTTP 오류 {self.code}" if self.code else "HTTP 오류가 발생했습니다.",
            "format": "OpenDART 응답 형식이 올바르지 않습니다.",
            "invalid": "입력값이 올바르지 않습니다.",
        }
        return f"{self.stage}: {hints.get(self.kind, '알 수 없는 통신 오류')}"

# OpenDART에서 검증된 최소한의 매핑만 유지합니다.
KNOWN_CORPS = {
    "삼성전자": {"corp_code": "00126380", "stock_code": "005930", "corp_name": "삼성전자"},
    "005930": {"corp_code": "00126380", "stock_code": "005930", "corp_name": "삼성전자"},
    "00126380": {"corp_code": "00126380", "stock_code": "005930", "corp_name": "삼성전자"},
}


class DartClient:
    def __init__(self, api_key: str, getter: Callable | None = None,
                 sleeper: Callable = time.sleep):
        self.api_key = str(api_key or "").strip()
        if not self.api_key:
            raise DartError("설정", "invalid")
        self.getter = getter or requests.get
        self.sleeper = sleeper

    def request(self, path: str, stage: str, params: dict | None = None,
                timeout=(5, 20), attempts=2):
        """동일 기관이 공개한 대체 호스트로 자동 전환합니다.

        인증/쿼터/입력값 오류 등 API가 *정상 응답*을 돌려준 경우에는
        우회하지 않습니다. IP 정책을 회피하는 용도가 아닙니다.
        """
        allowed = {
            "/api/corpCode.xml",
            "/api/company.json",
            "/api/fnlttSinglAcntAll.json",
        }
        if path not in allowed:
            raise DartError(stage, "invalid")
        args = {"crtfc_key": self.api_key, **(params or {})}
        # 연결이 안 되는 호스트에 같은 요청을 세 번씩 반복하지 않고
        # 공식 대체 호스트를 바로 시도합니다.
        last_error = None
        for base, api_prefix in API_ENDPOINTS:
            url = base + api_prefix + path[len("/api"):]
            try:
                resp = self.getter(
                    url,
                    params=args,
                    timeout=timeout,
                    headers={
                        "User-Agent": "Mozilla/5.0 (compatible; FinancialHealthReader/3.1)",
                        "Accept": "application/json, application/xml, application/zip",
                    },
                )
                # 사용제한·인증·입력 오류: 다른 호스트로 재시도하면 안 됩니다.
                if resp.status_code in (400, 401, 403, 404, 429):
                    raise DartError(stage, "http", str(resp.status_code))
                if resp.status_code >= 500:
                    last_error = DartError(stage, "http", str(resp.status_code))
                    continue
                if resp.status_code >= 300:
                    raise DartError(stage, "http", str(resp.status_code))
                return resp
            except DartError:
                raise
            except requests.exceptions.SSLError:
                last_error = DartError(stage, "ssl")
            except requests.exceptions.ProxyError:
                last_error = DartError(stage, "proxy")
            except requests.exceptions.ConnectTimeout:
                last_error = DartError(stage, "connect_timeout")
            except requests.exceptions.ReadTimeout:
                last_error = DartError(stage, "read_timeout")
            except requests.exceptions.RequestException:
                last_error = DartError(stage, "connection")
        raise last_error or DartError(stage, "connection")

    @staticmethod
    def read_json(response, stage):
        try:
            obj = response.json()
            if not isinstance(obj, dict):
                raise ValueError("JSON object expected")
        except (ValueError, TypeError):
            raise DartError(stage, "format") from None
        status = str(obj.get("status", ""))
        if status != "000":
            raise DartError(stage, "api", status if re.fullmatch(r"\d{3}", status) else "")
        return obj

    def company_info(self, corp_code="00126380"):
        if not re.fullmatch(r"\d{8}", corp_code):
            raise DartError("기업개황", "invalid")
        response = self.request(
            "/api/company.json", "기업개황",
            {"corp_code": corp_code},
            timeout=(8, 15),
        )
        return self.read_json(response, "기업개황")

    def fetch_financials(self, corp_code: str, year: int, report: str, fs_div: str):
        if not re.fullmatch(r"\d{8}", str(corp_code)):
            raise DartError("재무제표", "invalid")
        if report not in REPORT_CODES or fs_div not in ("CFS", "OFS") or not 2015 <= int(year) <= 2100:
            raise DartError("재무제표", "invalid")
        response = self.request(
            "/api/fnlttSinglAcntAll.json",
            "재무제표",
            {
                "corp_code": str(corp_code),
                "bsns_year": str(year),
                "reprt_code": REPORT_CODES[report],
                "fs_div": fs_div,
            },
        )
        data = self.read_json(response, "재무제표")
        rows = data.get("list", [])
        if not isinstance(rows, list):
            raise DartError("재무제표", "format")
        if rows and any(str(r.get("bsns_year", year)) != str(year) for r in rows):
            raise DartError("재무제표", "format")
        # 엉뚱한 회사의 응답을 현재 조회 결과로 표시하지 않습니다.
        if rows and any(
            str(r.get("corp_code")) != str(corp_code)
            for r in rows if r.get("corp_code")
        ):
            raise DartError("재무제표", "format")
        return rows

    def fetch_corp_codes(self) -> pd.DataFrame:
        response = self.request(
            "/api/corpCode.xml", "기업목록", timeout=(8, 45),
        )
        blob = response.content
        if len(blob) > 40_000_000:
            raise DartError("기업목록", "format")
        # API 오류는 HTTP 200과 XML로 돌아오기도 합니다.
        if not zipfile.is_zipfile(io.BytesIO(blob)):
            try:
                code = (ET.fromstring(blob).findtext("status") or "").strip()
            except ET.ParseError:
                raise DartError("기업목록", "format") from None
            raise DartError("기업목록", "api", code if re.fullmatch(r"\d{3}", code) else "")
        try:
            with zipfile.ZipFile(io.BytesIO(blob)) as z:
                names = [n for n in z.namelist() if n.lower().endswith(".xml")]
                if len(names) != 1:
                    raise ValueError("expected single XML")
                member = z.getinfo(names[0])
                if member.file_size > 65_000_000:
                    raise ValueError("XML is too large")
                root = ET.fromstring(z.read(member))
            records = []
            for item in root.findall("list"):
                records.append({
                    "corp_code": (item.findtext("corp_code") or "").strip(),
                    "corp_name": (item.findtext("corp_name") or "").strip(),
                    "corp_eng_name": (item.findtext("corp_eng_name") or "").strip(),
                    "stock_code": (item.findtext("stock_code") or "").strip(),
                })
            if not records:
                raise ValueError("empty company list")
            return pd.DataFrame.from_records(records)
        except (zipfile.BadZipFile, ValueError, ET.ParseError, OSError):
            raise DartError("기업목록", "format") from None


def resolve_direct(query: str):
    q = str(query or "").strip()
    if q in KNOWN_CORPS:
        return KNOWN_CORPS[q].copy()
    if re.fullmatch(r"\d{8}", q):
        return {"corp_code": q, "stock_code": "", "corp_name": f"공시 고유번호 {q}"}
    return None


def search_company_list(frame: pd.DataFrame, query: str) -> pd.DataFrame:
    q = re.sub(r"\s+", "", str(query or "")).casefold()
    if not q or frame.empty:
        return frame.iloc[:0].copy()
    df = frame.copy()
    names = df["corp_name"].fillna("").astype(str).str.replace(r"\s+", "", regex=True).str.casefold()
    engs = df["corp_eng_name"].fillna("").astype(str).str.replace(r"\s+", "", regex=True).str.casefold()
    stocks = df["stock_code"].fillna("").astype(str)
    scores = (names == q).astype(int) * 100
    scores += (stocks == query.strip()).astype(int) * 120
    scores += names.str.contains(re.escape(q), regex=True).astype(int) * 25
    scores += engs.str.contains(re.escape(q), regex=True).astype(int) * 20
    df["score"] = scores
    return df[df["score"] > 0].sort_values(["score", "corp_name"], ascending=[False, True]).head(20)
