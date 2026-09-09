# src/ai_client.py

"""
OpenAI 호환 AI API 호출 모듈입니다.

Codyssey API는 /v1/responses 대신
/v1/chat/completions 방식을 사용합니다.

AI 설정값은 config.json에서 analyzer.py를 거쳐 전달받습니다.
"""

import os

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


def create_client(
    api_key_env: str,
    base_url: str,
    timeout: float,
    retry: int,
) -> OpenAI:
    """
    config.json의 AI 설정값으로 OpenAI 호환 클라이언트를 생성합니다.
    """

    api_key = os.getenv(api_key_env)

    if not api_key:
        raise RuntimeError(
            f"환경변수 '{api_key_env}'에 API 키가 설정되어 있지 않습니다."
        )

    return OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
        max_retries=retry,
    )


def get_message_content(response) -> str:
    """
    Chat Completions API 응답에서 텍스트 내용을 안전하게 가져옵니다.
    """

    if not response.choices:
        raise ValueError("AI 응답에 choices가 없습니다.")

    content = response.choices[0].message.content

    if not content:
        raise ValueError("AI 응답 내용이 비어 있습니다.")

    return content.strip()


def analyze_sentiment(
    review_text: str,
    model_name: str,
    api_key_env: str,
    base_url: str,
    timeout: float,
    retry: int,
) -> dict:
    """
    리뷰 1건을 감정분석합니다.

    반환 형식:
    {
        "status": "success",
        "sentiment": "positive | neutral | negative",
        "confidence": 0.0 ~ 1.0
    }
    """

    try:
        client = create_client(
            api_key_env=api_key_env,
            base_url=base_url,
            timeout=timeout,
            retry=retry,
        )

        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "당신은 고객 리뷰 감정분석 도우미입니다. "
                        "요청된 출력 형식을 정확히 지켜주세요."
                    ),
                },
                {
                    "role": "user",
                    "content": f"""
다음 고객 리뷰의 감정을 분석하세요.
리뷰는 한국어, 영어, 일본어, 러시아어 등 어떤 언어로 작성되어 있어도 동일하게 분석하세요.

리뷰:
{review_text}

반드시 아래 형식으로만 답하세요.

sentiment: positive 또는 neutral 또는 negative
confidence: 0.0부터 1.0 사이 숫자
""".strip(),
                },
            ],
        )

        text = get_message_content(response)

        sentiment = "unknown"
        confidence = 0.0

        for line in text.splitlines():
            line = line.strip()

            if line.startswith("sentiment:"):
                sentiment = line.split(":", 1)[1].strip().lower()

            elif line.startswith("confidence:"):
                confidence_text = line.split(":", 1)[1].strip()
                confidence = float(confidence_text)

        if sentiment not in {
            "positive",
            "neutral",
            "negative",
        }:
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
            "raw_response": text,
        }

    except Exception as e:
        return {
            "status": "failed",
            "sentiment": "unknown",
            "confidence": 0.0,
            "error": str(e),
        }


def extract_insights(
    review_texts: list[str],
    model_name: str,
    api_key_env: str,
    base_url: str,
    timeout: float,
    retry: int,
) -> dict:
    """
    여러 리뷰에서 다음 정보를 추출합니다.

    - 긍정 키워드
    - 부정 키워드
    - 전체 요약
    - 개선 제안
    """

    if not review_texts:
        return {
            "status": "failed",
            "error": "no_reviews",
        }

    joined_reviews = "\n".join(
        f"- {text}"
        for text in review_texts
    )

    try:
        client = create_client(
            api_key_env=api_key_env,
            base_url=base_url,
            timeout=timeout,
            retry=retry,
        )

        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "당신은 고객 리뷰 분석 도우미입니다. "
                        "여러 리뷰를 종합하여 핵심 키워드, 요약, "
                        "개선 제안을 작성합니다."
                    ),
                },
                {
                    "role": "user",
                    "content": f"""
다음 고객 리뷰의 감정을 분석하세요.
리뷰는 언어와 무관하게 분석하되, 키워드와 요약은 한국어로 작성하세요.

리뷰 목록:
{joined_reviews}

다음 항목을 작성하세요.

positive_keywords: 긍정 키워드 3개
negative_keywords: 부정 키워드 3개
summary: 전체 리뷰 요약 1~2문장
suggestions: 개선 제안 3개

반드시 아래 형식으로만 답하세요.

positive_keywords: 키워드1 | 키워드2 | 키워드3
negative_keywords: 키워드1 | 키워드2 | 키워드3
summary: 요약 내용
suggestions: 제안1 | 제안2 | 제안3
""".strip(),
                },
            ],
        )

        text = get_message_content(response)

        positive_keywords = []
        negative_keywords = []
        summary = ""
        suggestions = []

        for line in text.splitlines():
            line = line.strip()

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
                "raw_response": text,
            }

        return {
            "status": "success",
            "positive_keywords": positive_keywords,
            "negative_keywords": negative_keywords,
            "summary": summary,
            "suggestions": suggestions,
            "raw_response": text,
        }

    except Exception as e:
        return {
            "status": "failed",
            "error": str(e),
        }