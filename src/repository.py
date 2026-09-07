# src/repository.py

import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Optional, Any


DEFAULT_DB_PATH = "data/reviews.db"


@contextmanager
def get_connection(db_path: str = DEFAULT_DB_PATH):
    """
    SQLite connection context manager.

    모든 DB 접근은 sqlite3.connect()를 직접 호출하지 말고
    반드시 이 함수를 통해 수행합니다.

    보장 사항:
    - PRAGMA foreign_keys = ON
    - PRAGMA journal_mode = WAL
    - PRAGMA busy_timeout = 10000
    - 정상 종료 시 commit
    - 예외 발생 시 rollback
    - 종료 시 close
    """
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.row_factory = sqlite3.Row

    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 10000;")

        yield conn

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def column_exists(
    conn: sqlite3.Connection,
    table_name: str,
    column_name: str,
) -> bool:
    """특정 테이블에 컬럼이 존재하는지 확인합니다."""
    # table_name은 내부 스키마 마이그레이션에서만 고정값으로 전달합니다.
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(row["name"] == column_name for row in rows)


def migrate_schema(conn: sqlite3.Connection) -> None:
    """기존 DB를 현재 스키마로 안전하게 마이그레이션합니다."""
    if not column_exists(conn, "raw_reviews", "processed"):
        conn.execute("""
        ALTER TABLE raw_reviews
        ADD COLUMN processed INTEGER NOT NULL DEFAULT 0
        """)

        # 구버전 DB에서 이미 clean_reviews로 정제된 raw는 재처리하지 않도록 백필합니다.
        conn.execute("""
        UPDATE raw_reviews
        SET processed = 1
        WHERE id IN (
            SELECT raw_id
            FROM clean_reviews
        )
        """)


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """
    Project C 리뷰 감정 분석 대시보드용 DB 스키마를 초기화합니다.

    생성 테이블:
    - raw_reviews
    - clean_reviews
    - analysis_results
    - extraction_results
    """
    with get_connection(db_path) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            source_file TEXT NOT NULL,
            original_row_number INTEGER,

            raw_text TEXT NOT NULL,
            raw_rating REAL,
            raw_date TEXT,
            raw_product TEXT,

            -- [31번 수정] 정제 '시도' 완료 여부. clean_reviews.raw_id 존재로
            --   추론하면, 중복이라 skip된 raw가 영원히 미정제로 남는다.
            --   저장이든 skip이든 한 번 처리하면 1로 표시해 재조회에서 제외한다.
            processed INTEGER NOT NULL DEFAULT 0,

            imported_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        );
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS clean_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            raw_id INTEGER NOT NULL,
            source_file TEXT NOT NULL,

            text_hash TEXT NOT NULL UNIQUE,
            cleaned_text TEXT NOT NULL,

            rating REAL CHECK (
                rating IS NULL OR rating BETWEEN 1 AND 5
            ),
            review_date TEXT,
            product_name TEXT,

            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),

            FOREIGN KEY (raw_id)
                REFERENCES raw_reviews(id)
                ON DELETE CASCADE
        );
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS analysis_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            review_id INTEGER NOT NULL,

            sentiment TEXT NOT NULL CHECK (
                sentiment IN ('positive', 'neutral', 'negative', 'unknown')
            ),
            confidence REAL CHECK (
                confidence IS NULL OR confidence BETWEEN 0 AND 1
            ),

            model_name TEXT NOT NULL,
            prompt_version TEXT NOT NULL DEFAULT 'v1',

            raw_response TEXT,

            analyzed_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),

            FOREIGN KEY (review_id)
                REFERENCES clean_reviews(id)
                ON DELETE CASCADE,

            UNIQUE (review_id, model_name, prompt_version)
        );
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS extraction_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            condition_json TEXT NOT NULL DEFAULT '{}',
            review_ids_json TEXT,

            positive_keywords_json TEXT,
            negative_keywords_json TEXT,
            keywords_json TEXT,

            summary TEXT,
            suggestions TEXT,

            model_name TEXT NOT NULL,
            prompt_version TEXT NOT NULL DEFAULT 'v1',

            raw_response TEXT,

            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        );
        """)

        # CREATE TABLE IF NOT EXISTS는 기존 테이블의 컬럼을 변경하지 않으므로,
        # 인덱스를 만들기 전에 누락 컬럼을 먼저 보강합니다.
        migrate_schema(conn)

        conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_raw_reviews_source_file
        ON raw_reviews(source_file);
        """)

        conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_raw_reviews_processed
        ON raw_reviews(processed, id);
        """)

        conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_raw_reviews_imported_at
        ON raw_reviews(imported_at);
        """)

        conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_clean_reviews_raw_id
        ON clean_reviews(raw_id);
        """)

        # [3-7 수정] text_hash는 UNIQUE 제약이 있어 SQLite가 유니크 인덱스를
        #   자동 생성합니다. 별도 인덱스는 중복이라 쓰기 성능만 깎으므로 제거했습니다.
        #   (idx_clean_reviews_text_hash 삭제)

        conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_clean_reviews_review_date
        ON clean_reviews(review_date);
        """)

        conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_clean_reviews_product_name
        ON clean_reviews(product_name);
        """)

        conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_analysis_results_review_id
        ON analysis_results(review_id);
        """)

        conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_analysis_results_sentiment
        ON analysis_results(sentiment);
        """)

        conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_analysis_results_analyzed_at
        ON analysis_results(analyzed_at);
        """)

        conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_extraction_results_created_at
        ON extraction_results(created_at);
        """)


def insert_raw_review(
    conn: sqlite3.Connection,
    source_file: str,
    raw_text: str,
    original_row_number: Optional[int] = None,
    raw_rating: Optional[float] = None,
    raw_date: Optional[str] = None,
    raw_product: Optional[str] = None,
) -> int:
    """
    원본 리뷰 1건을 raw_reviews에 저장합니다.

    Returns:
        생성된 raw_reviews.id
    """
    cur = conn.execute("""
    INSERT INTO raw_reviews (
        source_file,
        original_row_number,
        raw_text,
        raw_rating,
        raw_date,
        raw_product
    )
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        source_file,
        original_row_number,
        raw_text,
        raw_rating,
        raw_date,
        raw_product,
    ))

    return int(cur.lastrowid)


def insert_clean_review_skip_duplicate(
    conn: sqlite3.Connection,
    raw_id: int,
    source_file: str,
    text_hash: str,
    cleaned_text: str,
    rating: Optional[float] = None,
    review_date: Optional[str] = None,
    product_name: Optional[str] = None,
) -> dict[str, Any]:
    """
    [DEPRECATED / 3-1 정리] 구버전 함수. 신버전 insert_clean_review()로 위임합니다.

    정책(중복 판정·skip/upsert)을 한 곳(insert_clean_review)에만 두기 위해,
    이 함수는 인자를 dict로 묶어 신버전을 호출하는 얇은 wrapper로만 남깁니다.
    기존 호출 코드가 깨지지 않도록 유지하되, 새 코드는 insert_clean_review()를 쓰세요.
    """
    return insert_clean_review(
        conn,
        {
            "raw_id": raw_id,
            "source_file": source_file,
            "text_hash": text_hash,
            "cleaned_text": cleaned_text,
            "rating": rating,
            "review_date": review_date,
            "product_name": product_name,
        },
        dedup_policy="skip",
    )


def insert_analysis_result(
    conn: sqlite3.Connection,
    review_id: int,
    sentiment: str,
    model_name: str,
    prompt_version: str = "v1",
    confidence: Optional[float] = None,
    raw_response: Optional[str] = None,
) -> dict[str, Any]:
    """
    감정 분석 결과를 analysis_results에 저장합니다.

    [--all 재분석 정책] 같은 (review_id, model_name, prompt_version) 조합이
      이미 있으면 '기존 행을 덮어씁니다'(재분석 결과 반영).
      --unanalyzed 경로는 애초에 미분석 리뷰만 넘어오므로 신규 INSERT가 되고,
      --all 경로에서 이미 분석된 리뷰가 들어오면 이 덮어쓰기가 동작합니다.
      이력을 새 행으로 쌓지 않고 같은 조합을 갱신하는 방식입니다.

    lastrowid 추정을 쓰지 않고, 존재 여부를 먼저 확인한 뒤 분기합니다
    (insert_clean_review과 동일한 안전 패턴).

    Returns:
        {
            "id": analysis_results.id,
            "inserted": bool,   # 신규 저장이면 True
            "updated": bool     # 기존 결과를 덮어썼으면 True
        }
    """
    existing = conn.execute("""
    SELECT id FROM analysis_results
    WHERE review_id = ? AND model_name = ? AND prompt_version = ?
    """, (review_id, model_name, prompt_version)).fetchone()

    # 이미 있으면 덮어쓰기 (재분석)
    if existing is not None:
        conn.execute("""
        UPDATE analysis_results
        SET sentiment = ?, confidence = ?, raw_response = ?,
            analyzed_at = datetime('now', 'localtime')
        WHERE id = ?
        """, (sentiment, confidence, raw_response, existing["id"]))
        return {"id": int(existing["id"]), "inserted": False, "updated": True}

    # 없으면 신규 저장
    cur = conn.execute("""
    INSERT INTO analysis_results (
        review_id, sentiment, confidence,
        model_name, prompt_version, raw_response
    )
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        review_id, sentiment, confidence,
        model_name, prompt_version, raw_response,
    ))
    return {"id": int(cur.lastrowid), "inserted": True, "updated": False}


def insert_extraction_result(
    conn: sqlite3.Connection,
    model_name: str,
    prompt_version: str = "v1",
    condition_json: str = "{}",
    review_ids_json: Optional[str] = None,
    positive_keywords_json: Optional[str] = None,
    negative_keywords_json: Optional[str] = None,
    keywords_json: Optional[str] = None,
    summary: Optional[str] = None,
    suggestions: Optional[str] = None,
    raw_response: Optional[str] = None,
) -> int:
    """
    키워드, 요약, 개선 제안 결과를 extraction_results에 저장합니다.

    Returns:
        생성된 extraction_results.id
    """
    cur = conn.execute("""
    INSERT INTO extraction_results (
        condition_json,
        review_ids_json,
        positive_keywords_json,
        negative_keywords_json,
        keywords_json,
        summary,
        suggestions,
        model_name,
        prompt_version,
        raw_response
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        condition_json,
        review_ids_json,
        positive_keywords_json,
        negative_keywords_json,
        keywords_json,
        summary,
        suggestions,
        model_name,
        prompt_version,
        raw_response,
    ))

    return int(cur.lastrowid)


def get_unanalyzed_reviews(
    conn: sqlite3.Connection,
    model_name: str,
    prompt_version: str = "v1",
    limit: Optional[int] = None,
) -> list[sqlite3.Row]:
    """
    [DEPRECATED / 3-1 정리] 구버전 함수. 신버전 get_reviews_for_analysis()로 위임합니다.

    '미분석 조회' 로직을 한 곳에만 두기 위해, 이 함수는 신버전을 호출하는
    wrapper로만 남깁니다. 새 코드는 get_reviews_for_analysis(...)를 쓰세요.
    (반환 컬럼: id, cleaned_text, rating, review_date, product_name)
    """
    return get_reviews_for_analysis(
        conn,
        review_id=None,
        analyze_all=False,
        model_name=model_name,
        prompt_version=prompt_version,
        limit=limit,
    )


def get_sentiment_stats(
    conn: sqlite3.Connection,
    model_name: str,
    prompt_version: str = "v1",
) -> list[sqlite3.Row]:
    """
    감정 분포 통계를 조회합니다.

    [3-4 수정] 특정 model_name + prompt_version 기준으로만 집계합니다.
      모델 기준이 없으면, 같은 리뷰를 여러 모델로 분석했을 때
      감정 카운트가 중복 합산되어 통계가 부풀려집니다.
      호출 시 config.json의 ai.model 값을 그대로 넘기세요.
    """
    return conn.execute("""
    SELECT
        sentiment,
        COUNT(*) AS count
    FROM analysis_results
    WHERE model_name = ?
      AND prompt_version = ?
    GROUP BY sentiment
    ORDER BY count DESC
    """, (model_name, prompt_version)).fetchall()


def get_review_count(conn: sqlite3.Connection) -> dict[str, int]:
    """
    raw, clean, analysis 테이블의 기본 건수를 조회합니다.
    """
    raw_count = conn.execute("""
    SELECT COUNT(*) AS count
    FROM raw_reviews
    """).fetchone()["count"]

    clean_count = conn.execute("""
    SELECT COUNT(*) AS count
    FROM clean_reviews
    """).fetchone()["count"]

    analysis_count = conn.execute("""
    SELECT COUNT(*) AS count
    FROM analysis_results
    """).fetchone()["count"]

    extraction_count = conn.execute("""
    SELECT COUNT(*) AS count
    FROM extraction_results
    """).fetchone()["count"]

    return {
        "raw_reviews": int(raw_count),
        "clean_reviews": int(clean_count),
        "analysis_results": int(analysis_count),
        "extraction_results": int(extraction_count),
    }

# ===========================================================================
# collector / cleaner 연결용 함수 (collector·cleaner 담당 요청 반영)
# ===========================================================================

def insert_raw_review_row(conn: sqlite3.Connection, row: dict[str, Any]) -> int:
    """
    원본 리뷰 1건(dict)을 raw_reviews에 저장하고, 생성된 id를 반환합니다.

    collector가 파일에서 읽어 컬럼명을 표준화한 dict를 그대로 넘길 수 있게
    만든 편의 함수입니다. 필드가 없으면 None으로 처리하므로,
    선택 필드(별점/날짜/제품)가 비어 있어도 안전합니다.

    기대하는 row 키(없으면 None):
      source_file(필수), raw_text(필수),
      original_row_number, raw_rating, raw_date, raw_product

    반환값(int)은 cleaner가 clean_reviews의 raw_id로 사용합니다.
    """
    return insert_raw_review(
        conn,
        source_file=row["source_file"],
        raw_text=row["raw_text"],
        original_row_number=row.get("original_row_number"),
        raw_rating=row.get("raw_rating"),
        raw_date=row.get("raw_date"),
        raw_product=row.get("raw_product"),
    )


def get_raw_reviews_for_cleaning(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """
    아직 정제되지 않은 raw_reviews만 조회합니다.

    [31번 수정] '정제됨' 판정을 clean_reviews.raw_id 존재가 아니라
    raw_reviews.processed 플래그로 합니다. 그래야 중복이라 skip된 raw도
    '처리 시도 완료'로 표시되어 재조회에서 빠집니다(무한 재처리 방지).

    반환 컬럼: id, source_file, raw_text, raw_rating, raw_date, raw_product
    """
    return conn.execute("""
    SELECT
        rr.id,
        rr.source_file,
        rr.raw_text,
        rr.raw_rating,
        rr.raw_date,
        rr.raw_product
    FROM raw_reviews rr
    WHERE rr.processed = 0
    ORDER BY rr.id ASC
    """).fetchall()


def mark_raw_processed(conn: sqlite3.Connection, raw_id: int) -> None:
    """
    raw 리뷰 1건을 '정제 시도 완료'로 표시합니다.
    저장(신규)이든 중복 skip이든, cleaner가 한 건 처리를 마치면 호출합니다.
    """
    conn.execute("UPDATE raw_reviews SET processed = 1 WHERE id = ?", (raw_id,))


def insert_clean_review(
    conn: sqlite3.Connection,
    row: dict[str, Any],
    dedup_policy: str = "skip",
) -> dict[str, Any]:
    """
    정제된 리뷰 1건(dict)을 clean_reviews에 저장합니다.

    중복 정책(dedup_policy):
    - "skip"   : text_hash 충돌 시 INSERT하지 않고 기존 id 반환 (기본)
    - "upsert" : text_hash 충돌 시 기존 행을 새 값으로 갱신

    기대하는 row 키:
      raw_id(필수), source_file(필수), text_hash(필수), cleaned_text(필수),
      rating, review_date, product_name (없으면 None)

    반환: {"id": clean_reviews.id, "inserted": bool, "duplicate": bool}
      - inserted=True  : 신규 저장됨
      - duplicate=True  : text_hash 충돌 발생 (skip이면 무시, upsert면 갱신됨)

    [2-5 정책 명시] upsert 시 raw_id 와 source_file 은 갱신하지 않습니다(최초 출처 유지).
      즉 같은 text_hash가 다른 파일/행에서 다시 들어와도 '처음 저장된 출처'가 남습니다.
      갱신 대상은 cleaned_text, rating, review_date, product_name 뿐입니다.
      (최신 출처로 바꾸고 싶으면 UPDATE 문에 raw_id, source_file을 추가하세요.)
    """
    if dedup_policy not in ("skip", "upsert"):
        raise ValueError(f"알 수 없는 dedup_policy: {dedup_policy!r} (skip/upsert)")

    # [3-2 수정] lastrowid로 신규/갱신을 '추정'하지 않는다.
    #   SQLite에서 ON CONFLICT DO UPDATE 시 lastrowid는 신뢰할 수 없어,
    #   update인데 inserted=True로 잘못 판단할 수 있다.
    #   → 먼저 존재 여부를 명시적으로 확인한 뒤 분기한다.
    existing = conn.execute(
        "SELECT id FROM clean_reviews WHERE text_hash = ?",
        (row["text_hash"],),
    ).fetchone()

    # 1) 이미 존재 + skip → 아무것도 하지 않고 기존 id 반환
    if existing is not None and dedup_policy == "skip":
        return {"id": int(existing["id"]), "inserted": False, "duplicate": True}

    # 2) 이미 존재 + upsert → 기존 행 갱신 (텍스트 외 값을 최신으로)
    if existing is not None and dedup_policy == "upsert":
        conn.execute("""
        UPDATE clean_reviews
        SET cleaned_text = ?, rating = ?, review_date = ?, product_name = ?
        WHERE text_hash = ?
        """, (
            row["cleaned_text"],
            row.get("rating"),
            row.get("review_date"),
            row.get("product_name"),
            row["text_hash"],
        ))
        return {"id": int(existing["id"]), "inserted": False, "duplicate": True}

    # 3) 신규 → INSERT 후 새 id 반환
    cur = conn.execute("""
    INSERT INTO clean_reviews (
        raw_id, source_file, text_hash, cleaned_text,
        rating, review_date, product_name
    )
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        row["raw_id"],
        row["source_file"],
        row["text_hash"],
        row["cleaned_text"],
        row.get("rating"),
        row.get("review_date"),
        row.get("product_name"),
    ))
    return {"id": int(cur.lastrowid), "inserted": True, "duplicate": False}


# ===========================================================================
# ai_client / analyzer 연결용 함수 (AI 분석 담당 요청 반영)
# ===========================================================================

def get_reviews_for_analysis(
    conn: sqlite3.Connection,
    review_id: Optional[int] = None,
    analyze_all: bool = False,
    model_name: Optional[str] = None,
    prompt_version: str = "v1",
    limit: Optional[int] = None,
) -> list[sqlite3.Row]:
    """
    감정 분석 대상 리뷰를 조회합니다. (CLI의 --id / --all / --unanalyzed 대응)

    분기:
    - review_id 지정  : 그 리뷰 1건만
    - analyze_all=True: clean_reviews 전체
    - 그 외(기본)      : '이 model_name + prompt_version 으로 아직 분석 안 된' 리뷰만

    주의(재현성 설계):
      '분석 안 됨'을 단순히 "analysis_results에 존재하는가"로 보지 않고,
      model_name + prompt_version 조합 기준으로 판정합니다.
      덕분에 같은 리뷰를 다른 모델/프롬프트로 재분석하는 흐름이 막히지 않습니다.
      (analysis_results가 UNIQUE(review_id, model_name, prompt_version)인 것과 일관)

    [2-2 수정] model_name 기본값을 None으로 바꾸고, 미분석 조회(기본 분기)에서는
      model_name을 필수로 강제합니다. 빈 문자열 기준으로 조회하면 실제 모델과
      다른 미분석 판정이 나오기 때문입니다. config.json의 ai.model 값을 넘기세요.

    반환 컬럼(요청대로 포함):
      id, cleaned_text, rating, review_date, product_name
    """
    # 미분석 조회(=review_id 없고 analyze_all 아님)일 때만 model_name 필수
    if review_id is None and not analyze_all and not model_name:
        raise ValueError("미분석 리뷰 조회 시 model_name은 필수입니다.")

    base_cols = """
        cr.id,
        cr.cleaned_text,
        cr.rating,
        cr.review_date,
        cr.product_name
    """

    if review_id is not None:
        # 특정 1건
        return conn.execute(f"""
        SELECT {base_cols}
        FROM clean_reviews cr
        WHERE cr.id = ?
        """, (review_id,)).fetchall()

    if analyze_all:
        sql = f"SELECT {base_cols} FROM clean_reviews cr ORDER BY cr.id ASC"
        params: list[Any] = []
    else:
        # 이 모델+프롬프트로 아직 분석 결과가 없는 리뷰만
        sql = f"""
        SELECT {base_cols}
        FROM clean_reviews cr
        LEFT JOIN analysis_results ar
            ON ar.review_id = cr.id
           AND ar.model_name = ?
           AND ar.prompt_version = ?
        WHERE ar.id IS NULL
        ORDER BY cr.id ASC
        """
        params = [model_name, prompt_version]

    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)

    return conn.execute(sql, params).fetchall()


def get_reviews_for_extraction(
    conn: sqlite3.Connection,
    sentiment: Optional[str] = None,
    product: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    model_name: Optional[str] = None,
    prompt_version: str = "v1",
    limit: Optional[int] = None,
) -> list[sqlite3.Row]:
    """
    키워드/요약 추출 대상 리뷰를 조건별로 조회합니다.
    (CLI의 extract --sentiment/--product/--date-from/--date-to/--limit 대응)

    감정 필터가 있을 때만 analysis_results와 조인합니다.
    (감정은 clean_reviews가 아니라 분석 결과에 있으므로)

    [3-5 / 2-1 수정] 감정 필터 사용 시 model_name을 '필수'로 강제합니다.
      model_name이 없으면 같은 리뷰의 여러 모델 결과가 모두 조인되어
      중복 row가 생기고, 어떤 모델의 sentiment인지 불명확해집니다.
      따라서 sentiment를 넘길 때는 model_name도 반드시 함께 넘겨야 합니다.
      (product/date만으로 조회할 때는 model_name 불필요)

    반환 컬럼:
      id, cleaned_text, rating, review_date, product_name, sentiment(있으면)
    """
    # 감정 필터를 쓰면서 모델을 지정하지 않으면 중복 위험 → 막는다
    if sentiment is not None and not model_name:
        raise ValueError("sentiment 필터 사용 시 model_name은 필수입니다.")

    where: list[str] = []
    params: list[Any] = []

    # 감정 조건이 있으면 조인(모델/프롬프트 기준 포함), 없으면 순수 clean_reviews 조회
    if sentiment is not None:
        join = (
            "JOIN analysis_results ar ON ar.review_id = cr.id "
            "AND ar.model_name = ? AND ar.prompt_version = ?"
        )
        params.append(model_name)
        params.append(prompt_version)
        sentiment_col = ", ar.sentiment"
        where.append("ar.sentiment = ?")
        params.append(sentiment)
    else:
        join = ""
        sentiment_col = ""

    if product is not None:
        where.append("cr.product_name = ?")
        params.append(product)
    if date_from is not None:
        where.append("cr.review_date >= ?")
        params.append(date_from)
    if date_to is not None:
        where.append("cr.review_date <= ?")
        params.append(date_to)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    sql = f"""
    SELECT
        cr.id,
        cr.cleaned_text,
        cr.rating,
        cr.review_date,
        cr.product_name{sentiment_col}
    FROM clean_reviews cr
    {join}
    {where_sql}
    ORDER BY cr.id ASC
    """
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)

    return conn.execute(sql, params).fetchall()


# ===========================================================================
# list / show 조회용 함수 (CLI cmd_list, cmd_show 연결용)
# ===========================================================================

# --sort 표준값 → 실제 ORDER BY 절 매핑
_SORT_MAP = {
    "date_desc": "cr.review_date DESC, cr.id DESC",
    "date_asc": "cr.review_date ASC, cr.id ASC",
    "rating_desc": "cr.rating DESC, cr.id DESC",
    "rating_asc": "cr.rating ASC, cr.id ASC",
    "id_asc": "cr.id ASC",
}


def list_reviews(
    conn: sqlite3.Connection,
    sentiment: Optional[str] = None,
    rating: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    model_name: Optional[str] = None,
    prompt_version: str = "v1",
    sort: str = "date_desc",
    page: int = 1,
    size: int = 20,
) -> dict[str, Any]:
    """
    조건별 리뷰 목록을 페이지네이션하여 조회합니다. (CLI list 대응)

    감정(sentiment)은 clean_reviews가 아니라 analysis_results에 있으므로
    LEFT JOIN으로 붙입니다(분석 안 된 리뷰도 목록에는 나오되 sentiment=NULL).
    감정 필터를 쓸 때는 model_name을 함께 넘겨 모델 섞임을 방지하세요.

    반환:
      {
        "rows": [Row, ...],   # 현재 페이지 항목 (id, cleaned_text, rating,
                              #                    review_date, product_name, sentiment, confidence)
        "total": int,         # 필터 적용 후 전체 건수
        "page": int, "size": int, "total_pages": int
      }
    """
    # [치명 수정] model_name 필수. 없으면 LEFT JOIN이 여러 모델 결과를 모두 붙여
    #   total과 rows가 중복 부풀림. 감정 컬럼을 보여주려면 모델을 반드시 고정한다.
    if not model_name:
        raise ValueError("list_reviews 조회 시 model_name은 필수입니다.")
    # [권장] repository 함수 자체에도 페이지 방어 (CLI 검증과 별개로 안전망)
    if page < 1:
        raise ValueError("page는 1 이상이어야 합니다.")
    if size < 1:
        raise ValueError("size는 1 이상이어야 합니다.")

    where: list[str] = []
    params: list[Any] = []

    # 감정을 보여주기 위한 LEFT JOIN. model_name+prompt_version으로 고정해 중복 방지.
    join = (
        "LEFT JOIN analysis_results ar "
        "ON ar.review_id = cr.id "
        "AND ar.model_name = ? AND ar.prompt_version = ?"
    )
    params.append(model_name)
    params.append(prompt_version)

    if sentiment is not None:
        where.append("ar.sentiment = ?")
        params.append(sentiment)
    if rating is not None:
        where.append("cr.rating = ?")
        params.append(rating)
    if date_from is not None:
        where.append("cr.review_date >= ?")
        params.append(date_from)
    if date_to is not None:
        where.append("cr.review_date <= ?")
        params.append(date_to)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    order_sql = "ORDER BY " + _SORT_MAP.get(sort, _SORT_MAP["date_desc"])

    # 전체 건수 (페이지 계산용)
    total = conn.execute(
        f"SELECT COUNT(*) AS n FROM clean_reviews cr {join} {where_sql}",
        params,
    ).fetchone()["n"]

    # 페이지 항목
    offset = (page - 1) * size
    rows = conn.execute(
        f"""
        SELECT
            cr.id, cr.cleaned_text, cr.rating, cr.review_date,
            cr.product_name, ar.sentiment, ar.confidence
        FROM clean_reviews cr
        {join}
        {where_sql}
        {order_sql}
        LIMIT ? OFFSET ?
        """,
        params + [size, offset],
    ).fetchall()

    total_pages = (total + size - 1) // size if size > 0 else 1
    return {
        "rows": rows,
        "total": int(total),
        "page": page,
        "size": size,
        "total_pages": max(total_pages, 1),
    }


def get_review_by_id(
    conn: sqlite3.Connection,
    review_id: int,
    model_name: Optional[str] = None,
    prompt_version: str = "v1",
) -> Optional[sqlite3.Row]:
    """
    특정 리뷰 1건의 상세를 조회합니다. (CLI show 대응)

    원문·별점·날짜·제품명과 함께 감정 분석 결과를 LEFT JOIN으로 붙입니다.
    model_name을 주면 그 모델의 분석 결과를, 안 주면 아무 분석 결과 하나를 보여줍니다.
    없는 id면 None을 반환합니다.
    """
    join_cond = ["ar.review_id = cr.id"]
    params: list[Any] = []
    if model_name is not None:
        join_cond.append("ar.model_name = ?")
        params.append(model_name)
        join_cond.append("ar.prompt_version = ?")
        params.append(prompt_version)
    join = "LEFT JOIN analysis_results ar ON " + " AND ".join(join_cond)

    # [권장] model_name 미지정 시 여러 분석 결과 중 아무거나 붙는 비결정성을
    #   막기 위해 최신 분석 1건으로 한정한다.
    order_limit = "ORDER BY ar.analyzed_at DESC LIMIT 1" if model_name is None else ""

    params.append(review_id)
    return conn.execute(
        f"""
        SELECT
            cr.id, cr.cleaned_text, cr.rating, cr.review_date,
            cr.product_name, cr.source_file, cr.created_at,
            ar.sentiment, ar.confidence, ar.model_name, ar.analyzed_at
        FROM clean_reviews cr
        {join}
        WHERE cr.id = ?
        {order_limit}
        """,
        params,
    ).fetchone()
