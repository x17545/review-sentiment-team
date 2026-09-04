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
    모든 DB 접근은 sqlite3.connect()를 직접 호출하지 말고 이 함수를 통해 수행합니다.
    보장: foreign_keys ON / WAL / busy_timeout / 정상 시 commit / 예외 시 rollback / 종료 시 close
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
            rating REAL CHECK (rating IS NULL OR rating BETWEEN 1 AND 5),
            review_date TEXT,
            product_name TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (raw_id) REFERENCES raw_reviews(id) ON DELETE CASCADE
        );
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS analysis_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id INTEGER NOT NULL,
            sentiment TEXT NOT NULL CHECK (sentiment IN ('positive','neutral','negative','unknown')),
            confidence REAL CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
            model_name TEXT NOT NULL,
            prompt_version TEXT NOT NULL DEFAULT 'v1',
            raw_response TEXT,
            analyzed_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (review_id) REFERENCES clean_reviews(id) ON DELETE CASCADE,
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
        for idx in (
            "CREATE INDEX IF NOT EXISTS idx_raw_reviews_source_file ON raw_reviews(source_file);",
            "CREATE INDEX IF NOT EXISTS idx_clean_reviews_raw_id ON clean_reviews(raw_id);",
            "CREATE INDEX IF NOT EXISTS idx_clean_reviews_text_hash ON clean_reviews(text_hash);",
            "CREATE INDEX IF NOT EXISTS idx_analysis_results_review_id ON analysis_results(review_id);",
            "CREATE INDEX IF NOT EXISTS idx_analysis_results_sentiment ON analysis_results(sentiment);",
        ):
            conn.execute(idx)


def get_review_count(conn: sqlite3.Connection) -> dict[str, int]:
    def c(t): return conn.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
    return {
        "raw_reviews": int(c("raw_reviews")),
        "clean_reviews": int(c("clean_reviews")),
        "analysis_results": int(c("analysis_results")),
        "extraction_results": int(c("extraction_results")),
    }


def get_sentiment_stats(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("""
        SELECT sentiment, COUNT(*) AS count
        FROM analysis_results GROUP BY sentiment ORDER BY count DESC
    """).fetchall()
