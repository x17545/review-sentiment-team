import csv
import json
from pathlib import Path

from dotenv import load_dotenv

from src.ai_client import analyze_sentiment

INPUT_FILE = Path("prompt_validation.csv")
OUTPUT_FILE = Path("prompt_validation_results.csv")
CONFIG_FILE = Path("config.json")
PROMPT_VERSIONS = ("v1", "v2", "v3")


def load_config() -> dict:
    with CONFIG_FILE.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def load_validation_reviews() -> list[dict]:
    with INPUT_FILE.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    load_dotenv()

    config = load_config()
    ai_config = config["ai"]

    reviews = load_validation_reviews()
    results = []

    total_calls = len(reviews) * len(PROMPT_VERSIONS)
    current_call = 0

    print(f"검증 리뷰: {len(reviews)}건")
    print(f"비교 프롬프트: {', '.join(PROMPT_VERSIONS)}")
    print(f"총 AI 호출 예정: {total_calls}회")
    print()

    for prompt_version in PROMPT_VERSIONS:
        print(f"=== {prompt_version} 검증 시작 ===")

        for row in reviews:
            current_call += 1

            print(
                f"[{current_call}/{total_calls}] "
                f"리뷰 {row['review_id']} / {prompt_version}"
            )

            result = analyze_sentiment(
                review_text=row["review_text"],
                model_name=ai_config["model"],
                api_key_env=ai_config["api_key_env"],
                base_url=ai_config["base_url"],
                timeout=ai_config["timeout"],
                retry=ai_config["retry"],
                prompt_version=prompt_version,
            )

            ai_sentiment = result.get("sentiment", "unknown")
            confidence = result.get("confidence", 0.0)
            status = result.get("status", "failed")

            match = (
                status == "success"
                and ai_sentiment == row["human_label"]
            )

            results.append({
                "review_id": row["review_id"],
                "review_text": row["review_text"],
                "human_label": row["human_label"],
                "test_type": row["test_type"],
                "prompt_version": prompt_version,
                "ai_sentiment": ai_sentiment,
                "confidence": confidence,
                "match": match,
                "status": status,
                "error": result.get("error", ""),
            })

        print()

    fieldnames = [
        "review_id",
        "review_text",
        "human_label",
        "test_type",
        "prompt_version",
        "ai_sentiment",
        "confidence",
        "match",
        "status",
        "error",
    ]

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print("=== 검증 결과 요약 ===")

    for prompt_version in PROMPT_VERSIONS:
        version_results = [
            row
            for row in results
            if row["prompt_version"] == prompt_version
        ]

        successful = [
            row
            for row in version_results
            if row["status"] == "success"
        ]

        matched = [
            row
            for row in successful
            if row["match"]
        ]

        if successful:
            agreement_rate = (
                len(matched) / len(successful) * 100
            )
            avg_confidence = (
                sum(float(row["confidence"]) for row in successful)
                / len(successful)
            )
        else:
            agreement_rate = 0.0
            avg_confidence = 0.0

        print(
            f"{prompt_version}: "
            f"성공 {len(successful)}/{len(version_results)}건, "
            f"라벨 일치율 {agreement_rate:.1f}%, "
            f"평균 confidence {avg_confidence:.3f}"
        )

    print()
    print(f"상세 결과 저장: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
