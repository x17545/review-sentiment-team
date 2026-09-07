# src/analyzer.py

"""
AI 분석 업무 흐름을 담당하는 모듈입니다.

역할:
- AI 감정분석 호출
- 여러 리뷰 분석
- DB 분석 대상 조회
- 분석 결과 저장
- 인사이트 추출 및 저장
"""

import json

from src.ai_client import (
    analyze_sentiment,
    extract_insights,
)
from src.repository import (
    get_connection,
    get_reviews_for_analysis,
    insert_analysis_result,
    get_reviews_for_extraction,
    insert_extraction_result,
)


def analyze_review(
    review_text: str,
    model_name: str,
    api_key_env: str,
    base_url: str,
    timeout: float,
    retry: int,
) -> dict:
    """
    리뷰 1건을 AI로 분석합니다.
    """

    return analyze_sentiment(
        review_text=review_text,
        model_name=model_name,
        api_key_env=api_key_env,
        base_url=base_url,
        timeout=timeout,
        retry=retry,
    )


def analyze_reviews(
    review_texts: list[str],
    model_name: str,
    api_key_env: str,
    base_url: str,
    timeout: float,
    retry: int,
) -> list[dict]:
    """
    여러 리뷰를 순서대로 분석합니다.

    특정 리뷰에서 실패해도
    나머지 리뷰 분석을 계속 진행합니다.
    """

    results = []

    for review_text in review_texts:
        try:
            result = analyze_review(
                review_text=review_text,
                model_name=model_name,
                api_key_env=api_key_env,
                base_url=base_url,
                timeout=timeout,
                retry=retry,
            )

            results.append({
                "review_text": review_text,
                **result,
            })

        except Exception as e:
            results.append({
                "review_text": review_text,
                "status": "failed",
                "sentiment": "unknown",
                "confidence": 0.0,
                "error": str(e),
            })

    return results


def extract_review_insights(
    review_texts: list[str],
    model_name: str,
    api_key_env: str,
    base_url: str,
    timeout: float,
    retry: int,
) -> dict:
    """
    여러 리뷰의 인사이트를 추출합니다.
    """

    return extract_insights(
        review_texts=review_texts,
        model_name=model_name,
        api_key_env=api_key_env,
        base_url=base_url,
        timeout=timeout,
        retry=retry,
    )


def analyze_reviews_from_db(
    db_path: str,
    model_name: str,
    api_key_env: str,
    base_url: str,
    timeout: float,
    retry: int,
    prompt_version: str = "v1",
    review_id: int | None = None,
    analyze_all: bool = False,
    limit: int | None = None,
) -> list[dict]:
    """
    DB에서 분석 대상 리뷰를 가져와 AI 분석 후 저장합니다.
    """

    results = []

    with get_connection(db_path) as conn:
        rows = get_reviews_for_analysis(
            conn,
            review_id=review_id,
            analyze_all=analyze_all,
            model_name=model_name,
            prompt_version=prompt_version,
            limit=limit,
        )

        for row in rows:
            result = analyze_sentiment(
                review_text=row["cleaned_text"],
                model_name=model_name,
                api_key_env=api_key_env,
                base_url=base_url,
                timeout=timeout,
                retry=retry,
            )

            if result.get("status") != "success":
                results.append({
                    "review_id": row["id"],
                    **result,
                })
                continue

            saved = insert_analysis_result(
                conn,
                review_id=row["id"],
                sentiment=result["sentiment"],
                confidence=result["confidence"],
                model_name=model_name,
                prompt_version=prompt_version,
                raw_response=result.get("raw_response"),
            )

            results.append({
                "review_id": row["id"],
                **result,
                **saved,
            })

    return results


def extract_insights_from_db(
    db_path: str,
    model_name: str,
    api_key_env: str,
    base_url: str,
    timeout: float,
    retry: int,
    prompt_version: str = "v1",
    sentiment: str | None = None,
    product: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int | None = None,
) -> dict:
    """
    DB에서 조건에 맞는 리뷰를 조회하여
    인사이트를 추출하고 DB에 저장합니다.
    """

    with get_connection(db_path) as conn:
        rows = get_reviews_for_extraction(
            conn,
            sentiment=sentiment,
            product=product,
            date_from=date_from,
            date_to=date_to,
            model_name=model_name,
            prompt_version=prompt_version,
            limit=limit,
        )

        review_texts = [
            row["cleaned_text"]
            for row in rows
        ]

        review_ids = [
            row["id"]
            for row in rows
        ]

        if not review_texts:
            return {
                "status": "failed",
                "error": "no_reviews",
            }

        result = extract_insights(
            review_texts=review_texts,
            model_name=model_name,
            api_key_env=api_key_env,
            base_url=base_url,
            timeout=timeout,
            retry=retry,
        )

        if result.get("status") != "success":
            return result

        condition = {
            "sentiment": sentiment,
            "product": product,
            "date_from": date_from,
            "date_to": date_to,
            "limit": limit,
        }

        extraction_id = insert_extraction_result(
            conn,
            model_name=model_name,
            prompt_version=prompt_version,
            condition_json=json.dumps(
                condition,
                ensure_ascii=False,
            ),
            review_ids_json=json.dumps(
                review_ids,
                ensure_ascii=False,
            ),
            positive_keywords_json=json.dumps(
                result["positive_keywords"],
                ensure_ascii=False,
            ),
            negative_keywords_json=json.dumps(
                result["negative_keywords"],
                ensure_ascii=False,
            ),
            summary=result["summary"],
            suggestions=json.dumps(
                result["suggestions"],
                ensure_ascii=False,
            ),
            raw_response=result.get("raw_response"),
        )

        return {
            **result,
            "extraction_id": extraction_id,
            "review_count": len(review_ids),
        }