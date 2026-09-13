import hashlib
import re
from datetime import datetime


def normalize_text(text: str) -> str:
    """
    리뷰 텍스트를 정규화한다.

    규칙:
    1. None은 빈 문자열로 처리
    2. 문자열로 변환
    3. 앞뒤 공백 제거
    4. 연속된 공백/줄바꿈/탭을 한 칸으로 통일
    5. 반복된 !, ?, . 기호를 하나로 축약
    """
    if text is None:
        return ""

    text = str(text).strip()

    text = re.sub(r"\s+", " ", text)

    text = re.sub(r"!{2,}", "!", text)
    text = re.sub(r"\?{2,}", "?", text)
    text = re.sub(r"\.{2,}", ".", text)

    return text


def normalize_rating(rating):
    """
    별점을 1~5 범위의 float 값으로 정규화한다.
    유효하지 않은 값은 None으로 처리한다.
    """
    if rating is None:
        return None

    try:
        rating = float(rating)
    except (ValueError, TypeError):
        return None

    if 1 <= rating <= 5:
        return rating

    return None


def normalize_date(date_value):
    """
    날짜를 YYYY-MM-DD 형식으로 정규화한다.
    처리할 수 없는 값은 None으로 반환한다.
    """
    if date_value is None:
        return None

    date_text = str(date_value).strip()

    if not date_text:
        return None

    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y.%m.%d",
    ]

    for date_format in formats:
        try:
            parsed_date = datetime.strptime(date_text, date_format)
            return parsed_date.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None


def create_text_hash(text: str) -> str:
    """
    정규화된 리뷰 텍스트를 기준으로 SHA-256 해시를 생성한다.
    """
    normalized = normalize_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def clean_review(review: dict) -> dict:
    """
    collector에서 받은 리뷰 한 건을 정제한다.
    """
    cleaned_text = normalize_text(review.get("raw_text"))
    rating = normalize_rating(review.get("raw_rating"))
    review_date = normalize_date(review.get("raw_date"))

    raw_product = review.get("raw_product")
    product_name = (
        normalize_text(raw_product)
        if raw_product is not None
        else None
    )

    text_hash = create_text_hash(cleaned_text)

    return {
        "cleaned_text": cleaned_text,
        "rating": rating,
        "review_date": review_date,
        "product_name": product_name,
        "source_file": review.get("source_file"),
        "text_hash": text_hash,
    }


def clean_reviews(reviews: list[dict]) -> list[dict]:
    """
    여러 리뷰를 한 번에 정제한다.
    빈 리뷰는 제외한다.
    """
    cleaned_reviews = []

    for review in reviews:
        cleaned = clean_review(review)

        if not cleaned["cleaned_text"]:
            continue

        cleaned_reviews.append(cleaned)

    return cleaned_reviews


def run(
    db_path: str,
    config: dict,
    dedup_policy: str = "skip",
) -> dict:
    """
    raw_reviews의 데이터를 정제해서 clean_reviews에 저장한다.

    반환 예:
    {
        "processed": 10,
        "inserted": 8,
        "skipped": 2,
    }
    """
    from src.repository import (
        get_connection,
        get_raw_reviews_for_cleaning,
        insert_clean_review,
        mark_raw_processed,
    )

    processed = 0
    inserted = 0
    updated = 0
    skipped = 0

    min_review_length = config.get(
        "cleaning",
        {}
    ).get(
        "min_review_length",
        5
    )

    with get_connection(db_path) as conn:
        raw_reviews = get_raw_reviews_for_cleaning(conn)

        for row in raw_reviews:
            processed += 1

            review = {
                "raw_text": row["raw_text"],
                "raw_rating": row["raw_rating"],
                "raw_date": row["raw_date"],
                "raw_product": row["raw_product"],
                "source_file": row["source_file"],
            }

            cleaned = clean_review(review)

            if (
                not cleaned["cleaned_text"]
                or len(cleaned["cleaned_text"]) < min_review_length
            ):
                skipped += 1
                # [31번] 짧아서 제외한 raw도 '처리 시도 완료'로 표시(재조회 방지)
                mark_raw_processed(conn, row["id"])
                continue

            cleaned["raw_id"] = row["id"]

            result = insert_clean_review(
                conn,
                cleaned,
                dedup_policy=dedup_policy,
            )

            if result["inserted"]:
                inserted += 1
            elif result["duplicate"] and dedup_policy == "upsert":
                updated += 1
            else:
                skipped += 1

            # [31번] 저장이든 중복 skip이든 처리했으므로 표시(무한 재처리 방지)
            mark_raw_processed(conn, row["id"])

    return {
        "processed": processed,
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
    }