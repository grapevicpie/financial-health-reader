# 기업 재무 건강검진 v3

OpenDART 재무제표 및 사용자가 제공한 표·파일을 **근거 중심으로 검토하는 Streamlit 웹앱**입니다.

> 이번 버전은 v2 소스에 디자인과 현금흐름·재무분석 기능을 추가한 완성본입니다.
> 자동 투자판단, 감사보고서 전체 분석, 신용평가 또는 회계감사를 수행하는 프로그램은 아닙니다.

## v3에서 달라진 점

### 디자인
- 다크 네이비와 청록색의 제목 영역, 읽기 쉬운 지표 카드
- 7개 분석 화면: `종합 진단`, `손익·수익성`, `현금흐름·운전자본`, `자산·부채`, `원본·주석·검증`, `자금 일정`, `내보내기`
- `.streamlit/config.toml`을 통한 일관된 Streamlit 테마

### 분석
- **점수식 재무 건강등급 화면 제거**: 임의 가중치에서 나오는 허위 정확성 방지
- 순이익과 영업현금흐름의 차이를 수치로 비교
- 연도별 영업이익률·손익·활동별 현금흐름 추이
- 매출과 채권 계정의 증감률 비교: 기타채권 포함 가능성을 안내
- 순운전자본(유동자산−유동부채) 시계열
- 유동비율·부채비율과 구체적인 추가 검토 질문
- 현금흐름−유형자산취득액의 간이 참고값(다른 투자 지출 제외 안내)
- 계정 중복·충돌·재무상태표 불일치·핵심항목 누락 검증
- 사용자가 붙여넣은 **주석 문장의 앞뒤 문맥**을 키워드별로 보여주기
- 사용자 직접 입력 **예정 입출금 자금 일정 시뮬레이터**
- 진단 질문과 근거 항목, CSV/TXT 내보내기

### API 및 신뢰성
- v2의 OpenDART 오류 분류·재시도·회사 선택·직접 고유번호 조회 유지
- API 결과의 `corp_code`와 `bsns_year` 일치 확인 추가
- `currency`가 KRW가 아닌 응답을 원화로 잘못 읽지 않도록 보호
- 이전 조회 기업의 결과가 남지 않도록 유지
- API 키를 GitHub가 아닌 Streamlit Secrets에만 보관
- 공식 공시 API는 **재무제표 표만 제공합니다**. 주석 전문 및 차입금 만기표는 자동 추출하지 않습니다.

## 파일 구조

```text
app.py                         Streamlit 화면·입력
dart_api.py                    OpenDART 통신
finance.py                     재무표 변환·계정 매칭·기본 지표
insights.py                    새 분석·검증·주석 문맥·자금 일정
requirements.txt              패키지
.streamlit/config.toml          테마
.streamlit/secrets.toml.example Secrets 형식만 보이는 예시(실제 키 없음)
tests/test_finance.py
tests/test_dart_api.py
tests/test_insights.py
설치_가이드.md
```

## 설치 및 배포

1. **기존 GitHub 저장소를 백업**하세요. 복제하거나 새 백업 브랜치를 만드세요.
2. 압축을 풀어 루트의 `app.py`, `dart_api.py`, `finance.py`, `insights.py`, `requirements.txt`를 GitHub 저장소 최상위 경로에 업로드하세요.
3. `.streamlit/config.toml`도 `.streamlit` 디렉터리에 업로드하면 새 테마를 적용할 수 있습니다.
4. Streamlit Cloud의 기존 앱과 연결된 GitHub 브랜치가 이 코드가 들어간 브랜치인지 확인하세요.
5. `App settings → Secrets`에서 다음 값을 **Streamlit에만** 설정합니다.

   ```toml
   OPENDART_API_KEY = "본인 키"
   OPENDART_ENABLED = true
   ```
   실제 API 키는 README·GitHub·채팅에 절대로 입력하지 마세요.
6. 코드 변경이 반영되면 `샘플 체험`으로 화면을 확인하고, 이후 `OpenDART 자동 조회 → API 연결 확인`을 실행하세요.
7. API 연결 성공 시 `00126380` (삼성전자 공시 고유번호)을 직접 조회해 확인합니다.

### 연결 시간 초과가 그대로라면?
설정이 정상이더라도 Streamlit Cloud와 OpenDART 사이의 네트워크 문제일 수 있습니다. 먼저 로그의 ConnectTimeout/ReadTimeout 여부를 확인하세요. 이번 UI 개선 자체가 네트워크 차단을 해결하지는 않습니다. `표 붙여넣기` 또는 `엑셀·CSV 업로드`를 사용할 수 있습니다.

### 로컬 검사
```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v
streamlit run app.py
```

## 계산·해석의 원칙

- 수치가 없으면 0원으로 채우지 않습니다.
- 매출채권 계정은 기타채권이 포함될 수 있으며 이를 실제 회수 지연으로 단정하지 않습니다.
- 반기·분기의 손익·현금흐름은 누적치입니다. **연간 성장률이나 ROE/ROA 등으로 연율화하지 않습니다.**
- 순운전자본(유동자산-유동부채)은 유동성의 참고값입니다. 차입금 상환 일정은 별도 주석 확인이 필요합니다.
- CAPEX를 이용한 간이 FCF는 전체 투자활동 현금흐름을 의미하지 않습니다.
- 연결과 별도 재무제표를 서로 혼합하지 마세요.
- 주석 키워드 탐지 결과는 내용의 위험 여부를 확정하지 않습니다.
- 자금 일정 시뮬레이터의 기본 데이터는 **가상 숫자**입니다. 직접 입력한 거래 일정만 반영합니다.

## 한계와 테스트

- Python 문법 검사와 금융 계산·입력 검증·API 모의응답 테스트를 통과했습니다.
- 실제 Streamlit 화면 렌더링과 OpenDART 라이브 연결은 이 환경에서 실행하지 못했습니다.
- 전자공시 원문·감사보고서 주석 및 최신 변경사항은 이용자가 최종 확인해야 합니다.

## 공식 문서
- OpenDART: https://opendart.fss.or.kr/
- 전체 재무제표 API: https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&apiId=2019020
- Streamlit 테마: https://docs.streamlit.io/develop/concepts/configuration/theming
