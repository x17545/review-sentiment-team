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
- 감정별 / 기간별 / 제품별 리뷰 분석
- 리뷰 및 감정 분석 통계 조회
- 제품/카테고리별 비교 분석
- 부정 감정 급증 알림
- matplotlib 기반 차트 생성
- 텍스트 대시보드 리포트 생성
- HTML 대시보드 생성
- CSV / JSONL / Excel 결과 내보내기
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
│   │   ├── .gitkeep
│   │   └── sample_reviews.csv
│   └── clean/
│       └── .gitkeep
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
    ├── reporter.py
    ├── comparison.py
    └── alert.py
```

실행 과정에서 다음 파일 및 폴더가 생성될 수 있습니다.

```text
data/reviews.db
logs/app.log
output/
├── dashboard/
│   ├── dashboard_report.txt
│   ├── dashboard.html
│   ├── sentiment_distribution.png
│   ├── sentiment_trend.png
│   └── rating_sentiment_matrix.png
└── export/
    ├── reviews_export.csv
    ├── reviews_export.jsonl
    └── reviews_export.xlsx
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
| `src/comparison.py` | 제품/카테고리별 비교 분석 |
| `src/alert.py` | 부정 감정 급증 알림 |

---

## 3. 개발 환경

- Python 3.10 이상
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
        ↓
제품별 비교 분석
        ↓
부정 감정 급증 알림 확인
```

### 1단계 - 리뷰 데이터 불러오기

```powershell
python main.py import --file data/raw/sample_reviews.csv --db data/reviews.db
```

### 2단계 - 리뷰 데이터 정제

```powershell
python main.py clean --db data/reviews.db
```

중복 처리 정책을 지정할 수도 있습니다.

```powershell
python main.py clean --db data/reviews.db --dedup-policy skip
python main.py clean --db data/reviews.db --dedup-policy upsert
```

### 3단계 - AI 감정 분석

```powershell
python main.py analyze --db data/reviews.db --unanalyzed
```

일부 리뷰만 분석하려면:

```powershell
python main.py analyze --db data/reviews.db --unanalyzed --limit 1
```

특정 리뷰만 분석하려면:

```powershell
python main.py analyze --db data/reviews.db --id 1
```

### 4단계 - AI 인사이트 추출

```powershell
python main.py extract --db data/reviews.db
```

특정 상품을 대상으로 추출하려면:

```powershell
python main.py extract --db data/reviews.db --product "텀블러"
```

### 5단계 - 통계 확인

```powershell
python main.py stats --db data/reviews.db
```

### 6단계 - 대시보드 생성

```powershell
python main.py dashboard --db data/reviews.db --output output/dashboard
```

```text
output/dashboard/
├── dashboard_report.txt
├── dashboard.html
├── sentiment_distribution.png
├── sentiment_trend.png
└── rating_sentiment_matrix.png
```

### 7단계 - 결과 내보내기

CSV:

```powershell
python main.py export --db data/reviews.db --format csv --output output/export
```

JSONL:

```powershell
python main.py export --db data/reviews.db --format jsonl --output output/export
```

Excel:

```powershell
python main.py export --db data/reviews.db --format excel --output output/export
```

필터링 예시:

```powershell
python main.py export --db data/reviews.db --format csv --sentiment positive --rating-min 4 --output output/export
```

### 8단계 - 제품별 비교 분석

특정 제품 비교:

```powershell
python main.py compare --db data/reviews.db --products "머그컵" "텀블러"
```

전체 제품 비교:

```powershell
python main.py compare --db data/reviews.db --all
```

### 9단계 - 부정 감정 급증 알림 확인

기본 실행:

```powershell
python main.py alert --db data/reviews.db
```

기간과 임계값 지정:

```powershell
python main.py alert --db data/reviews.db --days 7 --threshold 20
```

특정 제품만 확인:

```powershell
python main.py alert --db data/reviews.db --product "텀블러"
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
| `dashboard` | 차트, TXT 리포트, HTML 대시보드 생성 |
| `export` | 분석 결과를 CSV / JSONL / Excel 파일로 내보내기 |
| `compare` | 제품/카테고리별 리뷰 비교 분석 |
| `alert` | 부정 감정 급증 알림 확인 |

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

### Raw / Clean 데이터 분리 설계

본 프로젝트에서는 원본 리뷰 데이터와 정제 완료 데이터를 서로 다른 단계로 분리하여 관리합니다.

- **Raw 데이터**
  - CSV 또는 Excel에서 처음 수집한 원본 데이터를 최대한 그대로 보존합니다.
  - 정제 과정에서 오류가 발생하거나 정제 규칙을 변경해야 할 경우 원본 데이터를 기준으로 다시 처리할 수 있습니다.
  - 사용자가 제공한 데이터와 실제 분석에 사용된 데이터의 차이를 추적할 수 있도록 합니다.

- **Clean 데이터**
  - 리뷰 텍스트 정규화, 별점 범위 검사, 날짜 형식 통일, 최소 리뷰 길이 검사, 중복 처리 등 정제 과정을 통과한 데이터를 저장합니다.
  - 이후 AI 감정 분석, 통계, 시각화에서는 일관된 형식의 데이터를 사용할 수 있도록 합니다.

Raw와 Clean 데이터를 분리한 이유는 **원본 데이터의 무결성을 보존하면서 분석용 데이터의 품질과 일관성을 확보하기 위해서**입니다.

하나의 저장 단계에서 원본 데이터를 직접 수정할 경우 정제 오류나 규칙 변경이 발생했을 때 최초 데이터를 복구하거나 비교하기 어렵습니다. 반면 원본을 별도로 보존하면 정제 로직이 변경되더라도 Raw 데이터를 기준으로 Clean 데이터를 다시 생성할 수 있습니다.

비즈니스 관점에서도 분석 결과에 이상이 발생했을 때 원본 리뷰와 정제 데이터를 비교하여 문제가 데이터 입력 단계, 정제 단계, AI 분석 단계 중 어디에서 발생했는지 추적할 수 있습니다. 이를 통해 분석 결과의 재현성과 데이터 품질 관리가 쉬워집니다.

데이터 흐름은 다음과 같습니다.

```text
사용자 입력 CSV / Excel
        ↓
Raw 리뷰 저장
        ↓
유효성 검사 및 정규화
        ↓
Clean 리뷰 저장
        ↓
AI 감정 분석 / 인사이트 추출
        ↓
통계 / 대시보드 / 결과 내보내기
```


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
AI 인사이트를 텍스트 리포트, HTML 대시보드 및 차트로 생성합니다.

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

### 별점-감정 불일치에 대한 가설 및 추가 분석

본 프로젝트에서는 다음 두 경우를 별점과 감정 분석 결과가 불일치한 리뷰로 정의합니다.

- 별점이 4점 이상이지만 감정 분석 결과가 `negative`인 경우
- 별점이 2점 이하이지만 감정 분석 결과가 `positive`인 경우

괴리율은 다음과 같이 계산합니다.

```text
별점-감정 괴리율
= 별점과 감정이 불일치한 리뷰 수
  / 전체 분석 완료 리뷰 수
  × 100
```

별점과 리뷰 본문의 감정이 항상 동일하게 나타나는 것은 아니므로, 다음과 같은 원인 가설을 세울 수 있습니다.
1. 제품과 서비스 평가 대상의 차이
   - 사용자는 제품 자체에는 만족하여 높은 별점을 부여했지만 배송, 포장, 고객 응대 등에 대한 불만을 리뷰 본문에 작성할 수 있습니다.
   - 반대로 낮은 별점을 주었지만 특정 기능이나 디자인에 대해서는 긍정적인 표현을 사용할 수도 있습니다.
2. 복합 감정이 포함된 리뷰
   - 하나의 리뷰 안에 긍정과 부정 표현이 동시에 포함될 수 있습니다.
   - 예를 들어 "디자인은 마음에 들지만 배송이 너무 늦었습니다."와 같은 리뷰는 별점과 본문 감정의 대표값이 서로 다르게 나타날 수 있습니다.
3. 별점 입력 습관의 차이
   - 사용자마다 별점을 부여하는 기준이 다르기 때문에 동일한 만족도라도 서로 다른 별점을 사용할 수 있습니다.
   - 일부 사용자는 리뷰 본문의 강한 불만 표현과 달리 관대한 별점을 줄 수도 있습니다.
4. AI 감정 분석 오류 가능성
   - 반어법, 복합 문장, 짧은 표현 등은 AI가 리뷰 작성자의 실제 의도를 정확히 해석하기 어려운 경우가 있습니다.
   - 따라서 괴리율이 높을 경우 데이터뿐 아니라 AI 분석 품질도 함께 점검할 필요가 있습니다.

괴리 현상의 원인을 검증하기 위해 다음과 같은 추가 분석을 제안합니다.

- 괴리가 발생한 리뷰만 별도로 추출하여 수동 검수
- 배송, 품질, 가격, 디자인, 서비스 등 주제별 키워드 분석
- 제품별 괴리율 비교
- 기간별 괴리율 변화 추적
- 감정 분석 신뢰도 점수와 괴리 여부의 관계 확인
- 신뢰도가 낮은 괴리 리뷰를 우선적으로 재분석 또는 수동 검수 대상으로 선정

이를 통해 별점과 리뷰 본문 중 어느 한쪽만으로 고객 만족도를 판단하는 한계를 보완하고, 고객 불만의 실제 원인과 AI 분석 품질 문제를 구분하여 확인할 수 있습니다.

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
dashboard_report.txt: 텍스트 기반 대시보드 리포트
dashboard.html: 브라우저에서 확인할 수 있는 HTML 대시보드
sentiment_distribution.png: 감정 분포 차트
sentiment_trend.png: 기간별 감정 추이 차트
rating_sentiment_matrix.png: 별점-감정 매트릭스 차트
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

JSONL 예시:
```powershell
python main.py export --db data/reviews.db --format jsonl --output output/export
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
- [x] `src/reporter.py` - 대시보드 리포트, HTML 대시보드 및 결과 내보내기
- [x] `src/comparison.py` - 제품/카테고리별 비교 분석
- [x] `src/alert.py` - 부정 감정 급증 알림

---

## 19. 통합 테스트 결과

다음 기능을 실제 CLI 환경에서 순차적으로 테스트했습니다.

| 테스트 | 결과 |
| --- | :---: |
| 샘플 CSV 리뷰 가져오기 | ✅ |
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
| JSONL 결과 내보내기 | ✅ |
| HTML 대시보드 생성 | ✅ |
| HTML escaping 적용 | ✅ |
| 제품/카테고리별 비교 분석 | ✅ |
| 특정 제품 지정 비교 분석 | ✅ |
| 전체 제품 비교 분석 | ✅ |
| 부정 감정 급증 알림 | ✅ |
| 알림 기준 기간 및 임계값 옵션 | ✅ |
| 특정 제품 알림 필터 | ✅ |
| 대화형 모드 실행 | ✅ |


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
  ↓
compare
  ↓
alert
```

각 단계가 SQLite 데이터베이스를 중심으로 연결되며,
수집한 리뷰 데이터가 정제 → AI 분석 → 인사이트 추출 →
시각화 및 리포트 생성 → 결과 내보내기 → 제품별 비교 분석 →
부정 감정 급증 알림 확인까지 이어지는 전체 흐름을 확인했습니다.

---

## 20. 보안 주의사항

- 실제 API 키는 `.env` 파일에만 저장합니다.
- `.env` 파일은 Git 저장소에 커밋하지 않습니다.
- API 키를 소스 코드나 README에 직접 작성하지 않습니다.
- 공유가 필요한 경우 `.env.example`을 사용합니다.

---

## 21. 보너스 기능

### 21.1 다국어 감정 분석

기본 한국어 리뷰 감정 분석 기능을 확장하여 영어 리뷰도 감정 분석할 수 있도록 구현했습니다.

AI 감정 분석 프롬프트에서 한국어, 영어 및 두 언어가 혼합된 리뷰를 처리할 수 있도록 명시했으며,
입력 언어와 관계없이 기존과 동일한 형식으로 분석 결과를 반환합니다.

```text
sentiment: positive | neutral | negative
confidence: 0.0 ~ 1.0
```

따라서 기존 데이터베이스 구조와 CLI 분석 흐름을 변경하지 않고 다국어 리뷰를 처리할 수 있습니다.

#### 지원 및 테스트 범위

| 테스트 리뷰 | 분석 결과 | 신뢰도 | 결과 |
| --- | --- | ---: | :---: |
| 한국어 긍정 리뷰 | positive | 0.98 | ✅ |
| 영어 긍정 리뷰 | positive | 0.98 | ✅ |
| 영어 부정 리뷰 | negative | 0.98 | ✅ |
| 영어 중립 리뷰 | neutral | 0.95 | ✅ |
| 한국어 + 영어 혼합 리뷰 | positive | 0.95 | ✅ |

실제 AI API를 호출하여 위 테스트를 수행했으며,
기존 한국어 감정 분석 기능이 정상적으로 유지되는 것도 함께 확인했습니다.

예시 영어 리뷰:

```text
The product quality is excellent and I am very satisfied with my purchase.
```

분석 결과 예시:

```text
sentiment: positive
confidence: 0.98
```

다국어 리뷰 역시 기존과 동일하게 `analyze` 명령을 통해 분석할 수 있습니다.

```powershell
python main.py analyze --db data/reviews.db --unanalyzed
```

### 21.2 제품/카테고리별 비교 분석

단일 제품 리뷰 분석 기능을 확장하여 복수 제품 간의 리뷰 통계와 AI 감정 분석 결과를 비교할 수 있도록 구현했습니다.

데이터베이스에 저장된 제품별 리뷰 데이터를 집계하고 감정 분석 결과를 결합하여, 제품 간의 평점·감정 비율 및 핵심 키워드를 동일한 규격으로 요약·비교합니다.

```text
product_name
- metrics: total_reviews, avg_rating
- sentiment_ratio: positive | neutral | negative (%)
- ai_insights: keywords, summary
```

따라서 사용자는 개별 제품을 일일이 조회하지 않고 CLI 명령어를 통해 제품 간의 반응을 한눈에 비교할 수 있습니다.

#### 지원 및 테스트 범위

| 테스트 항목 | 비교 대상 | 분석 지표 | 결과 |
| --- | --- | --- | :---: |
| 특정 제품 비교 | 머그컵 vs 텀블러 | 리뷰 수, 평균 별점, 감정 비율, 요약 | ✅ |
| 전체 제품 비교 | DB 내 전체 등록 제품 | 제품별 종합 지표 비교 | ✅ |
| 감정 분석 반영 | 긍정·중립·부정 리뷰 | AI 감정 분석 결과의 제품별 비율 계산 | ✅ |
| 키워드 분석 | 다수 제품 리뷰 본문 | 리뷰 기반 주요 키워드 표시/추출 및 요약 생성 | ✅ |

실제 데이터베이스(`data/reviews.db`) 환경에서 위 테스트를 수행했으며,
기존 단일 제품 분석 및 DB 데이터 무결성이 정상적으로 유지되는 것도 함께 확인했습니다.

비교 분석 결과 출력 예시 (※ 아래 수치는 가상 데이터 예시입니다):

```text
[제품 비교 분석 결과] (가상 예시)
1. 머그컵
   - 총 리뷰 수: 120개 | 평균 별점: 4.6 / 5.0
   - 감정 비율: positive 85% | neutral 10% | negative 5%
   - 주요 키워드: 디자인, 내구성, 그립감
   - 요약: 디자인과 마감 품질에 대한 만족도가 높음

2. 텀블러
   - 총 리뷰 수: 95개 | 평균 별점: 4.2 / 5.0
   - 감정 비율: positive 70% | neutral 18% | negative 12%
   - 주요 키워드: 보온력, 휴대성, 세척
   - 요약: 보온 성능은 우수하나 뚜껑 세척 편의성에 대한 개선 요구 있음
```

제품 비교 분석은 `compare` 명령을 통해 특정 제품을 지정하거나 전체 제품을 대상으로 실행할 수 있습니다.

특정 제품 비교:

```powershell
python main.py compare --db data/reviews.db --products "머그컵" "텀블러"
```

전체 제품 비교:

```powershell
python main.py compare --db data/reviews.db --all
```


### 21.3 부정 감정 급증 알림

최근 리뷰에서 부정 감정 비율이 이전 기간보다 급격하게 증가했는지 확인할 수 있는 알림 기능을 구현했습니다.

기준 날짜를 중심으로 최근 N일과 그 직전 N일의 분석 완료 리뷰를 비교하여 각 기간의 부정 감정 비율을 계산합니다. 최근 기간의 부정 감정 비율 증가 폭이 설정한 임계값 이상이면 경고를 표시합니다.

```text
이전 기간 부정 비율
최근 기간 부정 비율
증가 폭 (%p)
설정 임계값 (%p)
판정 결과
```

두 기간 중 한쪽이라도 분석된 리뷰가 없으면 잘못된 급증 판정을 내리지 않고 `판정 보류`로 처리합니다. 또한 특정 제품만 지정하여 부정 감정 변화를 확인할 수도 있습니다.

#### 지원 및 테스트 범위

| 테스트 항목 | 내용 | 결과 |
| --- | --- | :---: |
| 기본 급증 분석 | 최근 기간과 이전 기간의 부정 감정 비율 비교 | ✅ |
| 임계값 판정 | 증가 폭이 설정한 임계값 이상일 때 경고 표시 | ✅ |
| 데이터 부족 처리 | 비교 기간에 분석 리뷰가 없으면 판정 보류 | ✅ |
| 특정 제품 필터 | 제품명을 지정하여 해당 제품만 분석 | ✅ |
| 입력값 검증 | 기간 및 임계값의 잘못된 입력 처리 | ✅ |

실제 데이터베이스(`data/reviews.db`)를 사용하여 정상 상태와 급증 경고 상황을 모두 테스트했습니다.

기본 실행:
```powershell
python main.py alert --db data/reviews.db
```

기간과 임계값 지정:
```powershell
python main.py alert --db data/reviews.db --days 7 --threshold 20
```

기준 날짜를 지정한 급증 경고 테스트:
```powershell
python main.py alert --db data/reviews.db --end-date 2026-09-02 --days 1 --threshold 20
```

특정 제품만 확인:
```powershell
python main.py alert --db data/reviews.db --product "텀블러"
```


### 21.4 HTML 대시보드

기존 콘솔/TXT 리포트 기능을 확장하여 리뷰 감정 분석 결과를 웹 브라우저에서 확인할 수 있는 HTML 대시보드를 구현했습니다.

기존 `dashboard` 명령을 실행하면 콘솔 리포트와 함께 HTML 파일 및 시각화 차트가 생성됩니다. HTML 대시보드는 주요 지표, 감정 분석 인사이트, 차트, 최근 리뷰 목록을 한 화면에서 확인할 수 있도록 구성했습니다.

#### 대시보드 주요 구성

- 전체 리뷰 수
- 평균 별점
- 긍정 리뷰 비율
- 부정 리뷰 비율
- 긍정/부정 주요 키워드
- AI 요약 및 개선 제안
- 감정 분포 차트
- 기간별 감정 추이 차트
- 별점과 감정 분포 차트
- 최근 리뷰 표
  - 날짜
  - 제품명
  - 별점
  - 감정
  - 리뷰 내용

차트 이미지는 Base64 형식으로 HTML 내부에 포함되어 별도의 이미지 경로 없이 하나의 HTML 파일로 확인할 수 있습니다.

최근 리뷰 표는 데이터베이스에서 직접 조회하며, 리뷰 문자열에는 HTML escaping을 적용하여 안전하게 표시하도록 구현했습니다.

#### 지원 및 테스트 범위

| 테스트 항목 | 내용 | 결과 |
| --- | --- | :---: |
| HTML 생성 | `dashboard.html` 정상 생성 | ✅ |
| 핵심 지표 표시 | 리뷰 수, 평균 별점, 감정 비율 표시 | ✅ |
| AI 인사이트 | 키워드, 요약, 개선 제안 표시 | ✅ |
| 시각화 차트 | 3종 차트 생성 및 HTML 표시 | ✅ |
| 최근 리뷰 표 | 날짜, 제품, 별점, 감정, 리뷰 내용 표시 | ✅ |
| HTML escaping | 특수문자 및 HTML 태그 문자열 안전 처리 | ✅ |
| 기존 기능 회귀 테스트 | compare, alert 기능 정상 동작 확인 | ✅ |

실제 데이터베이스(`data/reviews.db`)를 사용하여 HTML 파일 생성과 브라우저 표시를 확인했습니다.

대시보드 실행:
```powershell
python main.py dashboard --db data/reviews.db --output output/dashboard
```

실행 후 주요 결과물:
```text
output/dashboard/
├── dashboard.html
├── dashboard_report.txt
├── sentiment_distribution.png
├── sentiment_trend.png
└── rating_sentiment_matrix.png
```

HTML 대시보드는 기존 `dashboard` 명령에 통합되어 있으므로 별도의 `html-dashboard` 명령은 사용하지 않습니다.
