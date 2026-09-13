"""
src/reporter.py
품질 지표 계산, 종합 대시보드 리포트 생성 및 데이터 Export 모듈.
"""

import os
import json
import base64
import datetime
import html
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


def _img_to_base64(path: str) -> Optional[str]:
    """PNG 파일을 base64 data URI로 변환. 파일이 없으면 None."""
    if not path or not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _parse_list_field(value) -> list:
    """키워드/제안 필드를 리스트로 정규화 (JSON 배열 문자열이면 파싱)."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("["):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
        return [text] if text else []
    return [str(value)]


def fetch_recent_reviews(db_path: str, limit: int = 10) -> list[dict]:
    """최근 리뷰 목록을 조회한다."""
    from src.repository import get_connection

    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                cr.review_date,
                cr.product_name,
                cr.rating,
                ar.sentiment,
                cr.cleaned_text
            FROM clean_reviews cr
            LEFT JOIN analysis_results ar
                ON ar.review_id = cr.id
            ORDER BY cr.review_date DESC, cr.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]


def build_recent_reviews_html(reviews: list[dict]) -> str:
    """최근 리뷰 목록을 HTML 테이블 행으로 변환한다."""
    if not reviews:
        return (
            '<tr>'
            '<td colspan="5" class="empty">최근 리뷰가 없습니다.</td>'
            '</tr>'
        )

    rows = []

    for review in reviews:
        review_date = html.escape(str(review.get("review_date", "")))
        product_name = html.escape(str(review.get("product_name", "")))
        rating = html.escape(str(review.get("rating", "")))
        sentiment = html.escape(str(review.get("sentiment", "")))
        cleaned_text = html.escape(str(review.get("cleaned_text", "")))

        rows.append(
            "<tr>"
            f"<td>{review_date}</td>"
            f"<td>{product_name}</td>"
            f"<td>{rating}</td>"
            f"<td>{sentiment}</td>"
            f"<td>{cleaned_text}</td>"
            "</tr>"
        )

    return "".join(rows)


def build_html_report(
    db_path: str,
    output_dir: str = "output",
    chart_paths: list[str] = None,
    use_mock: bool = False,
) -> str:
    """
    단일 HTML 대시보드를 생성한다.
    차트 PNG는 base64로 HTML 안에 직접 삽입하므로, 생성된 HTML 파일 하나만
    있으면 어디서든 차트까지 완전하게 보인다(단일 파일).
    """
    os.makedirs(output_dir, exist_ok=True)

    from src.visualizer import fetch_dataframe_for_chart
    df = fetch_dataframe_for_chart(db_path, use_mock=use_mock)
    ai_data = fetch_extraction_data(db_path)
    recent_reviews = fetch_recent_reviews(db_path, limit=10)
    recent_reviews_html = build_recent_reviews_html(recent_reviews)
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html_path = os.path.join(output_dir, "dashboard.html")

    if df.empty:
        html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<title>고객 리뷰 감정 분석 대시보드</title>
<style>{_HTML_STYLE}</style></head>
<body><div class="wrap">
<h1>고객 리뷰 감정 분석 대시보드</h1>
<p class="meta">생성일시: {now_str}</p>
<div class="card"><p class="empty">분석된 리뷰 데이터가 없습니다. 파이프라인을 먼저 실행해 주세요.</p></div>
</div></body></html>"""
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        return html_path

    metrics = calculate_metrics(df)
    date_min = df["review_date"].min() if "review_date" in df.columns else "N/A"
    date_max = df["review_date"].max() if "review_date" in df.columns else "N/A"

    metric_items = [
        ("총 리뷰 수", f"{metrics['total']}건"),
        ("긍정 비율", f"{metrics['pos_ratio']:.1f}%"),
        ("중립 비율", f"{metrics['neu_ratio']:.1f}%"),
        ("부정 비율", f"{metrics['neg_ratio']:.1f}%"),
        ("평균 별점", f"{metrics['avg_rating']:.2f}점"),
        ("평균 신뢰도", f"{metrics['avg_score']:.2f}"),
        ("별점-감정 괴리율", f"{metrics['mismatch_rate']:.1f}%"),
    ]
    metric_html = "".join(
        f'<div class="metric"><span class="mlabel">{k}</span>'
        f'<span class="mvalue">{v}</span></div>'
        for k, v in metric_items
    )

    def kw_list(items):
        out = []
        for it in items[:5]:
            if isinstance(it, (list, tuple)) and len(it) >= 2:
                out.append(f"<li>{it[0]} <span class='cnt'>({it[1]}회)</span></li>")
            else:
                out.append(f"<li>{it}</li>")
        return "".join(out) or "<li class='empty'>(없음)</li>"

    pos_html = kw_list(ai_data["pos_keywords"])
    neg_html = kw_list(ai_data["neg_keywords"])

    suggestions = _parse_list_field(ai_data.get("suggestions"))
    sug_html = "".join(f"<li>{s}</li>" for s in suggestions) or "<li class='empty'>(없음)</li>"

    chart_paths = chart_paths or []
    chart_html = ""
    chart_titles = {
        "sentiment_distribution": "감정 분포",
        "sentiment_trend": "일자별 감정 추이",
        "rating_sentiment_matrix": "별점 대비 감정 분포",
    }
    for p in chart_paths:
        uri = _img_to_base64(p)
        if uri is None:
            continue
        stem = os.path.splitext(os.path.basename(p))[0]
        title = chart_titles.get(stem, stem)
        chart_html += f'<div class="chart"><h3>{title}</h3><img src="{uri}" alt="{title}"></div>'
    if not chart_html:
        chart_html = '<p class="empty">생성된 차트가 없습니다.</p>'

    html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<title>고객 리뷰 감정 분석 대시보드</title>
<style>{_HTML_STYLE}</style></head>
<body><div class="wrap">
<h1>고객 리뷰 감정 분석 대시보드</h1>
<p class="meta">생성일시: {now_str} &nbsp;|&nbsp; 분석 기간: {date_min} ~ {date_max}</p>

<div class="card">
  <h2>핵심 지표</h2>
  <div class="metrics">{metric_html}</div>
</div>

<div class="grid2">
  <div class="card"><h2>TOP 긍정 키워드</h2><ul class="kw pos">{pos_html}</ul></div>
  <div class="card"><h2>TOP 부정 키워드</h2><ul class="kw neg">{neg_html}</ul></div>
</div>

<div class="card">
  <h2>AI 인사이트 요약</h2>
  <p class="summary">{ai_data['summary']}</p>
  <h2>개선 제안</h2>
  <ul class="sug">{sug_html}</ul>
</div>

<div class="card">
  <h2>차트</h2>
  <div class="charts">{chart_html}</div>
</div>

<div class="card">
  <h2>최근 리뷰</h2>
  <div class="table-wrap">
    <table class="review-table">
      <thead>
        <tr>
          <th>날짜</th>
          <th>제품</th>
          <th>별점</th>
          <th>감정</th>
          <th>리뷰</th>
        </tr>
      </thead>
      <tbody>
        {recent_reviews_html}
      </tbody>
    </table>
  </div>
</div>

<p class="foot">본 분석 결과는 입력 리뷰 데이터의 품질과 분포에 영향을 받으며, 참고 자료로 활용하시기 바랍니다.</p>
</div></body></html>"""

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    return html_path


_HTML_STYLE = """
* { box-sizing: border-box; }
body { margin:0; background:#f4f5f7; color:#1a1a1a;
  font-family:'Malgun Gothic','Apple SD Gothic Neo',sans-serif; }
.wrap { max-width:960px; margin:0 auto; padding:32px 20px 60px; }
h1 { font-size:24px; margin:0 0 4px; }
.meta { color:#666; font-size:13px; margin:0 0 24px; }
.card { background:#fff; border-radius:12px; padding:20px 24px; margin-bottom:20px;
  box-shadow:0 1px 3px rgba(0,0,0,.08); }
.card h2 { font-size:16px; margin:0 0 14px; padding-bottom:8px; border-bottom:1px solid #eee; }
.grid2 { display:grid; grid-template-columns:1fr 1fr; gap:20px; }
.metrics { display:grid; grid-template-columns:repeat(auto-fit,minmax(120px,1fr)); gap:12px; }
.metric { display:flex; flex-direction:column; gap:4px; padding:12px; background:#fafafa; border-radius:8px; }
.mlabel { font-size:12px; color:#777; }
.mvalue { font-size:20px; font-weight:700; }
ul { margin:0; padding-left:20px; line-height:1.9; }
.kw.pos li::marker { color:#4CAF50; }
.kw.neg li::marker { color:#F44336; }
.cnt { color:#999; font-size:13px; }
.summary { line-height:1.7; margin:0 0 8px; }
.sug li { margin-bottom:4px; }
.charts { display:flex; flex-direction:column; gap:24px; }
.chart h3 { font-size:14px; color:#555; margin:0 0 8px; }
.chart img { width:100%; height:auto; border:1px solid #eee; border-radius:8px; }
.empty { color:#999; }
.table-wrap {
  overflow-x: auto;
}

.review-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.review-table th,
.review-table td {
  padding: 10px 12px;
  border-bottom: 1px solid #eee;
  text-align: left;
  vertical-align: top;
}

.review-table th {
  background: #fafafa;
  font-weight: 700;
  white-space: nowrap;
}

.review-table td:nth-child(1),
.review-table td:nth-child(3),
.review-table td:nth-child(4) {
  white-space: nowrap;
}
.foot { color:#999; font-size:12px; text-align:center; margin-top:32px; }
@media(max-width:640px){ .grid2{grid-template-columns:1fr;} }
"""


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