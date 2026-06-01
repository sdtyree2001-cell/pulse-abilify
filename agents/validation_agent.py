import json
import urllib.request
from datetime import date, datetime, timedelta
from typing import Any

import anthropic

MODEL_NAME = "claude-opus-4-5"
MAX_TOKENS = 800
WEB_SEARCH_TOOL = [{"type": "web_search_20250305", "name": "web_search"}]


def _is_http_url(url: str) -> bool:
    return url.lower().startswith("http://") or url.lower().startswith("https://")


def _check_url_reachable(url: str) -> tuple[bool, str]:
    """Check URL reachability with a HEAD request."""
    if not url or not _is_http_url(url):
        return False, "Missing or unsupported URL format."
    request = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            status = response.getcode()
            if status == 404:
                return False, "URL returned 404 Not Found."
            return True, f"URL reachable with status {status}."
    except urllib.error.HTTPError as exc:
        if exc.code in {403, 405}:
            return True, f"URL access restricted but exists (HTTP {exc.code})."
        if exc.code == 404:
            return False, "URL returned 404 Not Found."
        return False, f"HTTP error {exc.code}."
    except Exception as exc:
        return False, f"URL request failed: {exc}"


def _check_date_valid(date_str: str) -> tuple[bool, str]:
    """Validate the publication date."""
    if not date_str:
        return False, "Publication date missing."
    try:
        parsed = date.fromisoformat(date_str[:10])
    except ValueError:
        return False, "Publication date could not be parsed."
    if parsed > date.today():
        return False, "Publication date is in the future."
    if parsed < date.today() - timedelta(days=90):
        return False, "Publication date is older than 90 days."
    return True, "Publication date is valid."


def _build_verification_prompt(signal: dict[str, Any], topic: str, kol_names: list[str] | None = None) -> str:
    return (
        f"Verify the following signal about Abilify (aripiprazole) and MDD adjunctive therapy for Otsuka Medical Affairs. "
        "Use web search to independently confirm the claim, source URL, and publication date. "
        f"Signal details: headline={signal.get('headline')}, summary={signal.get('summary')}, source_name={signal.get('source_name')}, source_url={signal.get('source_url')}, publication_date={signal.get('publication_date')}. "
        "Return only JSON with keys verified, confidence, verification_notes, corrected_url, corrected_date, hallucination_risk, hallucination_reason. "
        "If URL or date appear incorrect, provide corrected_url and/or corrected_date. "
        "Use none for corrected fields when not needed."
    )


def _parse_verification_output(raw_text: str) -> dict[str, Any]:
    try:
        cleaned = raw_text.strip()
        if cleaned.startswith("```") and cleaned.endswith("```"):
            cleaned = cleaned[3:-3].strip()
        if cleaned.startswith("json\n"):
            cleaned = cleaned[5:].strip()
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
        return {"verified": False, "confidence": "low", "verification_notes": "Unexpected output format."}
    except Exception as exc:
        return {"verified": False, "confidence": "low", "verification_notes": f"Parse failure: {exc}", "corrected_url": None, "corrected_date": None, "hallucination_risk": "high", "hallucination_reason": str(exc)}


def _verify_signal(client: anthropic.Client, signal: dict[str, Any], topic: str) -> dict[str, Any]:
    prompt = _build_verification_prompt(signal, topic)
    try:
        response = client.messages.stream(
            model=MODEL_NAME,
            tools=WEB_SEARCH_TOOL,
            max_tokens_to_sample=MAX_TOKENS,
            message=[{"role": "user", "content": prompt}],
        )
        output_text = ""
        for event in response:
            if getattr(event, "type", None) == "response.output_text.delta":
                output_text += event.delta
        verification = _parse_verification_output(output_text)
        return verification
    except Exception as exc:
        return {"verified": False, "confidence": "low", "verification_notes": f"Anthropic call failed: {exc}", "corrected_url": None, "corrected_date": None, "hallucination_risk": "high", "hallucination_reason": str(exc)}


def validate_all_research(client: anthropic.Client, research_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate research signals strictly and annotate verified vs flagged results."""
    total_verified = 0
    total_flagged = 0
    validated_topics: list[dict[str, Any]] = []
    for topic_result in research_results:
        topic_name = topic_result.get("topic", "Unknown Topic")
        signals = topic_result.get("signals", []) or []
        verified_signals: list[dict[str, Any]] = []
        flagged_signals: list[dict[str, Any]] = []
        for signal in signals:
            url = signal.get("source_url", "")
            date_text = signal.get("publication_date", "")
            url_ok, url_reason = _check_url_reachable(url)
            date_ok, date_reason = _check_date_valid(date_text)
            verification = _verify_signal(client, signal, topic_name)
            corrected_url = verification.get("corrected_url")
            corrected_date = verification.get("corrected_date")
            if corrected_url and corrected_url != url:
                signal["source_url"] = corrected_url
                url, url_ok, url_reason = corrected_url, *_check_url_reachable(corrected_url)
            if corrected_date and corrected_date != date_text:
                signal["publication_date"] = corrected_date
                date_text, date_ok, date_reason = corrected_date, *_check_date_valid(corrected_date)
            verified = (
                url_ok
                and date_ok
                and verification.get("verified") is True
                and verification.get("hallucination_risk") in {"none", "low"}
            )
            signal["_validation"] = {
                "url_check": {"pass": url_ok, "reason": url_reason},
                "date_check": {"pass": date_ok, "reason": date_reason},
                "claude_verification": verification,
            }
            signal["_status"] = "verified" if verified else "flagged"
            if verified:
                verified_signals.append(signal)
                total_verified += 1
            else:
                flagged_signals.append(signal)
                total_flagged += 1
        topic_result["_validation_summary"] = {
            "total": len(signals),
            "verified": len(verified_signals),
            "flagged": len(flagged_signals),
        }
        topic_result["signals"] = verified_signals
        validated_topics.append(topic_result)
    print(f"INFO: Validation complete. Verified={total_verified}, Flagged={total_flagged}")
    return validated_topics
