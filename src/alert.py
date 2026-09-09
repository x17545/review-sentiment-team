"""부정 감정 급증 알림 기능."""

from datetime import date, timedelta


def get_comparison_periods(
    end_date: date,
    days: int = 7,
) -> tuple[date, date, date, date]:
    """최근 기간과 직전 기간의 시작일/종료일을 계산한다."""
    if days < 1:
        raise ValueError("days는 1 이상이어야 합니다.")

    recent_end = end_date
    recent_start = recent_end - timedelta(days=days - 1)

    previous_end = recent_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=days - 1)

    return previous_start, previous_end, recent_start, recent_end


def get_negative_stats(
    conn,
    start_date: date,
    end_date: date,
    product_name: str | None = None,
) -> dict:
    """지정 기간의 분석된 리뷰 수와 부정 리뷰 비율을 계산한다."""
    query = """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN ar.sentiment = 'negative' THEN 1 ELSE 0 END) AS negative
        FROM clean_reviews cr
        JOIN analysis_results ar ON ar.review_id = cr.id
        WHERE cr.review_date BETWEEN ? AND ?
    """

    params = [start_date.isoformat(), end_date.isoformat()]

    if product_name:
        query += " AND cr.product_name = ?"
        params.append(product_name)

    row = conn.execute(query, params).fetchone()

    total = row[0] or 0
    negative = row[1] or 0
    negative_ratio = (negative / total * 100) if total else 0.0

    return {
        "total": total,
        "negative": negative,
        "negative_ratio": negative_ratio,
    }


def detect_negative_surge(
    conn,
    end_date: date,
    days: int = 7,
    threshold: float = 20.0,
    product_name: str | None = None,
) -> dict:
    """최근 기간의 부정률이 직전 기간보다 급증했는지 판정한다."""
    if threshold < 0:
        raise ValueError("threshold는 0 이상이어야 합니다.")

    previous_start, previous_end, recent_start, recent_end = get_comparison_periods(
        end_date=end_date,
        days=days,
    )

    previous = get_negative_stats(
        conn,
        previous_start,
        previous_end,
        product_name=product_name,
    )

    recent = get_negative_stats(
        conn,
        recent_start,
        recent_end,
        product_name=product_name,
    )

    has_enough_data = previous["total"] > 0 and recent["total"] > 0

    increase = recent["negative_ratio"] - previous["negative_ratio"]
    is_surge = has_enough_data and increase >= threshold

    return {
        "previous_start": previous_start.isoformat(),
        "previous_end": previous_end.isoformat(),
        "recent_start": recent_start.isoformat(),
        "recent_end": recent_end.isoformat(),
        "previous": previous,
        "recent": recent,
        "increase": increase,
        "threshold": threshold,
        "is_surge": is_surge,
        "has_enough_data": has_enough_data,
        "product_name": product_name,
    }