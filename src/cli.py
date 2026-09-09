# src/cli.py
"""
Project C - AI 기반 고객 리뷰 감정 분석 대시보드
CLI 진입 계층.

역할:
- argparse 서브커맨드 정의 (import/clean/analyze/extract/list/show/stats/dashboard/export)
- 입력값 검증 및 정규화 (같은 의미의 값은 하나로 통일)
- 키보드 인터럽트(Ctrl+C) / EOF(Ctrl+D) 안전 처리

주의:
- 이 파일은 '파싱과 검증'까지만 담당합니다.
- 실제 로직(수집/정제/분석/시각화)은 각 모듈 함수를 호출하도록 핸들러에서 연결합니다.
- DB 초기화(init_db)는 main()에서 한 번만 수행합니다. 핸들러는 DB가 준비됐다고 가정합니다.
- 진단 메시지(경고/오류)는 stdout이 아니라 stderr로 출력합니다.

실행 방법:
- 정식 실행은 프로젝트 루트의 main.py를 사용합니다.
      python main.py import --file data/sample_reviews.csv
- 이 파일 단독 실행도 테스트용으로 가능합니다.
      python src/cli.py list --sentiment 긍정
"""

import sys
import json
import sqlite3
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable, Any


DEFAULT_DB_PATH = "data/reviews.db"
DEFAULT_CONFIG_PATH = "config.json"
DEFAULT_OUTPUT_DIR = "output"

MAX_PAGE_SIZE = 100                      # --size 상한
VALID_DEDUP_POLICIES = ("skip", "upsert")   # 지원 중복 정책

LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 예외 / 진단 출력
# ---------------------------------------------------------------------------
class UserAbort(Exception):
    """사용자가 Ctrl+C / Ctrl+D 등으로 입력을 중단했을 때 사용."""


def eprint(*args: Any) -> None:
    """진단 메시지는 stderr로. (stdout은 데이터 출력 전용으로 비워둠)"""
    print(*args, file=sys.stderr)


# ---------------------------------------------------------------------------
# 설정 로딩 (최소 구현; 이후 config.py로 옮겨도 됨)
# ---------------------------------------------------------------------------
def load_config(path: str = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """
    config.json을 읽어 dict로 반환합니다.
    파일이 없으면 빈 설정으로 진행하되 경고만 출력합니다(실행 자체는 막지 않음).
    """
    p = Path(path)
    if not p.is_file():
        eprint(f"[경고] 설정 파일이 없습니다: {path} (기본값으로 진행)")
        return {}
    try:
        with p.open(encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise SystemExit(f"[오류] config.json 형식이 잘못되었습니다: {e}")


# ---------------------------------------------------------------------------
# 값 검증 / 변환 함수
#   argparse의 type= 에 넣으면, 잘못된 입력은 파싱 단계에서 걸러집니다.
#   같은 함수를 대화형 입력(prompt_until)에서도 재사용해 검증 규칙을 하나로 유지합니다.
# ---------------------------------------------------------------------------
def positive_int(value: str) -> int:
    """1 이상의 정수. --limit, --page 등에 사용."""
    try:
        n = int(value.strip())
    except ValueError:
        raise argparse.ArgumentTypeError(f"정수를 입력해야 합니다: {value!r}")
    if n < 1:
        raise argparse.ArgumentTypeError(f"1 이상이어야 합니다: {n}")
    return n


def bounded_int(low: int, high: int, field_name: str) -> Callable[[str], int]:
    """low~high 범위의 정수만 허용하는 타입 함수를 생성. --size 등에 사용."""
    def _convert(value: str) -> int:
        try:
            n = int(value.strip())
        except ValueError:
            raise argparse.ArgumentTypeError(f"{field_name}은(는) 정수여야 합니다: {value!r}")
        if not low <= n <= high:
            raise argparse.ArgumentTypeError(
                f"{field_name}은(는) {low}~{high} 범위여야 합니다: {n}"
            )
        return n
    return _convert


# --size: 1~MAX_PAGE_SIZE 로 제한 (과도한 출력 방지)
page_size_int = bounded_int(1, MAX_PAGE_SIZE, "페이지 크기(--size)")


def rating_int(value: str) -> int:
    """
    별점 정수 (1~5). --rating, --rating-min 양쪽에 사용.

    isdigit()을 쓰지 않는 이유:
    - '4.5'.isdigit() 는 False라 소수점은 걸러지지만,
      '²' 이나 아라비아 숫자('٤') 같은 유니코드 숫자에도 True를 돌려줘서
      뒤이은 int() 변환이 예외를 낼 수 있습니다(변환 성공을 보장 못 함).
    - 그래서 isdigit 대신 int() try/except로 '변환 가능 여부'를 직접 확인합니다.
    - int('4.5')는 ValueError를 내므로 소수점 별점은 자연히 거부됩니다(예: 4.5 불가).
    """
    text = value.strip()
    try:
        n = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"별점은 소수점 없는 정수여야 합니다: {value!r} "
            f"(예: '4.5'는 불가, '4'만 가능)"
        )
    if not 1 <= n <= 5:
        raise argparse.ArgumentTypeError(f"별점은 1~5 범위여야 합니다: {n}")
    return n


def date_str(value: str) -> str:
    """
    날짜를 YYYY-MM-DD 표준형으로 정규화합니다.
    입력이 20240108, 2024/01/08 이어도 모두 2024-01-08로 통일합니다.
    """
    text = value.strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(f"날짜 형식은 YYYY-MM-DD 여야 합니다: {value!r}")


def existing_review_file(value: str) -> str:
    """--file 인자용. 실제 존재하는 CSV/Excel 파일인지 확인합니다."""
    p = Path(value.strip())
    if not p.is_file():
        raise argparse.ArgumentTypeError(f"파일을 찾을 수 없습니다: {value}")
    if p.suffix.lower() not in (".csv", ".xlsx", ".xls"):
        raise argparse.ArgumentTypeError(
            f"CSV 또는 Excel 파일만 지원합니다: {value} (확장자: {p.suffix})"
        )
    return str(p)


def make_choice_normalizer(
    canonical_map: dict[str, list[str]],
    field_name: str,
) -> Callable[[str], str]:
    """
    '같은 의미의 여러 표기'를 하나의 표준값으로 모으는 정규화 함수를 만듭니다.

    예) 감정:  "긍정", "positive", "POSITIVE", "pos" -> 모두 "positive"
    예) 장르:  "sf", "SF", "에스에프", "science fiction" -> 모두 "sf"

    canonical_map = { 표준값: [동의어, ...] } 형태로 넘기면,
    대소문자/앞뒤공백을 무시하고 매칭합니다.
    """
    lookup: dict[str, str] = {}
    for canonical, synonyms in canonical_map.items():
        lookup[canonical.strip().lower()] = canonical
        for s in synonyms:
            lookup[s.strip().lower()] = canonical

    def _normalize(value: str) -> str:
        key = value.strip().lower()
        if key not in lookup:
            allowed = ", ".join(sorted(canonical_map.keys()))
            raise argparse.ArgumentTypeError(
                f"{field_name} 값이 올바르지 않습니다: {value!r} (허용: {allowed})"
            )
        return lookup[key]

    return _normalize


# 감정 필터: 어떻게 입력하든 내부값은 positive/negative/neutral/unknown 으로 통일
normalize_sentiment = make_choice_normalizer(
    {
        "positive": ["긍정", "pos", "p", "+"],
        "negative": ["부정", "neg", "n", "-"],
        "neutral": ["중립", "neu", "0"],
        "unknown": ["알수없음", "알 수 없음", "미상", "unk"],
    },
    field_name="감정(--sentiment)",
)

normalize_format = make_choice_normalizer(
    {
        "csv": [],
        "jsonl": ["json", "ndjson", "jsonlines"],
        "excel": ["xlsx", "xls", "엑셀"],
    },
    field_name="형식(--format)",
)

normalize_sort = make_choice_normalizer(
    {
        "date_desc": ["date", "recent", "newest", "최신"],
        "date_asc": ["oldest", "오래된"],
        "rating_desc": ["rating", "star", "별점", "high"],
        "rating_asc": ["low"],
        "id_asc": ["id"],
    },
    field_name="정렬(--sort)",
)


def validate_date_range(date_from: Optional[str], date_to: Optional[str]) -> None:
    """시작일이 종료일보다 늦으면 오류. (YYYY-MM-DD 문자열 비교로 순서 판정)"""
    if date_from and date_to and date_from > date_to:
        raise SystemExit(
            f"[오류] 시작일은 종료일보다 늦을 수 없습니다: {date_from} > {date_to}"
        )


# ---------------------------------------------------------------------------
# 대화형 입력 (Ctrl+C / Ctrl+D 안전 처리)
# ---------------------------------------------------------------------------
def safe_input(prompt: str) -> str:
    """input()을 감싸 Ctrl+D(EOFError)/Ctrl+C(KeyboardInterrupt)를 UserAbort로 변환."""
    try:
        return input(prompt)
    except EOFError:
        raise UserAbort("입력이 종료되었습니다 (Ctrl+D)")
    except KeyboardInterrupt:
        raise UserAbort("사용자가 취소했습니다 (Ctrl+C)")


def prompt_until(
    prompt: str,
    convert: Callable[[str], Any],
    allow_empty: bool = False,
    default: Any = None,
) -> Any:
    """유효한 값이 들어올 때까지 반복 입력. convert는 위 검증 함수를 재사용."""
    while True:
        raw = safe_input(prompt).strip()
        if not raw:
            if allow_empty:
                return default
            eprint("  값을 입력해 주세요.")
            continue
        try:
            return convert(raw)
        except (ValueError, argparse.ArgumentTypeError) as e:
            eprint(f"  입력 오류: {e}")


# ---------------------------------------------------------------------------
# 중복 정책 결정 헬퍼
#   우선순위: CLI > config > 기본값("skip")
#   CLI든 config든, 최종값이 지원 목록(VALID_DEDUP_POLICIES)에 없으면 여기서 차단.
#   'or'가 아니라 'is None' 검사를 쓰는 이유:
#     or는 falsy(빈문자열/0/False)를 전부 '없음'으로 취급해,
#     향후 0·False 옵션에서 사용자 지정이 무시되는 버그를 냅니다.
# ---------------------------------------------------------------------------
def resolve_dedup_policy(args: argparse.Namespace, config: dict[str, Any]) -> str:
    policy = args.dedup_policy
    source = "CLI"
    if policy is None:
        policy = config.get("cleaning", {}).get("duplicate_policy", "skip")
        source = "config/기본값"
    if policy not in VALID_DEDUP_POLICIES:
        allowed = ", ".join(VALID_DEDUP_POLICIES)
        raise SystemExit(
            f"[오류] 지원하지 않는 중복 정책: {policy!r} (출처: {source}, 허용: {allowed})"
        )
    return policy


# ---------------------------------------------------------------------------
# DB 초기화
#   repository.py가 아직 없을 때만(스텁 단계) 관대하게 넘어갑니다.
#   그 외 import 오류(오타 등)는 그대로 드러내 디버깅을 돕습니다.
# ---------------------------------------------------------------------------
def initialize_database(db_path: str, verbose: bool = False) -> None:
    # src.repository '자체'가 없을 때만 스텁으로 넘어간다.
    # repository.py 내부의 다른 import 실패(진짜 버그)는 그대로 드러낸다.
    try:
        from src.repository import init_db
    except ModuleNotFoundError as e:
        if e.name != "src.repository":
            raise                                    # 내부 import 오류는 숨기지 않음
        if verbose:
            eprint("[경고] src.repository 미연결 (스텁 단계로 진행)")
        return
    init_db(db_path)


# ---------------------------------------------------------------------------
# 명령별 핸들러 (지금은 파싱 결과 출력 스텁)
#   DB 초기화는 main()에서 끝났다고 가정합니다.
# ---------------------------------------------------------------------------
def cmd_import(args: argparse.Namespace, config: dict[str, Any]) -> None:
    file_path = args.file

    if file_path is None:
        file_path = prompt_until(
            "리뷰 파일 경로(CSV/Excel): ",
            existing_review_file,
        )

    print(f"[import] db={args.db}, file={file_path}")

    from src.collector import read_reviews
    from src.repository import get_connection, insert_raw_review_row

    rows = read_reviews(file_path, config)

    inserted = 0

    with get_connection(args.db) as conn:
        for row in rows:
            insert_raw_review_row(conn, row)
            inserted += 1

    print(f"가져오기 완료: {inserted}건 저장")


def cmd_clean(args: argparse.Namespace, config: dict[str, Any]) -> None:
    dedup_policy = resolve_dedup_policy(args, config)

    print(
        f"[clean] db={args.db}, "
        f"dedup_policy={dedup_policy}"
    )

    from src import cleaner

    result = cleaner.run(
        db_path=args.db,
        config=config,
        dedup_policy=dedup_policy,
    )

    print(
        f"정제 완료: "
        f"처리 {result['processed']}건, "
        f"저장 {result['inserted']}건, "
        f"갱신 {result['updated']}건, "
        f"제외 {result['skipped']}건"
    )


def cmd_analyze(args: argparse.Namespace, config: dict[str, Any]) -> None:
    if args.id is not None and args.limit is not None:
        raise SystemExit("[오류] --id와 --limit은 함께 사용할 수 없습니다.")
    if args.id is not None:
        target = f"id={args.id}"
    elif args.all:
        target = "all"
    else:
        target = "unanalyzed"
    print(f"[analyze] db={args.db}, target={target}, limit={args.limit}")
    from src.analyzer import analyze_reviews_from_db

    ai_config = config.get("ai", {})

    model_name = ai_config.get("model")
    if not model_name:
        raise SystemExit("[오류] config.json의 ai.model 설정이 필요합니다.")

    prompt_version = ai_config.get("prompt_version", "v1")

    results = analyze_reviews_from_db(
        db_path=args.db,
        model_name=model_name,
        api_key_env=ai_config["api_key_env"],
        base_url=ai_config["base_url"],
        timeout=ai_config["timeout"],
        retry=ai_config["retry"],
        prompt_version=prompt_version,
        review_id=args.id,
        analyze_all=args.all,
        limit=args.limit,
    )

    if not results:
        print("분석할 리뷰가 없습니다.")
        return

    success_count = sum(
        1 for result in results
        if result.get("status") == "success"
    )
    failed_count = len(results) - success_count

    for result in results:
        if result.get("status") == "failed":
            logger.error(
                "AI 분석 실패: review_id=%s, error=%s",
                result.get("review_id", "unknown"),
                result.get("error", "알 수 없는 오류"),
            )

    inserted_count = sum(
        1 for result in results
        if result.get("inserted") is True
    )
    updated_count = sum(
        1 for result in results
        if result.get("updated") is True
    )

    print(
        f"분석 완료: 처리 {len(results)}건, "
        f"성공 {success_count}건, 실패 {failed_count}건, "
        f"신규 저장 {inserted_count}건, 갱신 {updated_count}건"
    ) 


def cmd_extract(args: argparse.Namespace, config: dict[str, Any]) -> None:
    validate_date_range(args.date_from, args.date_to)
    print(
        f"[extract] db={args.db}, sentiment={args.sentiment}, product={args.product}, "
        f"date_from={args.date_from}, date_to={args.date_to}, limit={args.limit}"
    )
    from src.analyzer import extract_insights_from_db

    ai_config = config.get("ai", {})

    model_name = ai_config.get("model")
    if not model_name:
        raise SystemExit("[오류] config.json의 ai.model 설정이 필요합니다.")

    prompt_version = ai_config.get("prompt_version", "v1")

    result = extract_insights_from_db(
        db_path=args.db,
        model_name=model_name,
        api_key_env=ai_config["api_key_env"],
        base_url=ai_config["base_url"],
        timeout=ai_config["timeout"],
        retry=ai_config["retry"],
        prompt_version=prompt_version,
        sentiment=args.sentiment,
        product=args.product,
        date_from=args.date_from,
        date_to=args.date_to,
        limit=args.limit,
    )

    if result.get("status") != "success":
        if result.get("error") == "no_reviews":
            print("추출할 리뷰가 없습니다.")
        else:
            print(f"추출 실패: {result.get('error', '알 수 없는 오류')}")
        return

    print(f"추출 완료: 리뷰 {result['review_count']}건")
    print(f"긍정 키워드: {', '.join(result['positive_keywords'])}")
    print(f"부정 키워드: {', '.join(result['negative_keywords'])}")
    print(f"요약: {result['summary']}")
    print(f"개선 제안: {', '.join(result['suggestions'])}")
    print(f"DB 저장 ID: {result['extraction_id']}")


def cmd_list(args: argparse.Namespace, config: dict[str, Any]) -> None:
    validate_date_range(args.date_from, args.date_to)
    from src.repository import get_connection, list_reviews

    # [치명 수정] 감정 필터 유무와 무관하게 model_name을 항상 고정한다.
    #   그래야 LEFT JOIN이 한 리뷰당 한 모델 결과만 붙여 중복이 없다.
    model_name = config.get("ai", {}).get("model")
    if not model_name:
        raise SystemExit("[오류] config.json의 ai.model 설정이 필요합니다.")
    prompt_version = config.get("ai", {}).get("prompt_version", "v1")

    with get_connection(args.db) as conn:
        result = list_reviews(
            conn,
            sentiment=args.sentiment,
            rating=args.rating,
            date_from=args.date_from,
            date_to=args.date_to,
            model_name=model_name,
            prompt_version=prompt_version,
            sort=args.sort,
            page=args.page,
            size=args.size,
        )

    rows = result["rows"]
    print(f"=== 리뷰 목록 ({result['page']}/{result['total_pages']} 페이지, "
          f"총 {result['total']}건) ===")
    if not rows:
        logger.warning(
        "조건에 맞는 리뷰가 없습니다: sentiment=%s, rating=%s, date_from=%s, date_to=%s",
        args.sentiment,
        args.rating,
        args.date_from,
        args.date_to,
        )
        print("(조건에 맞는 리뷰가 없습니다)")
        return
    for r in rows:
        sentiment = r["sentiment"] or "-"
        rating = f"{r['rating']:.0f}" if r["rating"] is not None else "-"
        text = (r["cleaned_text"] or "")[:30]
        print(f"[{r['id']}] ★{rating} | {r['review_date'] or '-'} | "
              f"{text} | {sentiment}")


def cmd_show(args: argparse.Namespace, config: dict[str, Any]) -> None:
    from src.repository import get_connection, get_review_by_id

    model_name = config.get("ai", {}).get("model")
    prompt_version = config.get("ai", {}).get("prompt_version", "v1")

    with get_connection(args.db) as conn:
        row = get_review_by_id(conn, args.id,
                               model_name=model_name, prompt_version=prompt_version)

    if row is None:
        print(f"id={args.id} 리뷰를 찾을 수 없습니다.")
        return

    print(f"=== 리뷰 상세 (id={row['id']}) ===")
    print(f"정제문    : {row['cleaned_text']}")
    print(f"별점      : {row['rating'] if row['rating'] is not None else '-'}")
    print(f"작성일    : {row['review_date'] or '-'}")
    print(f"제품명    : {row['product_name'] or '-'}")
    print(f"출처파일  : {row['source_file'] or '-'}")
    print(f"감정      : {row['sentiment'] or '(미분석)'}", end="")
    if row["sentiment"] is not None:
        # [치명 수정] sentiment는 있는데 confidence가 NULL이면 :.2f에서 예외.
        conf = f"{row['confidence']:.2f}" if row["confidence"] is not None else "-"
        print(f" (신뢰도 {conf}, 모델 {row['model_name']})")
    else:
        print()


def cmd_stats(args: argparse.Namespace, config: dict[str, Any]) -> None:
    # [권장] --product는 아직 미구현이라 사용 시 명확히 차단
    if getattr(args, "product", None):
        logger.error("지원하지 않는 옵션 사용: stats --product=%s", args.product)
        raise SystemExit("[오류] stats --product는 아직 지원하지 않습니다.")

    from src.repository import get_connection, get_review_count, get_sentiment_stats

    model_name = config.get("ai", {}).get("model", "")
    prompt_version = config.get("ai", {}).get("prompt_version", "v1")

    with get_connection(args.db) as conn:
        counts = get_review_count(conn)
        sentiments = get_sentiment_stats(
            conn,
            model_name=model_name,
            prompt_version=prompt_version,
        )
        avg_rating_row = conn.execute(
            "SELECT AVG(rating) AS avg_rating FROM clean_reviews "
            "WHERE rating IS NOT NULL"
        ).fetchone()
        avg_rating = (
            float(avg_rating_row["avg_rating"])
            if avg_rating_row["avg_rating"] is not None
            else 0.0
        )

    print("=== 리뷰 분석 통계 ===")
    print(f"원본(raw)   : {counts['raw_reviews']}건")
    print(f"정제(clean) : {counts['clean_reviews']}건")
    print(f"분석 완료   : {counts['analysis_results']}건")
    print(f"추출 결과   : {counts['extraction_results']}건")
    print(f"평균 별점   : {avg_rating:.2f}점")

    # [치명 수정] 비율 분모는 전체 analysis_results가 아니라 '이 모델'의 감정 합계.
    #   전체로 나누면 다른 모델 결과가 섞여 비율이 틀린다.
    model_analyzed = sum(int(s["count"]) for s in sentiments)
    print(f"\n[감정 분포] (모델: {model_name or '미지정'})")
    if model_analyzed == 0:
        print("- (분석 데이터 없음)")
    else:
        for s in sentiments:
            ratio = s["count"] / model_analyzed * 100
            print(f"- {s['sentiment']}: {s['count']}건 ({ratio:.1f}%)")


def cmd_dashboard(args: argparse.Namespace, config: dict[str, Any]) -> None:
    from src.visualizer import build_charts
    from src.reporter import build_report


    visualization_config = config.get("visualization", {})
    dpi = visualization_config.get("dpi", 300)
    # 1) 차트 생성 (데이터 없으면 build_charts가 빈 리스트 반환)
    chart_paths = build_charts(
        args.db,
        output_dir=args.output,
        dpi=dpi,
    )
    # 2) 차트 경로를 넘겨 종합 리포트 생성
    report_path = build_report(args.db, output_dir=args.output,
                               chart_paths=chart_paths)
    print(f"\n리포트 저장: {report_path}")
    if chart_paths:
        print("차트 저장:")
        for p in chart_paths:
            print(f"  - {p}")


def cmd_export(args: argparse.Namespace, config: dict[str, Any]) -> None:
    from src.reporter import export

    export_path = export(
        db_path=args.db,
        format=args.format,
        sentiment=args.sentiment,
        rating_min=args.rating_min,
        output=args.output,
    )
    print(f"\n내보내기 저장: {export_path}")


def cmd_alert(args: argparse.Namespace, config: dict[str, Any]) -> None:
    from datetime import date
    from src.repository import get_connection
    from src.alert import detect_negative_surge

    if args.end_date:
        try:
            end_date = date.fromisoformat(args.end_date)
        except ValueError as exc:
            raise SystemExit("[오류] --end-date는 YYYY-MM-DD 형식이어야 합니다.") from exc
    else:
        end_date = date.today()

    with get_connection(args.db) as conn:
        result = detect_negative_surge(
            conn=conn,
            end_date=end_date,
            days=args.days,
            threshold=args.threshold,
            product_name=args.product,
        )

    target = args.product or "전체 제품"
    previous = result["previous"]
    recent = result["recent"]

    print("=" * 56)
    print("           🚨 부정 감정 급증 감지 결과")
    print("=" * 56)
    print(f"대상: {target}")
    print(
        f"직전 기간: {result['previous_start']} ~ {result['previous_end']} "
        f"| 부정 {previous['negative']} / 분석 {previous['total']} "
        f"({previous['negative_ratio']:.1f}%)"
    )
    print(
        f"최근 기간: {result['recent_start']} ~ {result['recent_end']} "
        f"| 부정 {recent['negative']} / 분석 {recent['total']} "
        f"({recent['negative_ratio']:.1f}%)"
    )
    print(f"부정률 증가폭: {result['increase']:+.1f}%p")
    print(f"경고 기준: {result['threshold']:.1f}%p")

    if not result["has_enough_data"]:
        print("ℹ 판정 보류: 두 비교 기간 모두 분석된 리뷰가 있어야 합니다.")
    elif result["is_surge"]:
        print("⚠ 경고: 부정 감정이 기준 이상 급증했습니다.")
    else:
        print("✅ 정상: 부정 감정 급증이 감지되지 않았습니다.")

    print("=" * 56)    


# ---------------------------------------------------------------------------
# 파서 구성
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="review-sentiment",
        description="AI 기반 고객 리뷰 감정 분석 대시보드",
    )

    # 모든 서브커맨드가 공유하는 '공통 옵션'.
    # 주의: 이 옵션들은 서브커맨드 '뒤'에 작성해야 합니다.
    #   가능:   python main.py list --db data/reviews.db
    #   불가능: python main.py --db data/reviews.db list
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite 경로")
    parent.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="설정 파일 경로")
    parent.add_argument("--verbose", action="store_true", help="상세 로그 출력")

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    # import
    p = sub.add_parser("import", parents=[parent], help="CSV/Excel 리뷰 가져오기")
    p.add_argument("--file", type=existing_review_file,
                   help="리뷰 파일 경로 (생략 시 대화형 입력)")
    p.set_defaults(func=cmd_import)

    # clean
    p = sub.add_parser("clean", parents=[parent], help="raw -> clean 정제")
    p.add_argument("--dedup-policy", choices=["skip", "upsert"], default=None,
                   help="중복 처리 정책 (미지정 시 config 값)")
    p.set_defaults(func=cmd_clean)

    # analyze
    p = sub.add_parser("analyze", parents=[parent], help="감정 분석")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--all", action="store_true", help="전체 재분석")
    g.add_argument("--unanalyzed", action="store_true", help="미분석만 (기본)")
    g.add_argument("--id", type=positive_int, help="특정 리뷰 id")
    p.add_argument("--limit", type=positive_int, help="최대 처리 건수 (--id와 병용 불가)")
    p.set_defaults(func=cmd_analyze)

    # extract
    p = sub.add_parser("extract", parents=[parent], help="키워드/요약 추출")
    p.add_argument("--sentiment", type=normalize_sentiment)
    p.add_argument("--product")
    p.add_argument("--date-from", type=date_str, dest="date_from")
    p.add_argument("--date-to", type=date_str, dest="date_to")
    p.add_argument("--limit", type=positive_int)
    p.set_defaults(func=cmd_extract)

    # list
    p = sub.add_parser("list", parents=[parent], help="리뷰 목록 조회")
    p.add_argument("--sentiment", type=normalize_sentiment)
    p.add_argument("--rating", type=rating_int, help="별점(1~5 정수)")
    p.add_argument("--date-from", type=date_str, dest="date_from")
    p.add_argument("--date-to", type=date_str, dest="date_to")
    p.add_argument("--page", type=positive_int, default=1)
    p.add_argument("--size", type=page_size_int, default=20,
                   help=f"페이지 크기 (1~{MAX_PAGE_SIZE})")
    p.add_argument("--sort", type=normalize_sort, default="date_desc")
    p.set_defaults(func=cmd_list)

    # show
    p = sub.add_parser("show", parents=[parent], help="리뷰 상세 조회")
    p.add_argument("id", type=positive_int, help="리뷰 id (위치 인자)")
    p.set_defaults(func=cmd_show)

    # stats
    p = sub.add_parser("stats", parents=[parent], help="통계 요약")
    p.add_argument("--product", help="특정 제품으로 한정")
    p.set_defaults(func=cmd_stats)

    # dashboard
    p = sub.add_parser("dashboard", parents=[parent], help="차트+리포트 생성")
    p.add_argument("--output", default=DEFAULT_OUTPUT_DIR, help="출력 폴더")
    p.set_defaults(func=cmd_dashboard)

    # export
    p = sub.add_parser("export", parents=[parent], help="데이터 내보내기")
    p.add_argument("--format", type=normalize_format, required=True,
                   help="csv / jsonl / excel (xlsx·엑셀 등 표기 허용)")
    p.add_argument("--sentiment", type=normalize_sentiment)
    p.add_argument("--rating-min", type=rating_int, dest="rating_min")
    p.add_argument("--output", default=DEFAULT_OUTPUT_DIR, help="출력 폴더")
    p.set_defaults(func=cmd_export)

    # alert (Bonus Feature)
    p = sub.add_parser(
        "alert",
        parents=[parent],
        help="부정 감정 급증 감지",
    )
    p.add_argument(
        "--days",
        type=int,
        default=7,
        help="비교할 기간 길이 (기본: 7일)",
    )
    p.add_argument(
        "--threshold",
        type=float,
        default=20.0,
        help="급증 판정 기준 (%%p, 기본: 20)",
    )
    p.add_argument(
        "--end-date",
        help="최근 기간의 기준 종료일 (YYYY-MM-DD, 기본: 오늘)",
    )
    p.add_argument(
        "--product",
        help="특정 제품만 분석",
    )
    p.set_defaults(func=cmd_alert)

    return parser


# ---------------------------------------------------------------------------
# 대화형 모드 (B안: 질문에 답만 하면 명령을 대신 조립)
#   원리: 사용자 답변을 argv 리스트로 조립한 뒤, 그대로 main(argv)에 넘긴다.
#         파싱·검증·정규화는 기존 build_parser()가 100% 담당하므로 규칙이 한 벌뿐.
# ---------------------------------------------------------------------------
def add_option(argv: list[str], flag: str, value: Optional[str]) -> None:
    """값이 있으면 argv에 [flag, value]를 추가. 빈 값(엔터)이면 무시 = 필터 없음."""
    if value:
        argv += [flag, value]


def ask(prompt: str) -> str:
    """대화형 질문 한 줄. 엔터만 치면 빈 문자열(=건너뛰기)."""
    return safe_input(prompt).strip()


def add_sentiment(argv: list[str], prompt: str) -> None:
    """감정 입력을 즉시 정규화·검증해 argv에 추가. 빈 입력이면 건너뜀."""
    value = ask(prompt)
    if value:
        add_option(argv, "--sentiment", prompt_until_value(value, normalize_sentiment))


def add_date(argv: list[str], flag: str, prompt: str) -> None:
    """날짜 입력을 즉시 형식 검증해 argv에 추가. 빈 입력이면 건너뜀."""
    value = ask(prompt)
    if value:
        add_option(argv, flag, prompt_until_value(value, date_str))


# 명령 번호 → 명령 이름
INTERACTIVE_COMMANDS = [
    "import", "clean", "analyze", "extract",
    "list", "show", "stats", "dashboard", "export",
]


def choose_command() -> str:
    """명령을 번호나 이름으로 고르게 한다."""
    menu = "  ".join(f"[{i}]{name}" for i, name in enumerate(INTERACTIVE_COMMANDS, 1))
    while True:
        eprint("\n무엇을 할까요?")
        eprint("  " + menu)
        raw = ask("번호 또는 명령 이름 (q=종료): ").lower()
        if raw in ("q", "quit", "exit"):
            raise UserAbort("사용자 종료")
        if raw in INTERACTIVE_COMMANDS:              # 이름으로 입력
            return raw
        if raw.isdigit() and 1 <= int(raw) <= len(INTERACTIVE_COMMANDS):
            return INTERACTIVE_COMMANDS[int(raw) - 1]  # 번호로 입력
        eprint("  올바른 번호나 명령 이름을 입력하세요.")


def build_argv_for(command: str) -> list[str]:
    """
    선택된 명령에 맞춰 필요한 질문만 던지고 argv를 조립한다.
    - 형식이 까다로운 값(별점 등)은 입력 즉시 prompt_until로 검증
    - 정규화가 필요한 값(감정/정렬/형식)은 그대로 넣고 최종 파싱이 처리
    """
    argv: list[str] = [command]

    if command == "import":
        # 파일 경로는 필수라 입력 즉시 존재 여부까지 검증
        path = prompt_until("리뷰 파일 경로(CSV/Excel): ", existing_review_file)
        add_option(argv, "--file", path)

    elif command == "clean":
        pol = ask("중복 정책 (skip, 엔터=기본): ")
        add_option(argv, "--dedup-policy", pol)

    elif command == "analyze":
        eprint("분석 대상: [1]미분석만(기본)  [2]전체  [3]특정 id")
        while True:                                  # 1/2/3/엔터 외에는 재입력
            pick = ask("선택 (엔터=미분석만): ")
            if pick in ("", "1", "2", "3"):
                break
            eprint("  1, 2, 3 중에서 선택하세요.")
        if pick == "2":
            argv.append("--all")
        elif pick == "3":
            rid = prompt_until("리뷰 id: ", positive_int)
            argv += ["--id", str(rid)]
        if "--id" not in argv:                       # id 지정 시 limit은 병용 불가
            lim = ask("최대 처리 건수 (엔터=제한없음): ")
            if lim:
                lim_val = prompt_until_value(lim, positive_int)
                add_option(argv, "--limit", str(lim_val))

    elif command == "extract":
        add_sentiment(argv, "감정 (긍정/부정/중립/미상, 엔터=전체): ")
        add_option(argv, "--product", ask("제품명 (엔터=전체): "))
        add_date(argv, "--date-from", "시작일 YYYY-MM-DD (엔터=제한없음): ")
        add_date(argv, "--date-to", "종료일 YYYY-MM-DD (엔터=제한없음): ")

    elif command == "list":
        add_sentiment(argv, "감정 (긍정/부정/중립/미상, 엔터=전체): ")
        rating = ask("별점 1~5 (엔터=전체): ")
        if rating:
            rating_val = prompt_until_value(rating, rating_int)   # 즉시 검증
            add_option(argv, "--rating", str(rating_val))
        add_date(argv, "--date-from", "시작일 YYYY-MM-DD (엔터=제한없음): ")
        add_date(argv, "--date-to", "종료일 YYYY-MM-DD (엔터=제한없음): ")
        sort = ask("정렬 (최신/오래된/별점, 엔터=최신): ")
        if sort:
            add_option(argv, "--sort", prompt_until_value(sort, normalize_sort))

    elif command == "show":
        rid = prompt_until("리뷰 id: ", positive_int)
        argv.append(str(rid))                        # show는 위치 인자

    elif command == "stats":
        add_option(argv, "--product", ask("제품명 (엔터=전체): "))

    elif command == "dashboard":
        add_option(argv, "--output", ask("출력 폴더 (엔터=output): "))

    elif command == "export":
        # 형식은 필수
        fmt = ask("형식 (csv/jsonl/excel): ")
        while not fmt:
            eprint("  형식은 필수입니다.")
            fmt = ask("형식 (csv/jsonl/excel): ")
        add_option(argv, "--format", prompt_until_value(fmt, normalize_format))
        add_sentiment(argv, "감정 필터 (긍정/부정/중립/미상, 엔터=전체): ")
        rmin = ask("최소 별점 1~5 (엔터=제한없음): ")
        if rmin:
            add_option(argv, "--rating-min", str(prompt_until_value(rmin, rating_int)))

    return argv


def prompt_until_value(first: str, convert: Callable[[str], Any]) -> Any:
    """
    이미 받은 첫 입력(first)을 검증하고, 실패하면 다시 물어본다.
    (list의 별점처럼 '값이 있을 때만' 검증하고 싶을 때 사용)
    """
    try:
        return convert(first)
    except (ValueError, argparse.ArgumentTypeError) as e:
        eprint(f"  입력 오류: {e}")
        return prompt_until("  다시 입력: ", convert)


def run_interactive() -> int:
    """대화형 진입점: 명령을 고르고 → argv를 조립해 → 기존 main()에 넘긴다."""
    eprint("=" * 52)
    eprint("  대화형 모드 (질문에 답하면 명령을 대신 만들어 실행합니다)")
    eprint("  기존 방식도 그대로 됩니다:  python cli.py list --sentiment 긍정")
    eprint("=" * 52)
    try:
        command = choose_command()
        argv = build_argv_for(command)
    except UserAbort as e:
        eprint(f"\n중단됨: {e}")
        return 130

    # 조립된 명령을 사용자에게 보여주고 실행 (무엇이 실행되는지 학습 효과)
    # 실제 실행 파일명을 그대로 반영 (cli.py / main.py / "cli (1).py" 등)
    script_name = Path(sys.argv[0]).name or "main.py"
    eprint(f"\n실행할 명령:  python {script_name} " + " ".join(argv))
    eprint("-" * 52)
    return main(argv)


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------
def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "command", None):
        parser.print_help()
        return 2

    config = load_config(args.config)

    # DB 초기화는 여기서 한 번만. CREATE TABLE IF NOT EXISTS라 매번 불러도 안전.
    initialize_database(args.db, verbose=args.verbose)

    try:
        logger.info("명령 실행 시작: %s", args.command)
        args.func(args, config)
        logger.info("명령 실행 완료: %s", args.command)
        return 0
    except UserAbort as e:
        logger.warning("사용자 중단: %s", e)
        eprint(f"\n중단됨: {e}")
        return 130                      # SIGINT 관례 종료코드
    except KeyboardInterrupt:
        logger.warning("사용자가 Ctrl+C로 실행을 중단했습니다.")
        eprint("\n중단됨 (Ctrl+C)")
        return 130
    except FileNotFoundError as e:
        logger.error("파일을 찾을 수 없습니다: %s", e)
        eprint(f"[오류] 파일을 찾을 수 없습니다: {e}")
        return 1
    # [15번] 아래 예외들도 traceback 대신 사용자용 메시지로 정리.
    except ValueError as e:
        logger.error("잘못된 입력/값: %s", e)
        eprint(f"[오류] 잘못된 입력/값입니다: {e}")
        return 1
    except sqlite3.Error as e:
        logger.error("데이터베이스 오류: %s", e)
        eprint(f"[오류] 데이터베이스 오류: {e}")
        return 1
    except Exception as e:
        logger.exception("예기치 못한 오류가 발생했습니다.")
        # 예상 못 한 오류도 최소한 한 줄로. (--verbose면 traceback을 보고 싶을 수 있어 안내)
        eprint(f"[오류] 예기치 못한 오류: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    # 인자 없이 실행하면 대화형 모드, 인자가 있으면 기존 CLI로 동작.
    #   python cli.py                         → 대화형 (질문에 답만)
    #   python cli.py list --sentiment 긍정   → 기존 방식 그대로
    #   python cli.py --interactive           → 명시적 대화형 진입
    if len(sys.argv) == 1 or sys.argv[1] in ("--interactive", "-i"):
        sys.exit(run_interactive())
    sys.exit(main())
