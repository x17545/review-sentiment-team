from pathlib import Path

import pandas as pd


def load_review_file(file_path: str) -> pd.DataFrame:
    """
    CSV 또는 Excel 리뷰 파일을 읽어서 DataFrame으로 반환한다.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

    suffix = path.suffix.lower()

    if suffix == ".csv":
        return pd.read_csv(path)

    if suffix in [".xlsx", ".xls"]:
        return pd.read_excel(path)

    raise ValueError(
        f"지원하지 않는 파일 형식입니다: {suffix} "
        f"(지원 형식: .csv, .xlsx, .xls)"
    )


def find_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """
    후보 컬럼명 중 실제 DataFrame에 존재하는 컬럼을 찾는다.
    대소문자 차이는 무시한다.
    """
    column_map = {
        str(column).strip().lower(): column
        for column in df.columns
    }

    for candidate in candidates:
        key = candidate.strip().lower()

        if key in column_map:
            return column_map[key]

    return None


def map_review_columns(
    df: pd.DataFrame,
    column_config: dict
) -> dict:
    """
    config.json의 columns 설정을 기준으로
    리뷰/별점/날짜/상품명 컬럼을 찾는다.
    """
    mapped = {}

    for field_name, candidates in column_config.items():
        mapped[field_name] = find_column(df, candidates)

    if mapped.get("text") is None:
        raise ValueError(
            "리뷰 내용 컬럼을 찾을 수 없습니다. "
            "config.json의 columns.text 설정을 확인하세요."
        )

    return mapped


def collect_reviews(
    file_path: str,
    column_config: dict
) -> list[dict]:
    """
    리뷰 파일을 읽고 컬럼을 표준 형식으로 변환한다.
    """
    df = load_review_file(file_path)
    mapped = map_review_columns(df, column_config)

    reviews = []

    for _, row in df.iterrows():
        review = {
            "raw_text": row[mapped["text"]],
            "raw_rating": (
                row[mapped["rating"]]
                if mapped.get("rating") is not None
                else None
            ),
            "raw_date": (
                row[mapped["date"]]
                if mapped.get("date") is not None
                else None
            ),
            "raw_product": (
                row[mapped["product"]]
                if mapped.get("product") is not None
                else None
            ),
            "source_file": Path(file_path).name,
        }

        reviews.append(review)

    return reviews


def read_reviews(file_path: str, config: dict) -> list[dict]:
    """
    CLI에서 사용하는 리뷰 파일 읽기 함수.

    config.json 전체 설정을 받아 columns 설정을 사용해
    리뷰 데이터를 표준 형식으로 변환한다.
    """
    column_config = config.get("columns", {})

    return collect_reviews(
        file_path=file_path,
        column_config=column_config,
    )