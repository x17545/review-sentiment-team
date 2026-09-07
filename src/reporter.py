"""
src/reporter.py
품질 지표 계산, 종합 대시보드 리포트 생성 및 데이터 Export 모듈.
"""

import os
import json
import datetime
import pandas as pd
from typing import Optional


def calculate_metrics(df: pd.DataFrame) -> dict:
    """비즈니스 핵심 품질 지표 계산 (데이터가 없을 경우 0 처리)"""
    total = len(df)
    if total == 0:
        return {
            "total": 0,
            "pos_cnt": 0,
            "neu_cnt": 0,
            "neg_cnt": 0,
            "pos_ratio": 0.0,
            "neu_ratio": 0.0,
            "neg_ratio": 0.0,
            "avg_rating": 0.0,
            "avg_score": 0.0,
            "mismatch_rate": 0.0,
        }

    pos_cnt = (df["sentiment"] == "positive").sum()
    neu_cnt = (df["sentiment"] == "neutral").sum()
    neg_cnt = (df["sentiment"] == "negative").sum()

    pos_ratio = (pos_cnt / total * 100)
    neu_ratio = (neu_cnt / total * 100)
    neg_ratio = (neg_cnt / total * 100)

    mismatch = df[
        ((df["rating"] >= 4) & (df["sentiment"] == "negative")) |
        ((df["rating"] <= 2) & (df["sentiment"] == "positive"))
    ].shape[0]
    mismatch_rate = (mismatch / total * 100)

    return {
        "total": total,
        "pos_cnt": pos_cnt,
        "neu_cnt": neu_cnt,
        "neg_cnt": neg_cnt,
        "pos_ratio": pos_ratio,
        "neu_ratio": neu_ratio,
        "neg_ratio": neg_ratio,
        "avg_rating": df["rating"].mean() if "rating" in df.columns else 0.0,
        "avg_score": df["confidence"].mean() if "confidence" in df.columns else 0.0,
        "mismatch_rate": mismatch_rate,
    }


def fetch_extraction_data(db_path: str) -> dict:
    """extraction_results 테이블에서 최신 키워드 및 요약 정보 조회"""
    try:
        from src.repository import get_connection
        with get_connection(db_path) as conn:
            row = conn.execute("""
                SELECT positive_keywords_json, negative_keywords_json, summary, suggestions
                FROM extraction_results 
                ORDER BY id DESC LIMIT 1
            """).fetchone()
            
            if row and (row["positive_keywords_json"] or row["summary"]):
                pos_kw = json.loads(row["positive_keywords_json"] or "[]")
                neg_kw = json.loads(row["negative_keywords_json"] or "[]")
                return {
                    "pos_keywords": pos_kw,
                    "neg_keywords": neg_kw,
                    "summary": row["summary"] or "분석된 요약 정보가 없습니다.",
                    "suggestions": row["suggestions"] or "등록된 개선 제안이 없습니다.",
                }
    except Exception as e:
        print(f"[경고] 키워드 DB 조회 실패: {e}")

    return {
        "pos_keywords": [],
        "neg_keywords": [],
        "summary": "추출된 AI 인사이트 데이터가 없습니다. (추출 파이프라인 실행 필요)",
        "suggestions": "추출 파이프라인을 먼저 실행해 주세요.",
    }


def build_report(
    db_path: str,
    output_dir: str = "output",
    chart_paths: list[str] = None,
    use_mock: bool = False
) -> str:
    """대시보드 리포트 텍스트 생성기 (데이터 유무에 따른 분기 처리)"""
    os.makedirs(output_dir, exist_ok=True)
    
    from src.visualizer import fetch_dataframe_for_chart
    df = fetch_dataframe_for_chart(db_path, use_mock=use_mock)
    ai_data = fetch_extraction_data(db_path)
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if df.empty:
        report = f"""============================================================
         고객 리뷰 감정 분석 대시보드
         생성일시: {now_str}
         분석 기간: 데이터 없음
============================================================

[핵심 지표]
(분석된 리뷰 데이터가 없습니다. 파이프라인을 먼저 실행해 주세요.)

[AI 인사이트 요약]
{ai_data['summary']}

[생성된 차트 파일]
(분석 데이터가 없어 차트가 생성되지 않았습니다)
============================================================
"""
    else:
        metrics = calculate_metrics(df)
        date_min = df["review_date"].min() if "review_date" in df.columns else "N/A"
        date_max = df["review_date"].max() if "review_date" in df.columns else "N/A"

        report = f"""============================================================
         고객 리뷰 감정 분석 대시보드
         생성일시: {now_str}
         분석 기간: {date_min} ~ {date_max}
============================================================

[핵심 지표]
┌──────────────────┬───────────────┐
│ 총 리뷰 수       │ {metrics['total']:>10} 건  │
│ 긍정 비율        │ {metrics['pos_ratio']:>10.1f} %  │
│ 중립 비율        │ {metrics['neu_ratio']:>10.1f} %  │
│ 부정 비율        │ {metrics['neg_ratio']:>10.1f} %  │
│ 평균 별점        │ {metrics['avg_rating']:>10.2f} 점  │
│ 평균 신뢰도 점수 │ {metrics['avg_score']:>10.2f}    │
│ 별점-감정 괴리율 │ {metrics['mismatch_rate']:>10.1f} %  │
└──────────────────┴───────────────┘

[TOP 5 긍정 키워드]
"""
        if ai_data["pos_keywords"]:
            for i, item in enumerate(ai_data["pos_keywords"][:5], 1):
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    report += f"{i}. {item[0]} ({item[1]}회)\n"
                else:
                    report += f"{i}. {item}\n"
        else:
            report += "(추출된 긍정 키워드가 없습니다)\n"

        report += "\n[TOP 5 부정 키워드]\n"
        if ai_data["neg_keywords"]:
            for i, item in enumerate(ai_data["neg_keywords"][:5], 1):
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    report += f"{i}. {item[0]} ({item[1]}회)\n"
                else:
                    report += f"{i}. {item}\n"
        else:
            report += "(추출된 부정 키워드가 없습니다)\n"

        report += f"""
[AI 인사이트 요약]
{ai_data['summary']}

[개선 제안]
{ai_data['suggestions']}

[생성된 차트 파일]
"""
        if chart_paths:
            for p in chart_paths:
                report += f"- {p}\n"
        else:
            report += "(생성된 차트 파일 없음)\n"

        report += "============================================================\n"

    print(report)

    txt_path = os.path.join(output_dir, "dashboard_report.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(report)

    return txt_path


def export(
    db_path: str,
    format: str,
    sentiment: Optional[str] = None,
    rating_min: Optional[int] = None,
    output: str = "output",
    use_mock: bool = False
) -> str:
    """내보내기 함수 (데이터가 없으면 Mock을 자동 주입하지 않고 안내 후 빈 파일 생성)"""
    os.makedirs(output, exist_ok=True)
    
    if use_mock:
        from src.visualizer import fetch_dataframe_for_chart
        df = fetch_dataframe_for_chart(db_path, use_mock=True)
    else:
        df = pd.DataFrame()
        try:
            from src.repository import get_connection
            with get_connection(db_path) as conn:
                query = """
                    SELECT 
                        c.id,
                        c.cleaned_text,
                        c.rating,
                        c.review_date,
                        c.product_name,
                        a.sentiment,
                        a.confidence
                    FROM clean_reviews c
                    JOIN analysis_results a ON c.id = a.review_id
                """
                df = pd.read_sql_query(query, conn)
        except Exception:
            pass

    if df.empty:
        print("[안내] DB에 내보낼 분석 데이터가 없습니다. 빈 템플릿으로 저장합니다.")
        columns = ["id", "cleaned_text", "rating", "review_date", "product_name", "sentiment", "confidence"]
        df = pd.DataFrame(columns=columns)
    else:
        if sentiment and "sentiment" in df.columns:
            df = df[df["sentiment"] == sentiment]
        if rating_min is not None and "rating" in df.columns:
            df = df[df["rating"] >= rating_min]

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    file_ext = "xlsx" if format == "excel" else format
    filename = f"exported_reviews_{timestamp}.{file_ext}"
    export_path = os.path.join(output, filename)

    if format == "csv":
        df.to_csv(export_path, index=False, encoding="utf-8-sig")
    elif format == "excel":
        df.to_excel(export_path, index=False, engine="openpyxl")
    elif format == "jsonl":
        df.to_json(export_path, orient="records", lines=True, force_ascii=False)
    else:
        raise ValueError(f"지원하지 않는 포맷입니다: {format}")

    print(f"[export 완료] {len(df)}건의 데이터가 저장되었습니다: {export_path}")
    return export_path