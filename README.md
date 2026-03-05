# Lecture2Summary — AI 강의 녹취 및 핵심 요약 서비스

Gemini AI를 활용하여 강의 녹음 파일을 텍스트로 변환하고, 핵심 내용을 요약해주는 웹 서비스입니다. 특히 PDF 교안을 함께 업로드하면 전문 용어를 더욱 정확하게 교정합니다.

## ✨ 주요 기능

-   **브라우저 녹음 및 파일 업로드**: 실시간 음성 녹음 또는 기존 오디오 파일(MP3, M4A 등) 업로드 지원.
-   **교안 기반 텍스트 교정**: PDF 교안을 참고하여 AI가 오타 및 전문 용어를 정확하게 수정.
-   **핵심 요약 생성**: 긴 강의 내용을 한눈에 보기 쉽게 요약.
-   **실시간 사용량 대시보드**: WebSocket을 통해 현재 사용 중인 모델별 토큰 및 요청 수 실시간 모니터링.
-   **모델 자동 폴백(Fallback)**: 특정 모델의 Quota가 초과될 경우 하위 모델로 자동 전환하여 분석 완료.
-   **영구 저장소**: PostgreSQL(메타데이터) 및 MinIO(오브젝트 스토리지)를 활용한 안정적인 데이터 관리.

## 🛠 기술 스택

-   **Backend**: FastAPI (Python)
-   **Frontend**: Vanilla JS, CSS (Modern & Premium Design)
-   **AI**: Google Gemini API (2.5 Flash, 2.0 Flash, 2.0 Flash Lite 등)
-   **Database**: PostgreSQL
-   **Storage**: MinIO (S3 Compatible)
-   **Infrastructure**: Docker, Docker Compose

## 🚀 시작하기

### 1. 환경 설정
`.env` 파일에 Gemini API 키를 설정하거나 실행 시 환경 변수로 전달해야 합니다.

### 2. 실행 (Docker Compose)
프로젝트 루트 디렉토리에서 아래 명령어를 실행하세요.

```bash
GEMINI_API_KEY="YOUR_API_KEY" docker-compose up --build -d
```

### 3. 접속
-   **웹 서비스**: [http://localhost:8000](http://localhost:8000)
-   **MinIO 콘솔**: [http://localhost:9001](http://localhost:9001) (ID/PW: minioadmin / minioadmin123)

## 📊 모델 폴백 순서
무료 티어 사용량 제한을 극복하기 위해 아래 순서대로 자동 시도합니다:
1. `gemini-2.5-flash`
2. `gemini-2.0-flash`
3. `gemini-2.0-flash-lite`
4. `gemini-3-flash-preview`
5. `gemini-2.5-flash-lite`

## 📝 라이선스
MIT License
