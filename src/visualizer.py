"""
src/visualizer.py
대시보드 차트 생성 모듈 (Matplotlib 기반).
- 감정 분포 도넛 차트
- 시간별 감정 변화 추이 꺾은선 차트 (마커 겹침 방지 및 결측일 보정)
- 별점-감정 교차 분포 누적 막대 차트 (1~5점 축 고정)
"""

import os
import platform
import sqlite3
import matplotlib.pyplot as plt
import pandas as pd
import random


def setup_korean_font():
    """운영체제별 한글 폰트 설정 (폰트 깨짐 방지)"""
    system_name = platform.system()
    if system_name == "Windows":
        plt.rc("font", family="Malgun Gothic")
    elif system_name == "Darwin":
        plt.rc("font", family="AppleGothic")
    else:
        plt.rc("font", family="NanumGothic")
    plt.rc("axes", unicode_minus=False)


def fetch_dataframe_for_chart(db_path: str) -> pd.DataFrame:
    """DB에서 차트 생성용 데이터 조회 (데이터 부족 시 Mock 반환)"""
    try:
        from src.repository import get_connection
        with get_connection(db_path) as conn:
            query = """
                SELECT
                    c.id,
                    c.rating,
                    c.review_date,
                    a.sentiment,
                    a.confidence
                FROM clean_reviews c
                JOIN analysis_results a ON c.id = a.review_id
            """
            df = pd.read_sql_query(query, conn)
            if not df.empty:
                return df
            return _make_mock_data()
    except Exception as e:
        print(f"[경고] 차트용 DB 조회 실패, mock 사용: {e}")
        return _make_mock_data()


def _make_mock_data() -> pd.DataFrame:
    """DB에 데이터가 없을 때 파이프라인 검증용 Mock Data (시드 고정으로 데이터 일관성 보장)"""
    random.seed(42)  # 매 호출 시 동일한 난수 발생 (리포트/차트/엑셀 수치 일치)
    rows = []
    dates = [f"2026-08-{d:02d}" for d in range(1, 15)]
    sentiments = ["positive", "neutral", "negative"]
    weights = [0.5, 0.15, 0.35]

    for i in range(1, 121):
        date = random.choice(dates)
        sent = random.choices(sentiments, weights=weights)[0]
        if sent == "positive":
            rating = random.choice([4.0, 5.0])
        elif sent == "neutral":
            rating = 3.0
        else:
            rating = random.choice([1.0, 2.0])

        if random.random() < 0.05:
            rating = random.choice([1.0, 5.0])

        conf = round(random.uniform(0.6, 0.98), 2)

        rows.append({
            "id": i,
            "review_date": date,
            "sentiment": sent,
            "rating": rating,
            "confidence": conf,
        })

    return pd.DataFrame(rows)


def plot_sentiment_distribution(df: pd.DataFrame, output_dir: str) -> str:
    """1. 감정 분포 도넛 차트"""
    save_path = os.path.join(output_dir, "sentiment_distribution.png")
    
    order = ["positive", "neutral", "negative"]
    counts = df["sentiment"].value_counts().reindex(order).fillna(0)
    counts = counts[counts > 0]
    
    color_map = {"positive": "#4CAF50", "neutral": "#FFC107", "negative": "#F44336"}
    colors = [color_map.get(s, "#9E9E9E") for s in counts.index]
    labels = [s.capitalize() for s in counts.index]

    plt.figure(figsize=(7, 6))
    plt.pie(
        counts, 
        labels=labels, 
        autopct="%1.1f%%", 
        startangle=140, 
        colors=colors,
        wedgeprops=dict(width=0.4, edgecolor="w", linewidth=2)
    )
    plt.title("고객 리뷰 감정 분포 (Sentiment Distribution)", fontsize=13, pad=15, weight="bold")
    plt.tight_layout()
    plt.savefig(save_path, dpi=300)
    plt.close()
    return save_path


def plot_sentiment_trend(df: pd.DataFrame, output_dir: str) -> str:
    """2. 시간별 감정 변화 추이 꺾은선 차트"""
    save_path = os.path.join(output_dir, "sentiment_trend.png")
    temp_df = df.copy()
    temp_df["review_date"] = pd.to_datetime(temp_df["review_date"])

    trend = temp_df.groupby([temp_df["review_date"].dt.date, "sentiment"]).size().unstack(fill_value=0)

    if not trend.empty:
        all_dates = pd.date_range(start=trend.index.min(), end=trend.index.max()).date
        trend = trend.reindex(all_dates, fill_value=0)

    for s in ["positive", "neutral", "negative"]:
        if s not in trend.columns:
            trend[s] = 0

    plt.figure(figsize=(10, 5))
    
    styles = {
        "positive": {"color": "#4CAF50", "marker": "o", "markersize": 8, "alpha": 0.85},
        "neutral":  {"color": "#FFC107", "marker": "s", "markersize": 7, "alpha": 0.85},
        "negative": {"color": "#F44336", "marker": "^", "markersize": 8, "alpha": 0.85},
    }

    for col in ["positive", "neutral", "negative"]:
        cfg = styles[col]
        plt.plot(
            trend.index.astype(str), 
            trend[col], 
            marker=cfg["marker"], 
            markersize=cfg["markersize"],
            linewidth=2.2, 
            label=col.capitalize(), 
            color=cfg["color"],
            alpha=cfg["alpha"]
        )

    plt.title("일자별 감정 변화 추이 (Sentiment Trend)", fontsize=13, pad=15, weight="bold")
    plt.xlabel("리뷰 작성일", fontsize=10)
    plt.ylabel("리뷰 수", fontsize=10)
    
    max_val = int(trend[["positive", "neutral", "negative"]].max().max())
    plt.yticks(range(0, max(max_val + 2, 4)))
    
    plt.xticks(rotation=45)
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(title="Sentiment")
    plt.tight_layout()
    plt.savefig(save_path, dpi=300)
    plt.close()
    return save_path


def plot_rating_sentiment_matrix(df: pd.DataFrame, output_dir: str) -> str:
    """3. 별점별 감정 분포 누적 막대 차트"""
    save_path = os.path.join(output_dir, "rating_sentiment_matrix.png")
    
    pivot = pd.crosstab(df["rating"], df["sentiment"]).reindex(
        index=[1.0, 2.0, 3.0, 4.0, 5.0], fill_value=0
    )

    for c in ["positive", "neutral", "negative"]:
        if c not in pivot.columns:
            pivot[c] = 0

    pivot = pivot[["positive", "neutral", "negative"]]
    pivot.columns = [c.capitalize() for c in pivot.columns]

    colors = ["#4CAF50", "#FFC107", "#F44336"]

    ax = pivot.plot(
        kind="bar", 
        stacked=True, 
        figsize=(8, 6), 
        color=colors, 
        edgecolor="black", 
        alpha=0.85
    )
    
    plt.title("별점 대비 감정 분포 (Rating vs Sentiment)", fontsize=13, pad=15, weight="bold")
    plt.xlabel("별점 (Rating)", fontsize=10)
    plt.ylabel("리뷰 수", fontsize=10)
    
    max_y = int(pivot.sum(axis=1).max())
    ax.set_yticks(range(0, max(max_y + 2, 4)))
    
    plt.xticks(ticks=range(5), labels=["1.0", "2.0", "3.0", "4.0", "5.0"], rotation=0)
    plt.grid(axis="y", linestyle="--", alpha=0.5)
    plt.legend(title="Sentiment")
    plt.tight_layout()
    plt.savefig(save_path, dpi=300)
    plt.close()
    return save_path


def build_charts(db_path: str, output_dir: str = "output") -> list[str]:
    """메인 진입점"""
    setup_korean_font()
    os.makedirs(output_dir, exist_ok=True)
    df = fetch_dataframe_for_chart(db_path)

    return [
        plot_sentiment_distribution(df, output_dir),
        plot_sentiment_trend(df, output_dir),
        plot_rating_sentiment_matrix(df, output_dir),
    ]