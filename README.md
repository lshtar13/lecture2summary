# Lecture2Summary

AI 기반 강의 녹취 및 요약 서비스입니다. 강의 오디오를 업로드하거나 브라우저에서 직접 녹음하면, Google Gemini AI가 자동으로 텍스트 변환과 핵심 요약을 생성합니다. 선택적으로 PDF 교안을 함께 업로드하면 전문 용어를 정확히 교정합니다.

## 주요 기능

- **오디오 텍스트 변환** — 강의 오디오 파일(MP3, M4A, WAV, WebM, OGG)을 텍스트로 변환
- **핵심 요약 생성** — AI가 강의 내용을 분석하여 핵심 요약 제공
- **교안 기반 교정** — PDF 교안을 참고하여 전문 용어를 정확히 교정
- **브라우저 녹음** — 별도 프로그램 없이 브라우저에서 직접 녹음 가능 (실시간 파형 시각화)
- **타임스탬프 포함** — 변환된 텍스트에 MM:SS 형식의 타임스탬프 포함
- **작업 기록 관리** — 이전 작업 조회, 재시도, 삭제 및 텍스트 파일 다운로드

## 기술 스택

| 구분 | 기술 |
|------|------|
| Backend | FastAPI, Uvicorn |
| AI | Google Gemini API |
| Database | PostgreSQL 15 (asyncpg, SQLAlchemy) |
| Storage | MinIO (S3 호환 오브젝트 스토리지) |
| Frontend | Vanilla JavaScript, HTML5, CSS3 |
| Infra | Docker, Docker Compose |

## 프로젝트 구조

```
lecture2summary/
├── Dockerfile
├── docker-compose.yml
├── test_stt.py              # Gemini 처리 CLI 테스트 스크립트
└── app/
    ├── main.py              # FastAPI 애플리케이션
    ├── services/
    │   ├── gemini.py        # Google Gemini AI 서비스
    │   ├── db.py            # PostgreSQL 비동기 ORM
    │   ├── storage.py       # MinIO 스토리지 연동
    │   └── pdf.py           # PDF 텍스트 추출
    └── static/
        ├── index.html       # SPA 프론트엔드
        ├── app.js           # 프론트엔드 로직
        └── style.css        # 다크 테마 스타일
```

## 시작하기

### 사전 요구사항

- [Docker](https://docs.docker.com/get-docker/) 및 [Docker Compose](https://docs.docker.com/compose/install/)
- [Google Gemini API 키](https://aistudio.google.com/apikey)

### 설치 및 실행

1. 저장소를 클론합니다.

   ```bash
   git clone https://github.com/lshtar13/lecture2summary.git
   cd lecture2summary
   ```

2. `.env` 파일을 생성하고 Gemini API 키를 설정합니다.

   ```bash
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

3. Docker Compose로 실행합니다.

   ```bash
   docker compose up --build
   ```

4. 브라우저에서 [http://localhost:8000](http://localhost:8000)에 접속합니다.

### 서비스 구성

| 서비스 | 포트 | 설명 |
|--------|------|------|
| app | 8000 | FastAPI 웹 애플리케이션 |
| db | 5432 | PostgreSQL 데이터베이스 |
| minio | 9000 / 9001 | MinIO 오브젝트 스토리지 / 관리 콘솔 |

## 환경 변수

| 변수명 | 설명 | 기본값 |
|--------|------|--------|
| `GEMINI_API_KEY` | Google Gemini API 키 | (필수) |
| `DATABASE_URL` | PostgreSQL 연결 문자열 | `postgresql+asyncpg://admin:admin123@db:5432/lecture2summary` |
| `MINIO_ENDPOINT` | MinIO 엔드포인트 | `minio:9000` |
| `MINIO_ACCESS_KEY` | MinIO 접근 키 | `minioadmin` |
| `MINIO_SECRET_KEY` | MinIO 시크릿 키 | `minioadmin123` |
| `MINIO_BUCKET_NAME` | MinIO 버킷 이름 | `lectures` |
| `MINIO_SECURE` | MinIO HTTPS 사용 여부 | `False` |

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `POST` | `/api/upload` | 오디오(+PDF) 업로드 및 처리 시작 |
| `GET` | `/api/status/{task_id}` | 작업 처리 상태 조회 |
| `GET` | `/api/result/{task_id}` | 완료된 결과(요약/텍스트) 조회 |
| `GET` | `/api/history` | 전체 작업 기록 조회 |
| `POST` | `/api/retry/{task_id}` | 실패한 작업 재시도 |
| `GET` | `/api/download/{task_id}` | 변환된 텍스트 파일 다운로드 |
| `DELETE` | `/api/history/{task_id}` | 작업 기록 및 파일 삭제 |

## 사용 방법

1. 웹 페이지에서 오디오 파일을 업로드하거나 브라우저 녹음 기능을 사용합니다.
2. (선택) PDF 교안을 함께 업로드하면 전문 용어 교정 정확도가 높아집니다.
3. "AI 변환 시작" 버튼을 클릭합니다.
4. AI가 분석을 완료하면 핵심 요약과 전체 텍스트를 확인할 수 있습니다.
5. 결과를 텍스트 파일로 다운로드하거나, 기록 탭에서 이전 작업을 관리할 수 있습니다.

## 라이선스

이 프로젝트는 MIT 라이선스를 따릅니다.
