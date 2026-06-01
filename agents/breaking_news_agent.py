import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import anthropic

from agents.email_sender import send_alert_email

MODEL_NAME = "claude-opus-4-5"
MAX_TOKENS = 1200
WEB_SEARCH_TOOL = [{"type": "web_search_20250305", "name": "web_search"}]
LAST_ALERTS_FILE = ".last_alerts.json"
BREAKING_TRIGGERS = [
    "FDA label change or new safety communication for aripiprazole",
    "New head-to-head clinical trial data vs. Abilify or aripiprazole",
    "Major guideline update (APA, CANMAT, WFSBP) affecting MDD adjunctive therapy",
    "KOL published statement, paper, or public comment on Abilify or MDD adjunctive therapy",
    "Competitor approval, label expansion, or major regulatory action (Spravato, Exxua, Auvelity, Rexulti, Vraylar)",
    "Significant safety signal or pharmacovigilance update for aripiprazole",
    "Major payer or formulary policy change affecting aripiprazole access",
    "Breaking news from APA annual meeting, ASCP, ECNP, or major psychiatry conference",
    "Investor or earnings call statements about MDD competitive landscape from J&J, Axsome, Aytu, AbbVie",
    "Patient advocacy organization major statement or campaign about MDD treatment or aripiprazole",
]
PRIORITY_MAP = {
    "critical": "#8B2635",
    "high": "#B5540A",
    "medium": "#4A6741",
}


def _load_kol_names() -> list[str]:
    path = Path("kol_watchlist.json")
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return [item.get("name", "") for item in data if isinstance(item, dict) and item.get("name")]
    except Exception:
        return []


def _load_sent_alerts() -> list[str]:
    path = Path(LAST_ALERTS_FILE)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return [str(item) for item in data if isinstance(item, str)]
    except Exception:
        return []


def _save_sent_alerts(headlines: list[str]) -> None:
    path = Path(LAST_ALERTS_FILE)
    trimmed = headlines[-200:]
    path.write_text(json.dumps(trimmed, indent=2))


def _build_prompt(kol_names: list[str]) -> str:
    kol_text = ", ".join(kol_names) if kol_names else "No KOL names provided."
    return (
        "Search for breaking developments in the last 6 hours, or up to 48 hours if needed, that match the alert triggers for aripiprazole and MDD adjunctive therapy. "
        "Include KOL watchlist names when relevant. Return only JSON array of alert objects, or [] if nothing breaking. "
        f"Breaking triggers: {BREAKING_TRIGGERS}. KOL watchlist: {kol_text}. "
        "Alert object schema: headline, summary, significance_for_otsuka, source_name, source_url, publication_date, publication_time, priority, trigger_type, kol_name."
    )


def _parse_alerts(raw_text: str) -> list[dict[str, Any]]:
    cleaned = raw_text.strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        cleaned = cleaned[3:-3].strip()
    if cleaned.startswith("json\n"):
        cleaned = cleaned[5:].strip()
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
    except Exception as exc:
        print(f"WARNING: Could not parse breaking news JSON: {exc}")
    return []


def _alert_card(alert: dict[str, Any]) -> str:
    priority = alert.get("priority", "medium")
    border_color = PRIORITY_MAP.get(priority, "#4A6741")
    kol_badge = ""
    if alert.get("kol_name"):
        kol_badge = (
            f"<span style=\"display:inline-block;background:#8B2635;color:#fff;padding:6px 10px;border-radius:999px;font-family:'Courier New',monospace;font-size:12px;margin-bottom:10px;\">"
            f"KOL: {alert['kol_name']}" 
            f"</span>"
        )
    return (
        f"<div style=\"border-left:4px solid {border_color};padding:18px 18px 18px 14px;margin-bottom:18px;background:#fff;\">"
        f"{kol_badge}"
        f"<div style=\"font-family:Georgia,serif;font-size:18px;font-weight:700;color:#1A1612;margin-bottom:10px;\">{alert.get('headline','Urgent development')}</div>"
        f"<div style=\"font-family:Georgia,serif;font-size:14px;line-height:1.6;color:#1A1612;margin-bottom:12px;\">{alert.get('summary','')}</div>"
        f"<div style=\"font-family:'Courier New',monospace;font-size:13px;color:#0D6E6E;margin-bottom:10px;\">{alert.get('source_name','Source')} · {alert.get('publication_date','')}</div>"
        f"<div style=\"font-family:'Courier New',monospace;font-size:13px;color:#1A1612;\">Trigger: {alert.get('trigger_type','Unknown')}</div>"
        f"</div>"
    )


def _build_email_html(alerts: list[dict[str, Any]]) -> str:
    cards = "".join(_alert_card(alert) for alert in alerts)
    run_date = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"<html><body style=\"margin:0;padding:0;background:#F5F0E8;color:#1A1612;\">"
        f"<div style=\"max-width:640px;margin:0 auto;padding:24px;\">"
        f"<div style=\"background:#8B2635;color:#fff;padding:24px;border-radius:16px;margin-bottom:24px;\">"
        f"<div style=\"font-family:Georgia,serif;font-size:28px;font-weight:700;\">Pulse Breaking News</div>"
        f"<div style=\"font-family:'Courier New',monospace;font-size:14px;margin-top:10px;\">{run_date}</div>"
        f"</div>"
        f"{cards}"
        f"<div style=\"margin-top:20px;font-family:'Courier New',monospace;font-size:12px;color:#1A1612;\">This alert is generated by Pulse breaking news scanning and is for internal Medical Affairs awareness only.</div>"
        f"</div></body></html>"
    )


def run_breaking_news_agent(client: anthropic.Client) -> int:
    """Run the breaking news scan and send alerts for new findings."""
    kol_names = _load_kol_names()
    print(f"INFO: Loaded {len(kol_names)} KOL names for breaking news scan.")
    prompt = _build_prompt(kol_names)
    try:
        response = client.messages.stream(
            model=MODEL_NAME,
            tools=WEB_SEARCH_TOOL,
            max_tokens_to_sample=MAX_TOKENS,
            message=[{"role": "user", "content": prompt}],
        )
        raw_text = ""
        for event in response:
            if getattr(event, "type", None) == "response.output_text.delta":
                raw_text += event.delta
        alerts = _parse_alerts(raw_text)
    except Exception as exc:
        print(f"ERROR: Breaking news Anthropic call failed: {exc}")
        return 0

    if not alerts:
        print("INFO: No breaking alerts found.")
        return 0

    sent_headlines = _load_sent_alerts()
    new_alerts = [alert for alert in alerts if alert.get("headline") not in sent_headlines]
    if not new_alerts:
        print("INFO: No new breaking alerts after deduplication.")
        return 0

    html_body = _build_email_html(new_alerts)
    highest_priority = max((alert.get("priority", "medium") for alert in new_alerts), key=lambda p: ["medium", "high", "critical"].index(p))
    subject_prefix = "🚨 PULSE CRITICAL ALERT —" if highest_priority == "critical" else "⚠ Pulse Breaking —" if highest_priority == "high" else "Pulse Alert —"
    headline = new_alerts[0].get("headline", "New development")
    subject = f"{subject_prefix} {headline}"
    success = send_alert_email(subject, html_body, priority=highest_priority)
    if success:
        updated_headlines = sent_headlines + [alert.get("headline", "") for alert in new_alerts]
        _save_sent_alerts(updated_headlines)
        print(f"INFO: Sent {len(new_alerts)} breaking alert(s).")
        return len(new_alerts)
    print("ERROR: Failed to send breaking alert email.")
    return 0
