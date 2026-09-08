# Review Sentiment

AI 기반 고객 리뷰 감정 분석 대시보드 (Project C)

고객 리뷰 데이터를 수집하고 정제한 뒤 AI를 이용해 감정을 분석하고,
긍정·부정 키워드와 요약 및 개선 제안을 추출하여
통계, 차트, 리포트 형태로 제공하는 Python CLI 프로젝트입니다.

---

## 1. 주요 기능

- CSV / Excel 형식의 리뷰 데이터 불러오기
- 설정 파일 기반 컬럼 자동 매핑
- 리뷰 텍스트, 별점, 날짜 데이터 정제
- SHA-256 기반 `text_hash` 생성 및 중복 처리
- SQLite 데이터베이스 저장 및 조회
- AI 기반 고객 리뷰 감정 분석
  - positive
  - neutral
  - negative
- 감정 분석 신뢰도 점수 저장
- AI 기반 인사이트 추출
  - 긍정 키워드
  - 부정 키워드
  - 빈출 칭찬/불만 사항
  - 전체 리뷰 요약
  - 개선 제안
  - 감정별 리뷰 분석
  - 기간별 리뷰 분석
  - 제품별 리뷰 분석
  - 감정 분석 통계 조회
  - matplotlib 기반 시각화
  - 텍스트 대시보드 리포트 생성
  - CSV / Excel 결과 내보내기
  - 대화형 모드 및 일반 CLI 지원

---

## 2. 프로젝트 구조

```text
review-sentiment/
├── main.py
├── config.json
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
│
├── data/
│   ├── raw/
│   │   └── sample_reviews.csv
│   ├── clean/
│   └── reviews.db
│
├── logs/
├── output/
│
└── src/
    ├── __init__.py
    ├── cli.py
    ├── collector.py
    ├── cleaner.py
    ├── repository.py
    ├── ai_client.py
    ├── analyzer.py
    ├── visualizer.py
    └── reporter.py
```

### 주요 모듈

| 파일 | 역할 |
| --- | --- |
| `main.py` | 프로그램 실행 진입점 |
| `src/cli.py` | CLI 명령어 파싱 및 실행 흐름 제어 |
| `src/collector.py` | CSV / Excel 리뷰 데이터 수집 및 컬럼 매핑 |
| `src/cleaner.py` | 리뷰 텍스트, 별점, 날짜 정제 및 해시 생성 |
| `src/repository.py` | SQLite 스키마, 저장, 조회 및 마이그레이션 |
| `src/ai_client.py` | AI API 호출 및 응답 처리 |
| `src/analyzer.py` | 감정 분석 및 인사이트 추출 흐름 제어 |
| `src/visualizer.py` | matplotlib 기반 차트 생성 |
| `src/reporter.py` | 대시보드 리포트 및 결과 내보내기 |

---

## 3. 개발 환경

- Python 3
- SQLite
- pandas
- openpyxl
- matplotlib
- python-dotenv
- openai

필요한 패키지는 `requirements.txt`를 통해 설치합니다.

---

## 4. 초기 설정

### 4-1. 가상환경 생성

Windows PowerShell 기준:

```powershell
python -m venv .venv
```

### 4-2. 가상환경 활성화

```powershell
.\.venv\Scripts\Activate.ps1
```

### 4-3. 패키지 설치

```powershell
pip install -r requirements.txt
```

### 4-4. 환경변수 파일 생성

`.env.example`을 복사하여 `.env` 파일을 생성합니다.

```powershell
Copy-Item .env.example .env
```

`.env` 파일에 발급받은 API 키를 입력합니다.

```text
OPENAI_API_KEY=발급받은_API_키
```

> `.env`에는 실제 API 키가 포함되므로 Git 저장소에 업로드하지 않습니다.

---

## 5. AI 설정

AI 관련 설정은 `config.json`에서 관리합니다.

예시:

```json
{
  "ai": {
    "api_key_env": "OPENAI_API_KEY",
    "base_url": "https://copa.codyssey.kr/v1",
    "model": "gpt-5-mini",
    "timeout": 30,
    "retry": 2
  }
}
```

프로젝트에서는 Codyssey API의 Chat Completions 방식으로 AI 분석을 수행합니다.

API 키 자체는 `config.json`에 직접 작성하지 않고 `.env`의
`OPENAI_API_KEY` 환경변수를 통해 불러옵니다.

---

## 6. 실행 방법

### 대화형 모드

```powershell
python main.py
```

화면의 질문에 답하면서 기능을 사용할 수 있습니다.

### 일반 CLI

```powershell
python main.py list
```

전체 명령어와 옵션은 다음 명령으로 확인할 수 있습니다.

```powershell
python main.py --help
```

### 공통 옵션 사용 시 주의사항

`--db`, `--config`, `--verbose` 등의 공통 옵션은
서브커맨드 뒤에 작성합니다.

가능:

```powershell
python main.py list --db data/reviews.db
```

잘못된 사용:

```powershell
python main.py --db data/reviews.db list
```

---

## 7. 기본 사용 흐름

프로그램은 다음 순서로 사용하는 것을 권장합니다.

```text
리뷰 데이터 불러오기
        ↓
리뷰 데이터 정제
        ↓
AI 감정 분석
        ↓
AI 인사이트 추출
        ↓
통계 확인
        ↓
대시보드 생성
        ↓
결과 내보내기
```

### 1단계 - 리뷰 데이터 불러오기

```powershell
python main.py import --file data/raw/sample_reviews.csv --db data/reviews.db
```

### 2단계 - 리뷰 데이터 정제

```powershell
python main.py clean --db data/reviews.db
```

### 3단계 - AI 감정 분석

```powershell
python main.py analyze --db data/reviews.db
```

일부 리뷰만 테스트하려면:

```powershell
python main.py analyze --limit 1
```

### 4단계 - AI 인사이트 추출

```powershell
python main.py extract --db data/reviews.db
```

### 5단계 - 통계 확인

```powershell
python main.py stats --db data/reviews.db
```

### 6단계 - 대시보드 생성

```powershell
python main.py dashboard --db data/reviews.db --output output/dashboard
```

### 7단계 - 결과 내보내기

```powershell
python main.py export --db data/reviews.db --format csv --output output/export
```

---

## 8. 주요 CLI 명령어

| 명령어 | 설명 |
| --- | --- |
| `import` | CSV / Excel 리뷰 데이터 가져오기 |
| `clean` | 가져온 리뷰 데이터 정제 |
| `analyze` | AI를 이용한 리뷰 감정 분석 |
| `extract` | 키워드, 요약, 개선 제안 추출 |
| `list` | 리뷰 목록 조회 |
| `show` | 특정 리뷰 상세 조회 |
| `stats` | 리뷰 및 감정 분석 통계 조회 |
| `dashboard` | 차트와 대시보드 리포트 생성 |
| `export` | 분석 결과를 파일로 내보내기 |

세부 옵션은 다음과 같이 확인할 수 있습니다.

```powershell
python main.py <명령어> --help
```

예:

```powershell
python main.py analyze --help
```

---

## 9. 데이터 수집 및 정제

### 데이터 수집

`collector.py`에서는 CSV / Excel 파일을 읽고
`config.json`의 컬럼 설정을 이용하여 리뷰 데이터를 매핑합니다.

지원하는 주요 데이터:

- 리뷰 내용
- 별점
- 작성일
- 상품명

### 데이터 정제

`cleaner.py`에서는 다음 작업을 수행합니다.

- 불필요한 공백 제거
- 반복되는 일부 문장부호 정리
- 별점 형식 정규화
- 날짜 형식 정규화
- 최소 리뷰 길이 검사
- SHA-256 기반 `text_hash` 생성

정제된 리뷰는 SQLite 데이터베이스에 저장됩니다.

### 중복 처리 정책

중복 리뷰는 `config.json`의 `cleaning.duplicate_policy` 또는
`clean --dedup-policy` 옵션으로 처리 방식을 선택할 수 있습니다.

- `skip`: 이미 처리된 중복 리뷰는 건너뜁니다.
- `upsert`: 동일한 `text_hash`의 기존 정제 데이터를 갱신합니다.

예:
```powershell
python main.py clean --db data/reviews.db --dedup-policy skip
python main.py clean --db data/reviews.db --dedup-policy upsert
```

---

## 10. AI 감정 분석

AI는 정제된 고객 리뷰를 다음 세 가지 감정으로 분류합니다.

```text
positive
neutral
negative
```

분석 결과에는 감정 분류와 함께 신뢰도 점수가 저장됩니다.

예:

```text
sentiment  : positive
confidence : 0.99
```

분석 결과는 SQLite 데이터베이스에 저장됩니다.

### 분석 대상 선택

`analyze` 명령은 옵션에 따라 분석 대상을 선택할 수 있습니다.

- `--all`: 전체 정제 리뷰를 대상으로 분석합니다.
- `--unanalyzed`: 아직 감정 분석 결과가 없는 리뷰만 분석합니다.
- `--id`: 특정 리뷰 ID를 지정하여 분석합니다.
- `--limit`: 한 번에 처리할 최대 리뷰 수를 지정합니다.

예:
```powershell
python main.py analyze --db data/reviews.db --unanalyzed --limit 10
python main.py analyze --db data/reviews.db --id 1
```

---

## 11. AI 인사이트 추출

`extract` 명령은 리뷰 데이터를 바탕으로 다음 정보를 추출합니다.

- 긍정 키워드
- 부정 키워드
- 전체 리뷰 요약
- 개선 제안

예시:

```text
긍정 키워드: 만족, 좋음, 칭찬
부정 키워드: 배송지연, 품질불만, 실망

요약:
제품에 대해 긍정적인 반응이 있으나 배송이 늦고
품질에 대한 불만이 주요 문제로 제기되고 있습니다.

개선 제안:
- 품질 관리 강화
- 배송 프로세스 개선
- 배송 지연 시 사전 안내 및 보상 정책 도입
```

추출 결과 역시 데이터베이스에 저장되어
대시보드 리포트에서 활용됩니다.

---

## 12. 통계 조회

다음 명령으로 현재 데이터베이스 상태와 감정 분포를 확인할 수 있습니다.

```powershell
python main.py stats --db data/reviews.db
```

출력 예:

```text
=== 리뷰 분석 통계 ===
원본(raw)   : 3건
정제(clean) : 3건
분석 완료   : 1건
추출 결과   : 1건
평균 별점   : 4.33점

[감정 분포] (모델: gpt-5-mini)
- positive: 1건 (100.0%)
```

---

## 13. 대시보드

대시보드는 분석된 리뷰를 기반으로 핵심 지표와
AI 인사이트를 텍스트 리포트 및 차트로 생성합니다.

```powershell
python main.py dashboard --db data/reviews.db --output output/dashboard
```

### 주요 지표

- 총 리뷰 수
- 긍정 비율
- 중립 비율
- 부정 비율
- 평균 별점
- 평균 신뢰도 점수
- 별점-감정 괴리율
- 긍정 키워드
- 부정 키워드
- AI 인사이트 요약
- 개선 제안

### 생성 차트

```text
sentiment_distribution.png
sentiment_trend.png
rating_sentiment_matrix.png
```

### 시각화 설정

차트 이미지의 해상도는 `config.json`의 `visualization` 설정으로 관리할 수 있습니다.

```json
{
  "visualization": {
    "dpi": 300
  }
}
```

`dpi` 값은 대시보드의 감정 분포, 감정 추이,
별점-감정 매트릭스 차트를 PNG 파일로 저장할 때 적용됩니다.

### 리포트

```text
dashboard_report.txt
```

분석된 리뷰 데이터가 없는 경우에는 임의의 분석 데이터를 자동 생성하지 않고,
차트 생성을 건너뛰며 데이터가 없음을 리포트에 표시합니다.

---

## 14. 결과 내보내기

분석 결과는 파일 형태로 내보낼 수 있습니다.

지원 형식:

- CSV
- JSONL
- Excel

CSV 예시:
```powershell
python main.py export --db data/reviews.db --format csv --output output/export
```

Excel 예시:
```powershell
python main.py export --db data/reviews.db --format excel --output output/export
```

감정과 최소 별점을 이용해 내보낼 데이터를 필터링할 수 있습니다.

예:
```powershell
python main.py export --db data/reviews.db --format csv --sentiment positive --rating-min 4 --output output/export
```

- `--sentiment`: 특정 감정 결과만 선택합니다.
- `--rating-min`: 지정한 별점 이상의 리뷰만 선택합니다.

분석 데이터가 없는 경우 임의의 데이터를 생성하지 않고
빈 템플릿 형태로 저장합니다.

---

## 15. 데이터베이스

프로젝트에서는 SQLite를 사용합니다.

기본 데이터베이스:

```text
data/reviews.db
```

주요 데이터는 단계별로 관리됩니다.

```text
원본 리뷰
    ↓
정제 리뷰
    ↓
AI 감정 분석 결과
    ↓
AI 인사이트 추출 결과
```

기존 데이터베이스에 필요한 컬럼이 없는 경우
초기화 과정에서 스키마 마이그레이션을 수행합니다.

### 로그 관리

프로그램의 주요 실행 과정과 오류는 Python `logging` 모듈을 이용하여 기록합니다.

로그 파일:
```text
logs/app.log
```

주요 로그 수준:

- `INFO`: 명령 실행 시작 및 완료 등 정상적인 실행 정보
- `WARNING`: 조건에 맞는 리뷰가 없는 경우 등 주의가 필요한 상황
- `ERROR`: 잘못된 옵션 사용이나 실행 중 발생한 오류

로그를 통해 CLI 실행 과정과 오류 발생 여부를 확인할 수 있습니다.

---

## 16. 데이터 편향 및 주의사항

분석 결과는 입력 리뷰 데이터의 품질과 분포에 영향을 받습니다.

리뷰 수가 적거나 특정 상품, 기간 또는 감정에 편향된 경우
감정 비율, 키워드 및 AI 요약 결과가 실제 고객 전체의 의견을
대표하지 않을 수 있습니다.

또한 AI가 생성한 감정 분석, 키워드, 요약 및 개선 제안은
입력 데이터와 AI 모델의 응답에 따라 달라질 수 있습니다.

따라서 분석 결과는 고객 리뷰를 이해하기 위한 참고 자료로 활용하는 것을 권장합니다.

---

## 17. 팀 역할 분담

본 프로젝트는 4인 팀 프로젝트로 진행했습니다.

| 담당 | 주요 역할 |
| --- | --- |
| 조장 - 양승현 | `collector.py`, `cleaner.py`, 전체 통합 및 테스트 |
| 박상훈 | `repository.py`, `cli.py` |
| 안소연 | `ai_client.py`, `analyzer.py`, AI/CLI 연동 |
| 정형경 | `visualizer.py`, `reporter.py` |

각 기능을 모듈 단위로 나누어 구현한 뒤,
Git 브랜치와 Pull Request를 이용하여 통합했습니다.

---

## 18. 구현 현황

- [x] `main.py` / `src/cli.py` - CLI 파싱, 검증 및 대화형 모드
- [x] `src/collector.py` - CSV / Excel 읽기 및 컬럼 매핑
- [x] `src/cleaner.py` - 데이터 정제 및 `text_hash` 생성
- [x] `src/repository.py` - SQLite 스키마, 저장, 조회 및 마이그레이션
- [x] `src/ai_client.py` - AI API 호출 및 응답 처리
- [x] `src/analyzer.py` - 감정 분석 및 인사이트 추출
- [x] `src/visualizer.py` - matplotlib 기반 차트 생성
- [x] `src/reporter.py` - 대시보드 리포트 및 결과 내보내기

---

## 19. 통합 테스트 결과

다음 기능을 실제 CLI 환경에서 순차적으로 테스트했습니다.

| 테스트 | 결과 |
| --- | :---: |
| 36개 샘플 CSV 리뷰 가져오기 | ✅ |
| 리뷰 데이터 정제 | ✅ |
| `skip` 중복 처리 | ✅ |
| `upsert` 중복 데이터 갱신 | ✅ |
| SQLite 스키마 마이그레이션 | ✅ |
| 리뷰 목록 조회 및 페이지네이션 | ✅ |
| 감정 / 별점 / 날짜 필터 조회 | ✅ |
| 별점 기준 정렬 | ✅ |
| 리뷰 상세 조회 | ✅ |
| AI 감정 분석 (`--id`) | ✅ |
| 미분석 리뷰 AI 분석 (`--unanalyzed`) | ✅ |
| AI 인사이트 추출 | ✅ |
| 감정 / 상품 조건 인사이트 추출 | ✅ |
| 감정 분석 통계 및 평균 별점 | ✅ |
| 대시보드 및 TXT 리포트 생성 | ✅ |
| 감정 분포 차트 생성 | ✅ |
| 감정 추이 차트 생성 | ✅ |
| 별점-감정 매트릭스 생성 | ✅ |
| `visualization.dpi` 설정 적용 | ✅ |
| CSV 결과 내보내기 | ✅ |
| Excel 결과 내보내기 | ✅ |
| `--sentiment` / `--rating-min` 내보내기 필터 | ✅ |
| INFO / WARNING / ERROR 로그 기록 | ✅ |
| AI API 실패 시 오류 로그 및 해당 리뷰 건너뛰기 | ✅ |
| 분석 데이터가 없는 경우 처리 | ✅ |

### 최종 통합 테스트 흐름

```text
import
  ↓
clean
  ↓
analyze
  ↓
extract
  ↓
list / show / stats
  ↓
dashboard
  ↓
export
```

각 단계가 SQLite 데이터베이스를 중심으로 연결되며,
수집한 리뷰 데이터가 정제 → AI 분석 → 인사이트 추출 →
시각화 및 리포트 생성까지 이어지는 전체 흐름을 확인했습니다.

---

## 20. 보안 주의사항

- 실제 API 키는 `.env` 파일에만 저장합니다.
- `.env` 파일은 Git 저장소에 커밋하지 않습니다.
- API 키를 소스 코드나 README에 직접 작성하지 않습니다.
- 공유가 필요한 경우 `.env.example`을 사용합니다.