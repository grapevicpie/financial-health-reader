# Streamlit Cloud 배포 가이드

이 앱은 PC와 같은 와이파이가 아니어도 핸드폰 데이터 또는 외부 와이파이로 접속할 수 있게 Streamlit Community Cloud에 배포하는 것을 기준으로 만들었습니다.

## 1. GitHub 저장소 만들기

1. GitHub에서 새 Repository 생성
2. 이름 예시: `financial-health-reader`
3. Public 또는 Private 선택
4. 이 폴더의 파일을 업로드
   - `app.py`
   - `requirements.txt`
   - `README.md`
   - `CLOUD_DEPLOY_GUIDE.md`
   - 샘플 CSV 파일

## 2. Streamlit Community Cloud 배포

1. Streamlit Community Cloud 접속
2. `Create app`
3. Repository 선택
4. Branch: `main`
5. Main file path: `app.py`
6. App URL 예시: `financial-health-reader`
7. Deploy 클릭

배포 후 생성되는 주소 예시:

```text
https://financial-health-reader.streamlit.app
```

이 주소는 PC를 꺼도 핸드폰 데이터/다른 와이파이에서 접속할 수 있습니다.

## 3. 핸드폰 홈화면에 앱처럼 추가

### iPhone

Safari에서 배포 주소 열기 → 공유 버튼 → 홈 화면에 추가

### Android

Chrome에서 배포 주소 열기 → 오른쪽 위 점 3개 → 홈 화면에 추가 또는 앱 설치

## 4. OpenDART API 키 연결

OpenDART 자동 조회를 쓰려면 Streamlit Cloud의 앱 설정에서 Secrets에 아래 내용을 넣습니다.

```toml
OPENDART_API_KEY = "여기에_발급받은_키"
```

저장 후 앱을 재부팅하거나 새로고침합니다.

## 5. 주의

API 키는 GitHub 코드에 넣지 마세요. 반드시 Streamlit Secrets에만 넣으세요.
