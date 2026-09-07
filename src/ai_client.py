# src/ai_client.py

import os

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)


def analyze_sentiment(review_text: str, model_name: str) -> dict:
    """
    리뷰 1건의 감정을 분석합니다.
    model_name은 config.json의 ai.model 값을 전달받아 사용합니다.
    """
    try:
        response = client.responses.create(
            model=model_name,
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


def extract_insights(review_texts: list[str], model_name: str) -> dict:
    """
    여러 리뷰에서 긍정/부정 키워드, 요약, 개선 제안을 추출합니다.
    model_name은 config.json의 ai.model 값을 전달받아 사용합니다.
    """
    joined_reviews = "\n".join(
        f"- {text}" for text in review_texts
    )

    try:
        response = client.responses.create(
            model=model_name,
            input=f"""
다음 고객 리뷰들을 분석하세요.

리뷰 목록:
{joined_reviews}

다음 항목을 반드시 작성하세요.

positive_keywords: 긍정 키워드 3개
negative_keywords: 부정 키워드 3개
summary: 전체 리뷰 요약 1~2문장
suggestions: 개선 제안 3개

반드시 아래 형식을 지켜주세요.

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

        if not summary:
            return {
                "status": "failed",
                "error": "invalid_summary",
            }

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
            "error": str(e),
        }