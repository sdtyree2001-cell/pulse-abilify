import json
from datetime import date
from typing import Any

import anthropic

MODEL_NAME = "claude-opus-4-5"
MAX_TOKENS = 200

COLOR_MAP = {
    "high": "#8B2635",
    "medium": "#B5540A",
    "low": "#4A6741",
}
TREND_BADGES = {
    "accelerating": ("↑↑", "#8B2635"),
    "stable": ("→", "#0D6E6E"),
    "decelerating": ("↓", "#B5540A"),
}


def _build_prompt(topic: str, signals: list[dict[str, Any]]) -> str:
    return (
        f"Write exactly two sentences synthesizing the verified signals for the topic '{topic}' in the context of Abilify (aripiprazole) as adjunctive MDD therapy. "
        "Be direct, actionable, and omit filler language. Return only two sentences."
    )


def _ask_for_narrative(client: anthropic.Client, topic: str, signals: list[dict[str, Any]]) -> str:
    prompt = _build_prompt(topic, signals)
    try:
        response = client.responses.create(
            model=MODEL_NAME,
            max_tokens_to_sample=MAX_TOKENS,
            input=prompt,
        )
        output_text = response.output[0].content[0].text
        return output_text.strip()
    except Exception as exc:
        print(f"WARNING: Narrative generation failed for topic {topic}: {exc}")
        return "No narrative available due to generation error."


def _format_signal_card(signal: dict[str, Any]) -> str:
    strength = signal.get("signal_strength", "low")
    border_color = COLOR_MAP.get(strength, "#4A6741")
    headline = signal.get("headline", "Unknown headline")
    summary = signal.get("summary", "")
    significance = signal.get("significance", "")
    source_name = signal.get("source_name", "Source")
    source_url = signal.get("source_url", "#")
    publication_date = signal.get("publication_date", "")
    return (
        f"<div style=\"border-left:4px solid {border_color};padding:16px 16px 16px 12px;margin-bottom:18px;background:#fffaf2;\">"
        f"<div style=\"font-family:'Courier New',monospace;font-size:13px;color:#1A1612;letter-spacing:0.02em;\">{strength.upper()} SIGNAL</div>"
        f"<div style=\"font-family:Georgia,serif;font-size:18px;font-weight:700;color:#1A1612;margin:8px 0;\">{headline}</div>"
        f"<div style=\"font-family:Georgia,serif;font-size:15px;line-height:1.5;color:#1A1612;margin-bottom:12px;\">{summary}</div>"
        f"<div style=\"background:#EDE8DC;padding:12px;border-radius:8px;margin-bottom:12px;\">"
        f"<div style=\"font-family:'Courier New',monospace;font-size:13px;color:#4A6741;margin-bottom:6px;\">Why it matters</div>"
        f"<div style=\"font-family:Georgia,serif;font-size:14px;line-height:1.5;color:#1A1612;\">{significance}</div>"
        f"</div>"
        f"<div style=\"font-family:'Courier New',monospace;font-size:12px;color:#0D6E6E;\">{source_name} · {publication_date}</div>"
        f"</div>"
    )


def _build_header(run_date: str, total_topics: int, verified_count: int, flagged_count: int, high_topics: list[str]) -> str:
    high_html = "".join(
        f"<span style=\"display:inline-block;padding:6px 10px;margin-right:6px;margin-bottom:6px;border-radius:999px;background:#8B2635;color:#fff;font-family:'Courier New',monospace;font-size:12px;\">{topic}</span>"
        for topic in high_topics
    )
    high_section = (
        f"<div style=\"background:#1A1612;color:#fff;border-radius:10px;padding:14px 16px;margin-bottom:20px;\">"
        f"<div style=\"font-family:Georgia,serif;font-size:15px;font-weight:700;margin-bottom:8px;\">High-signal topics</div>"
        f"{high_html}"
        f"</div>"
    ) if high_topics else ""
    return (
        f"<div style=\"background:#1A1612;color:#fff;padding:22px 24px;border-radius:16px;text-align:center;margin-bottom:24px;\">"
        f"<div style=\"font-family:Georgia,serif;font-size:28px;font-weight:700;letter-spacing:0.02em;\">● Pulse</div>"
        f"<div style=\"font-family:'Courier New',monospace;font-size:14px;color:#D4CEC4;margin-top:8px;\">{run_date} · Abilify · MDD</div>"
        f"</div>"
        f"<div style=\"font-family:'Courier New',monospace;font-size:13px;color:#1A1612;margin-bottom:16px;\">"
        f"{total_topics} topics monitored · {verified_count} verified signals · {flagged_count} flagged & excluded"
        f"</div>"
        f"{high_section}"
    )


def _build_topic_section(topic_result: dict[str, Any], narrative: str) -> str:
    topic = topic_result.get("topic", "Unknown Topic")
    trend = topic_result.get("topic_trend", "stable")
    badge_text, badge_color = TREND_BADGES.get(trend, ("→", "#0D6E6E"))
    verified_count = len(topic_result.get("signals", []))
    flagged_count = topic_result.get("_validation_summary", {}).get("flagged", 0)
    signal_cards = "".join(_format_signal_card(signal) for signal in topic_result.get("signals", []))
    excluded_note = (
        f"<div style=\"font-family:'Courier New',monospace;font-size:13px;color:#8B2635;margin-top:8px;\">{flagged_count} flagged signal(s) excluded from this brief.</div>"
        if flagged_count
        else ""
    )
    return (
        f"<div style=\"margin-bottom:24px;padding:20px;background:#fff;border-radius:14px;border:1px solid #D4CEC4;\">"
        f"<div style=\"display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;\">"
        f"<div style=\"font-family:Georgia,serif;font-size:20px;font-weight:700;color:#1A1612;\">{topic}</div>"
        f"<div style=\"background:{badge_color};color:#fff;padding:8px 12px;border-radius:999px;font-family:'Courier New',monospace;font-size:13px;\">{badge_text}</div>"
        f"</div>"
        f"<div style=\"font-family:'Courier New',monospace;font-size:13px;color:#0D6E6E;margin-bottom:10px;\">Verified: {verified_count} · Flagged: {flagged_count}</div>"
        f"<div style=\"font-family:Georgia,serif;font-size:15px;line-height:1.6;color:#1A1612;margin-bottom:16px;\">{narrative}</div>"
        f"{signal_cards}"
        f"{excluded_note}"
        f"</div>"
    )


def generate_brief(client: anthropic.Client, validated_results: list[dict[str, Any]], run_date: str | None = None) -> str:
    """Generate the full HTML email brief from validated results."""
    run_date_text = run_date or date.today().isoformat()
    total_topics = len(validated_results)
    verified_count = sum(len(topic.get("signals", [])) for topic in validated_results)
    flagged_count = sum(topic.get("_validation_summary", {}).get("flagged", 0) for topic in validated_results)
    high_topics = [topic.get("topic") for topic in validated_results if any(signal.get("signal_strength") == "high" for signal in topic.get("signals", []))]

    topic_sections = ""
    for topic_result in validated_results:
        signals = topic_result.get("signals", [])
        narrative = _ask_for_narrative(client, topic_result.get("topic", ""), signals) if signals else "No verified signals were identified for this topic." 
        topic_sections += _build_topic_section(topic_result, narrative)

    html = (
        f"<html><body style=\"margin:0;padding:0;background:#F5F0E8;color:#1A1612;\">"
        f"<div style=\"max-width:640px;margin:0 auto;padding:24px;background:#F5F0E8;\">"
        f"<div style=\"background:#EDE8DC;padding:24px;border-radius:20px;\">"
        f"{_build_header(run_date_text, total_topics, verified_count, flagged_count, high_topics)}"
        f"{topic_sections}"
        f"<div style=\"font-family:'Courier New',monospace;font-size:12px;color:#1A1612;padding:16px 0 0;border-top:1px solid #D4CEC4;\">"
        f"Validated with Anthropic Claude and strict URL/date checks. For internal Medical Affairs use only. {run_date_text}."
        f"</div>"
        f"</div></div></body></html>"
    )
    return html
