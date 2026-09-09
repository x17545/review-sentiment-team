"""
src/comparison.py
제품/카테고리별 리뷰 데이터 비교 분석 모듈 (Bonus Feature).

기존 ai_client / analyzer / repository 코드를 수정하지 않고 독립적으로 동작합니다.
- 제품별 총 리뷰 수, 평균 별점, 긍정/중립/부정 감정 비율 계산
- 각 제품별 키워드 추출 결과(extraction_results) 연동 및 텍스트 빈도 보조 분석
- CLI 비교 테이블 서식 렌더링
"""

import json
import sqlite3
import re
from collections import Counter
from typing import Any, Optional


def get_available_products(conn: sqlite3.Connection) -> list[str]:
    """DB에 저장된 고유 제품 목록을 반환합니다 (NULL 및 빈 문자열 제외)."""
    rows = conn.execute("""
        SELECT DISTINCT product_name
        FROM clean_reviews
        WHERE product_name IS NOT NULL AND TRIM(product_name) != ''
        ORDER BY product_name ASC
    """).fetchall()
    return [r["product_name"] for r in rows]


def _extract_simple_keywords(texts: list[str], top_n: int = 3) -> list[str]:
    """리뷰 본문에서 한글/영문 2글자 이상 단어를 추출해 최빈 단어를 반환합니다 (보조용)."""
    words = []
    stop_words = {"너무", "정말", "진짜", "매우", "아주", "그냥", "좀", "다", "더", "수", "것", "이", "그", "저"}
    for t in texts:
        tokens = re.findall(r"[가-힣a-zA-Z]{2,}", t)
        words.extend([w for w in tokens if w not in stop_words])
    counter = Counter(words)
    return [w for w, _ in counter.most_common(top_n)]


def compare_products_data(
    conn: sqlite3.Connection,
    product_names: list[str],
    model_name: str,
    prompt_version: str = "v1",
) -> list[dict[str, Any]]:
    """지정된 제품 목록에 대해 리뷰 통계 및 키워드를 집계합니다."""
    results = []

    for prod in product_names:
        # 1. 리뷰 수 및 평균 별점
        stat_row = conn.execute("""
            SELECT 
                COUNT(*) AS total_reviews,
                AVG(rating) AS avg_rating
            FROM clean_reviews
            WHERE product_name = ?
        """, (prod,)).fetchone()

        total_reviews = int(stat_row["total_reviews"]) if stat_row else 0
        avg_rating = float(stat_row["avg_rating"]) if stat_row and stat_row["avg_rating"] is not None else 0.0

        # 2. 감정 분석 분포 (특정 model + prompt 기준)
        sentiment_rows = conn.execute("""
            SELECT 
                ar.sentiment,
                COUNT(*) AS count
            FROM clean_reviews cr
            JOIN analysis_results ar 
                ON ar.review_id = cr.id
               AND ar.model_name = ?
               AND ar.prompt_version = ?
            WHERE cr.product_name = ?
            GROUP BY ar.sentiment
        """, (model_name, prompt_version, prod)).fetchall()

        sent_counts = {"positive": 0, "neutral": 0, "negative": 0, "unknown": 0}
        for r in sentiment_rows:
            sent_counts[r["sentiment"]] = int(r["count"])

        analyzed_total = sum(sent_counts.values())
        
        pos_ratio = (sent_counts["positive"] / analyzed_total * 100) if analyzed_total > 0 else 0.0
        neu_ratio = (sent_counts["neutral"] / analyzed_total * 100) if analyzed_total > 0 else 0.0
        neg_ratio = (sent_counts["negative"] / analyzed_total * 100) if analyzed_total > 0 else 0.0

        # 3. extraction_results 테이블에서 키워드/요약 조회 (최신 1건)
        ext_row = conn.execute("""
            SELECT positive_keywords_json, negative_keywords_json, keywords_json, summary
            FROM extraction_results
            WHERE condition_json LIKE ?
            ORDER BY id DESC LIMIT 1
        """, (f'%"{prod}"%',)).fetchone()

        pos_keywords = []
        neg_keywords = []
        neu_keywords = []
        summary = "-"

        if ext_row:
            try:
                if ext_row["positive_keywords_json"]:
                    pos_keywords = json.loads(ext_row["positive_keywords_json"])
                if ext_row["negative_keywords_json"]:
                    neg_keywords = json.loads(ext_row["negative_keywords_json"])
                if ext_row["keywords_json"]:
                    all_kw = json.loads(ext_row["keywords_json"])
                    neu_keywords = [w for w in all_kw if w not in pos_keywords and w not in neg_keywords]
                if ext_row["summary"]:
                    summary = ext_row["summary"]
            except Exception:
                pass

        # extraction_results에 없을 경우 본문 텍스트 기반 보조 키워드 추출
        if not pos_keywords and not neg_keywords and not neu_keywords:
            raw_texts = conn.execute("""
                SELECT cleaned_text FROM clean_reviews 
                WHERE product_name = ? LIMIT 50
            """, (prod,)).fetchall()
            texts = [r["cleaned_text"] for r in raw_texts if r["cleaned_text"]]
            neu_keywords = _extract_simple_keywords(texts, top_n=3)

        results.append({
            "product_name": prod,
            "total_reviews": total_reviews,
            "analyzed_reviews": analyzed_total,
            "avg_rating": avg_rating,
            "positive_count": sent_counts["positive"],
            "neutral_count": sent_counts["neutral"],
            "negative_count": sent_counts["negative"],
            "positive_ratio": pos_ratio,
            "neutral_ratio": neu_ratio,
            "negative_ratio": neg_ratio,
            "positive_keywords": pos_keywords,
            "neutral_keywords": neu_keywords,
            "negative_keywords": neg_keywords,
            "summary": summary,
        })

    return results


def format_comparison_table(results: list[dict[str, Any]]) -> str:
    """비교 결과를 터미널에서 보기 좋은 표 형태로 포맷팅합니다."""
    if not results:
        return "비교할 제품 데이터가 없습니다."

    lines = []
    lines.append("=" * 78)
    lines.append("                   📊 제품별 리뷰 비교 분석 결과")
    lines.append("=" * 78)

    header = f"{'제품명':<16} | {'총리뷰':>6} | {'평균별점':>8} | {'긍정%':>7} | {'중립%':>7} | {'부정%':>7}"
    lines.append(header)
    lines.append("-" * 78)

    for r in results:
        rating_str = f"★ {r['avg_rating']:.2f}"
        pos_str = f"{r['positive_ratio']:.1f}%"
        neu_str = f"{r['neutral_ratio']:.1f}%"
        neg_str = f"{r['negative_ratio']:.1f}%"
        
        # 긴 제품명 자르기
        p_name = r["product_name"]
        if len(p_name) > 14:
            p_name = p_name[:12] + ".."

        row_str = f"{p_name:<16} | {r['total_reviews']:>6}건 | {rating_str:>8} | {pos_str:>8} | {neu_str:>8} | {neg_str:>8}"
        lines.append(row_str)

    lines.append("-" * 78)
    lines.append("📌 [제품별 감정 분포 및 주요 키워드/요약]")

    for r in results:
        pos_kw = ", ".join(r["positive_keywords"][:4]) or "-"
        neu_kw = ", ".join(r["neutral_keywords"][:4]) or "-"
        neg_kw = ", ".join(r["negative_keywords"][:4]) or "-"

        lines.append(f"\n▶ {r['product_name']}")
        lines.append(
            f"  · 감정 분포: 긍정 {r['positive_count']}건({r['positive_ratio']:.1f}%) | "
            f"중립 {r['neutral_count']}건({r['neutral_ratio']:.1f}%) | "
            f"부정 {r['negative_count']}건({r['negative_ratio']:.1f}%)"
        )
        lines.append(f"  · 긍정 키워드: {pos_kw}")
        lines.append(f"  · 중립/공통 키워드: {neu_kw}")
        lines.append(f"  · 부정 키워드: {neg_kw}")
        if r["summary"] != "-":
            lines.append(f"  · 요약: {r['summary']}")

    lines.append("=" * 78)
    return "\n".join(lines)