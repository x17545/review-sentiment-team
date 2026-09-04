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

        conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_raw_reviews_source_file
        ON raw_reviews(source_file);
        """)

        conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_raw_reviews_imported_at
        ON raw_reviews(imported_at);
        """)

        conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_clean_reviews_raw_id
        ON clean_reviews(raw_id);
        """)

        conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_clean_reviews_text_hash
        ON clean_reviews(text_hash);
        """)

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
    정제 리뷰를 clean_reviews에 저장합니다.

    중복 정책:
    - text_hash가 없으면 INSERT
    - text_hash가 이미 있으면 INSERT하지 않고 기존 id 반환
    - 즉, 기본 정책은 skip

    Returns:
        {
            "id": clean_reviews.id,
            "inserted": bool,
            "duplicate": bool
        }
    """
    cur = conn.execute("""
    INSERT INTO clean_reviews (
        raw_id,
        source_file,
        text_hash,
        cleaned_text,
        rating,
        review_date,
        product_name
    )
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(text_hash) DO NOTHING
    """, (
        raw_id,
        source_file,
        text_hash,
        cleaned_text,
        rating,
        review_date,
        product_name,
    ))

    if cur.rowcount == 1:
        return {
            "id": int(cur.lastrowid),
            "inserted": True,
            "duplicate": False,
        }

    row = conn.execute("""
    SELECT id
    FROM clean_reviews
    WHERE text_hash = ?
    """, (text_hash,)).fetchone()

    if row is None:
        raise RuntimeError(
            "clean_reviews insert skipped, but existing row was not found. "
            f"text_hash={text_hash}"
        )

    return {
        "id": int(row["id"]),
        "inserted": False,
        "duplicate": True,
    }


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

    동일한 review_id, model_name, prompt_version 조합이 이미 있으면
    중복 저장하지 않고 기존 id를 반환합니다.

    Returns:
        {
            "id": analysis_results.id,
            "inserted": bool,
            "duplicate": bool
        }
    """
    cur = conn.execute("""
    INSERT INTO analysis_results (
        review_id,
        sentiment,
        confidence,
        model_name,
        prompt_version,
        raw_response
    )
    VALUES (?, ?, ?, ?, ?, ?)
    ON CONFLICT(review_id, model_name, prompt_version) DO NOTHING
    """, (
        review_id,
        sentiment,
        confidence,
        model_name,
        prompt_version,
        raw_response,
    ))

    if cur.rowcount == 1:
        return {
            "id": int(cur.lastrowid),
            "inserted": True,
            "duplicate": False,
        }

    row = conn.execute("""
    SELECT id
    FROM analysis_results
    WHERE review_id = ?
      AND model_name = ?
      AND prompt_version = ?
    """, (
        review_id,
        model_name,
        prompt_version,
    )).fetchone()

    if row is None:
        raise RuntimeError(
            "analysis_results insert skipped, but existing row was not found. "
            f"review_id={review_id}, model_name={model_name}, "
            f"prompt_version={prompt_version}"
        )

    return {
        "id": int(row["id"]),
        "inserted": False,
        "duplicate": True,
    }


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
    아직 감정 분석이 완료되지 않은 clean_reviews 목록을 조회합니다.

    주의:
    이 함수는 DB 조회만 수행합니다.
    AI API 호출은 이 함수 호출 이후 DB 트랜잭션 밖에서 수행하는 것을 권장합니다.
    """
    sql = """
    SELECT
        cr.id,
        cr.cleaned_text,
        cr.rating,
        cr.review_date,
        cr.product_name,
        cr.source_file
    FROM clean_reviews cr
    LEFT JOIN analysis_results ar
        ON cr.id = ar.review_id
       AND ar.model_name = ?
       AND ar.prompt_version = ?
    WHERE ar.id IS NULL
    ORDER BY cr.id ASC
    """

    params: list[Any] = [model_name, prompt_version]

    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)

    return conn.execute(sql, params).fetchall()


def get_sentiment_stats(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """
    감정 분포 통계를 조회합니다.
    """
    return conn.execute("""
    SELECT
        sentiment,
        COUNT(*) AS count
    FROM analysis_results
    GROUP BY sentiment
    ORDER BY count DESC
    """).fetchall()


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

    '정제됨'의 기준: clean_reviews.raw_id 에 해당 raw.id 가 이미 존재하는지.
    LEFT JOIN 후 매칭이 없는(cr.id IS NULL) raw 행만 남깁니다.
    이렇게 하면 clean을 여러 번 실행해도 이미 정제한 원본을 다시 처리하지 않습니다.

    반환 컬럼: id(raw_reviews.id), source_file, raw_text, raw_rating, raw_date, raw_product
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
    LEFT JOIN clean_reviews cr
        ON cr.raw_id = rr.id
    WHERE cr.id IS NULL
    ORDER BY rr.id ASC
    """).fetchall()


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
    """
    if dedup_policy not in ("skip", "upsert"):
        raise ValueError(f"알 수 없는 dedup_policy: {dedup_policy!r} (skip/upsert)")

    params = (
        row["raw_id"],
        row["source_file"],
        row["text_hash"],
        row["cleaned_text"],
        row.get("rating"),
        row.get("review_date"),
        row.get("product_name"),
    )

    if dedup_policy == "skip":
        # 충돌 시 아무것도 하지 않음
        cur = conn.execute("""
        INSERT INTO clean_reviews (
            raw_id, source_file, text_hash, cleaned_text,
            rating, review_date, product_name
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(text_hash) DO NOTHING
        """, params)
    else:  # upsert: 충돌 시 기존 행 갱신 (raw_id/텍스트 외 값을 최신으로)
        cur = conn.execute("""
        INSERT INTO clean_reviews (
            raw_id, source_file, text_hash, cleaned_text,
            rating, review_date, product_name
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(text_hash) DO UPDATE SET
            cleaned_text  = excluded.cleaned_text,
            rating        = excluded.rating,
            review_date   = excluded.review_date,
            product_name  = excluded.product_name
        """, params)

    # 신규 INSERT면 rowcount==1 이고 lastrowid가 새 id
    if cur.rowcount == 1 and cur.lastrowid:
        # upsert로 '갱신'된 경우도 rowcount가 1일 수 있어, 신규 여부를 별도 확인
        row_db = conn.execute(
            "SELECT id FROM clean_reviews WHERE text_hash = ?",
            (row["text_hash"],),
        ).fetchone()
        # lastrowid가 실제 그 해시의 id와 같으면 신규 INSERT로 판단
        is_new = row_db is not None and int(row_db["id"]) == int(cur.lastrowid)
        return {
            "id": int(row_db["id"]),
            "inserted": is_new,
            "duplicate": not is_new,
        }

    # 충돌(skip으로 무시됐거나 upsert로 갱신) → 기존 id 조회
    existing = conn.execute(
        "SELECT id FROM clean_reviews WHERE text_hash = ?",
        (row["text_hash"],),
    ).fetchone()
    if existing is None:
        raise RuntimeError(
            f"clean_reviews 저장 후 행을 찾지 못했습니다. text_hash={row['text_hash']}"
        )
    return {"id": int(existing["id"]), "inserted": False, "duplicate": True}


# ===========================================================================
# ai_client / analyzer 연결용 함수 (AI 분석 담당 요청 반영)
# ===========================================================================

def get_reviews_for_analysis(
    conn: sqlite3.Connection,
    review_id: Optional[int] = None,
    analyze_all: bool = False,
    model_name: str = "",
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

    반환 컬럼(요청대로 포함):
      id, cleaned_text, rating, review_date, product_name
    """
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
    limit: Optional[int] = None,
) -> list[sqlite3.Row]:
    """
    키워드/요약 추출 대상 리뷰를 조건별로 조회합니다.
    (CLI의 extract --sentiment/--product/--date-from/--date-to/--limit 대응)

    감정 필터가 있을 때만 analysis_results와 조인합니다.
    (감정은 clean_reviews가 아니라 분석 결과에 있으므로)

    반환 컬럼:
      id, cleaned_text, rating, review_date, product_name, sentiment(있으면)
    """
    where: list[str] = []
    params: list[Any] = []

    # 감정 조건이 있으면 조인, 없으면 순수 clean_reviews 조회
    if sentiment is not None:
        join = "JOIN analysis_results ar ON ar.review_id = cr.id"
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
