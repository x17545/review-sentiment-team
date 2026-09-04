# review-sentiment

AI 기반 고객 리뷰 감정 분석 대시보드 (Project C)

## 실행 방법

```
python main.py                       # 대화형 모드 (질문에 답만)
python main.py list --sentiment 긍정  # 일반 CLI
python main.py --help
```

공통 옵션(--db / --config / --verbose)은 서브커맨드 '뒤'에 씁니다.
  가능:   python main.py list --db data/reviews.db
  불가능: python main.py --db data/reviews.db list

## 초기 세팅

1. `pip install -r requirements.txt`
2. `cp .env.example .env` 후 .env 에 API 키 입력
3. `python main.py stats` 로 동작 확인 (DB 자동 생성)

## 수동 테스트 명령

```
python main.py import --file data/sample_reviews.csv
python main.py clean
python main.py analyze --unanalyzed --limit 5
python main.py stats
python main.py dashboard
python main.py export --format csv
```

## 데이터 편향 안내

분석 결과는 입력 리뷰 데이터의 품질과 분포에 영향을 받습니다.
리뷰 수가 적거나 특정 상품/기간/감정에 편향된 경우, 감정 비율·키워드·요약
결과가 실제 고객 전체 의견을 대표하지 않을 수 있습니다.

## 구현 현황

- [x] main.py / src/cli.py  (파싱·검증·정규화·대화형)
- [x] src/repository.py      (SQLite 스키마·저장·조회)
- [ ] src/collector.py       (CSV/Excel 읽기 + 컬럼 매핑)
- [ ] src/cleaner.py         (정제 + text_hash)
- [ ] src/ai_client.py       (AI 호출 + 응답 정규화)
- [ ] src/analyzer.py        (분석 흐름 제어)
- [ ] src/visualizer.py      (matplotlib 차트)
- [ ] src/reporter.py        (리포트 + 내보내기)
