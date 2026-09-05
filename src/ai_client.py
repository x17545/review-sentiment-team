# src/ai_client.py
"""
ai_client 모듈 (미구현 스텁).
TODO: cli.py의 각 핸들러(# TODO 표시)에서 호출될 함수를 여기에 구현합니다.
"""
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

def analyze_sentiment(review_text: str) -> dict:
    try:
        response = client.responses.create(
            model="gpt-4o-mini",
            input=f"""
다음 고객 리뷰의 감정을 분석하세요.

리뷰:
{review_text}

반드시 아래 형식으로 답하세요.

sentiment: positive 또는 neutral 또는 negative
confidence: 0.0부터 1.0 사이 숫자
"""
        )

        text = response.output_text.strip()

        sentiment = "unknown"
        confidence = 0.0

        for line in text.splitlines():
            if line.startswith("sentiment:"):
                sentiment = line.split(":", 1)[1].strip()

            if line.startswith("confidence:"):
                confidence = float(line.split(":", 1)[1].strip())

        if sentiment not in {"positive", "neutral", "negative"}:
            return {
                "status": "failed",
                "sentiment": "unknown",
                "confidence": 0.0,
                "error": "invalid_sentiment",
            }

        if not 0.0 <= confidence <= 1.0:
            return {
                "status": "failed",
                "sentiment": "unknown",
                "confidence": 0.0,
                "error": "invalid_confidence",
            }

        return {
            "status": "success",
            "sentiment": sentiment,
            "confidence": confidence,
        }

    except Exception as e:
        return {
            "status": "failed",
            "sentiment": "unknown",
            "confidence": 0.0,
            "error": str(e),
        }
def extract_insights(review_texts: list[str]) -> dict:
    joined_reviews = "\n".join(
        f"- {text}" for text in review_texts
    )

    try:
        response = client.responses.create(
            model="gpt-4o-mini",
            input=f"""
다음 고객 리뷰들을 분석하세요.

리뷰 목록:
{joined_reviews}

다음 항목을 반드시 작성하세요.

positive_keywords: 긍정 키워드 3개
negative_keywords: 부정 키워드 3개
summary: 전체 리뷰 요약 1~2문장
suggestions: 개선 제안 3개

반드시 아래 형식을 지키세요.

positive_keywords: 키워드1 | 키워드2 | 키워드3
negative_keywords: 키워드1 | 키워드2 | 키워드3
summary: 요약 내용
suggestions: 제안1 | 제안2 | 제안3
"""
        )

        text = response.output_text.strip()

        positive_keywords = []
        negative_keywords = []
        summary = ""
        suggestions = []

        for line in text.splitlines():
            if line.startswith("positive_keywords:"):
                value = line.split(":", 1)[1].strip()
                positive_keywords = [
                    item.strip()
                    for item in value.split("|")
                    if item.strip()
                ]

            elif line.startswith("negative_keywords:"):
                value = line.split(":", 1)[1].strip()
                negative_keywords = [
                    item.strip()
                    for item in value.split("|")
                    if item.strip()
                ]

            elif line.startswith("summary:"):
                summary = line.split(":", 1)[1].strip()

            elif line.startswith("suggestions:"):
                value = line.split(":", 1)[1].strip()
                suggestions = [
                    item.strip()
                    for item in value.split("|")
                    if item.strip()
                ]

        return {
            "status": "success",
            "positive_keywords": positive_keywords,
            "negative_keywords": negative_keywords,
            "summary": summary,
            "suggestions": suggestions,
        }

    except Exception as e:
        return {
            "status": "failed",
            "positive_keywords": [],
            "negative_keywords": [],
            "summary": "",
            "suggestions": [],
            "error": str(e),
        }