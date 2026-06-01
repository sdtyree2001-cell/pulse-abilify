import json
from typing import Any

import anthropic

MODEL_NAME = "claude-opus-4-5"
MAX_TOKENS = 2000
WEB_SEARCH_TOOL = [{"type": "web_search_20250305", "name": "web_search"}]
TOPICS = [
    "Unmet Needs",
    "Place in Therapy",
    "Competitive Intelligence",
    "Access and Reimbursement",
    "Evidence Gaps",
    "Efficacy",
    "Safety",
    "Storage and Stability Issues",
    "Guideline Confusion",
    "Dosing and Administration",
    "Epidemiological Trends",
]

PRODUCT_CONTEXT = (
    "Product: Abilify (aripiprazole)\n"
    "Indication: Major Depressive Disorder (MDD) — adjunctive therapy to antidepressants\n"
    "Company: Otsuka Pharmaceuticals\n"
    "Audience: Medical Affairs Medical Director\n"
    "Key competitors: Spravato (esketamine, J&J), Exxua (gepirone, Aytu BioPharma), "
    "Auvelity (dextromethorphan-bupropion, Axsome), Rexulti (brexpiprazole, Otsuka/Lundbeck), "
    "generic aripiprazole, Vraylar (cariprazine, AbbVie)"
)


def _stream_to_text(response: Any) -> str:
    """Convert a streaming Anthropic response into text."""
    content = ""
    for event in response:
        if getattr(event, "type", None) == "response.output_text.delta":
            content += event.delta
    return content


def _clean_json_text(raw_text: str) -> str:
    """Strip markdown fences and whitespace before JSON parsing."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        cleaned = cleaned[3:-3].strip()
    if cleaned.startswith("json\n"):
        cleaned = cleaned[5:].strip()
    return cleaned


def _parse_json_safe(raw_text: str) -> dict[str, Any]:
    """Parse JSON safely, returning a fallback dict if parsing fails."""
    cleaned = _clean_json_text(raw_text)
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
        return {"parse_error": "Expected object, got different type", "raw_text": cleaned}
    except json.JSONDecodeError as exc:
        return {"parse_error": str(exc), "raw_text": cleaned}


def _build_prompt(topic: str) -> str:
    return (
        f"{PRODUCT_CONTEXT}\n\n"
        f"Search for the most recent signals for the topic: {topic}. "
        "Use web search to find developments in the last 7 days preferred, last 30 days acceptable. "
        "Find 2–3 distinct signals or developments. "
        "Return structured JSON only, no markdown or preamble, using the schema: "
        "{\n  \"topic\": \"string\",\n  \"signals\": [ ... ],\n  \"topic_trend\": \"accelerating|stable|decelerating\",\n  \"topic_summary\": \"One sentence summary...\"\n}\n"
        "Each signal must include headline, summary, significance, source_name, source_url, publication_date, signal_strength."
    )


def run_research(client: anthropic.Client, topics: list[str] | None = None) -> list[dict[str, Any]]:
    """Run research for each monitored topic and return structured results."""
    topics_to_run = topics or TOPICS
    results: list[dict[str, Any]] = []
    for index, topic in enumerate(topics_to_run, start=1):
        print(f"INFO: Researching topic {index}/{len(topics_to_run)}: {topic}")
        prompt = _build_prompt(topic)
        try:
            response = client.messages.stream(
                model=MODEL_NAME,
                tools=WEB_SEARCH_TOOL,
                max_tokens_to_sample=MAX_TOKENS,
                message=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )
            raw_text = _stream_to_text(response)
            parsed = _parse_json_safe(raw_text)
            if parsed.get("topic") != topic:
                parsed.setdefault("topic", topic)
            results.append(parsed)
        except Exception as exc:
            print(f"WARNING: Research failed for topic {topic}: {exc}")
            results.append({"topic": topic, "parse_error": str(exc), "signals": [], "topic_trend": "stable", "topic_summary": "Research failed."})
    return results
