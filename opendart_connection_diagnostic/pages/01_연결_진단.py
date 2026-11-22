"""OpenDART 연결 확인 전용 페이지. 인증키는 화면이나 로그에 출력하지 않습니다."""
import requests
import streamlit as st

st.set_page_config(page_title="OpenDART 네트워크 진단", page_icon="🔎")
st.title("🔎 OpenDART 네트워크 진단")
st.info("Streamlit 서버에서 일반 웹사이트와 OpenDART에 직접 접속합니다. 인증키는 표시하지 않습니다.")

def probe(label, url, *, params=None):
    try:
        response = requests.get(
            url,
            params=params,
            timeout=(7, 15),
            allow_redirects=False,
        )
        st.write(f"**{label}:** HTTP {response.status_code}")
        if label == "OpenDART 기업개황 API" and response.status_code == 200:
            try:
                body = response.json()
                status = str(body.get("status", "응답 없음"))
                message = str(body.get("message", "응답 없음"))
                if status.isdigit() and len(status) == 3:
                    st.write(f"OpenDART status: **{status}**, message: **{message[:80]}**")
                else:
                    st.write("예상하지 못한 API 응답입니다.")
            except ValueError:
                st.write("JSON 대신 다른 형식의 응답을 받았습니다.")
    except requests.exceptions.ConnectTimeout:
        st.error(f"{label}: ConnectTimeout (연결 단계에서 시간 초과)")
    except requests.exceptions.ReadTimeout:
        st.error(f"{label}: ReadTimeout (응답 수신 단계에서 시간 초과)")
    except requests.exceptions.SSLError:
        st.error(f"{label}: SSLError (TLS 인증서/연결 오류)")
    except requests.exceptions.ConnectionError:
        st.error(f"{label}: ConnectionError (DNS, 네트워크 경로 또는 접속 제한 가능)")
    except requests.exceptions.RequestException as exc:
        st.error(f"{label}: {type(exc).__name__}")

if st.button("3가지 연결 테스트", type="primary"):
    probe("일반 웹사이트", "https://www.python.org/")
    probe("OpenDART 홈페이지", "https://opendart.fss.or.kr/")
    try:
        key = str(st.secrets.get("OPENDART_API_KEY", "")).strip()
    except Exception:
        key = ""
    if not key:
        st.warning("Streamlit Secrets에서 OPENDART_API_KEY를 읽지 못했습니다.")
    else:
        probe(
            "OpenDART 기업개황 API",
            "https://opendart.fss.or.kr/api/company.json",
            params={"crtfc_key": key, "corp_code": "00126380"},
        )

st.caption("API 키, 전체 요청 URL, 응답 개인정보는 출력하지 않습니다.")
