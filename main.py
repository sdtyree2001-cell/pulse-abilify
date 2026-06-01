import argparse
import json
import os
from datetime import date

import anthropic

from agents.brief_generator import generate_brief
from agents.breaking_news_agent import run_breaking_news_agent
from agents.email_sender import send_daily_brief
from agents.research_agent import TOPICS, run_research
from agents.validation_agent import validate_all_research

ANTHROPIC_ENV = "ANTHROPIC_API_KEY"


def _get_client() -> anthropic.Client:
    api_key = os.environ.get(ANTHROPIC_ENV, "")
    if not api_key:
        print("ERROR: Missing Anthropic API key. Set the ANTHROPIC_API_KEY environment variable.")
        raise SystemExit(1)
    return anthropic.Client(api_key=api_key)


def _save_html(output_html: str, filename: str) -> None:
    with open(filename, "w", encoding="utf-8") as handle:
        handle.write(output_html)
    print(f"INFO: HTML saved to {filename}")


def run_daily(client: anthropic.Client, dry_run: bool = False) -> None:
    run_date = date.today().isoformat()
    research_results = run_research(client)
    validated_results = validate_all_research(client, research_results)
    html = generate_brief(client, validated_results, run_date=run_date)
    output_path = f"/tmp/pulse_brief_{run_date}.html"
    _save_html(html, output_path)
    if not dry_run:
        success = send_daily_brief(html, run_date=run_date)
        if not success:
            raise SystemExit(1)
    verified_count = sum(len(topic.get("signals", [])) for topic in validated_results)
    flagged_count = sum(topic.get("_validation_summary", {}).get("flagged", 0) for topic in validated_results)
    print(f"SUMMARY: Verified signals={verified_count}, Flagged signals={flagged_count}, Dry-run={dry_run}")


def run_test(client: anthropic.Client) -> None:
    run_date = date.today().isoformat()
    preview_topics = ["Competitive Intelligence", "Safety"]
    research_results = run_research(client, topics=preview_topics)
    validated_results = validate_all_research(client, research_results)
    html = generate_brief(client, validated_results, run_date=run_date)
    output_path = "/tmp/pulse_test_brief.html"
    _save_html(html, output_path)
    for topic in validated_results:
        summary = topic.get("_validation_summary", {})
        print(f"TEST TOPIC: {topic.get('topic')} — Verified={summary.get('verified',0)} Flagged={summary.get('flagged',0)}")
    print("INFO: Test mode completed. No email was sent.")


def run_breaking(client: anthropic.Client) -> None:
    sent_count = run_breaking_news_agent(client)
    print(f"SUMMARY: Breaking news alerts sent={sent_count}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Pulse Abilify intelligence agent runner.")
    parser.add_argument("--daily", action="store_true", help="Run full daily briefing pipeline.")
    parser.add_argument("--breaking", action="store_true", help="Run breaking news scan only.")
    parser.add_argument("--test", action="store_true", help="Run preview test mode and save HTML locally.")
    parser.add_argument("--dry-run", action="store_true", help="Skip email sending in daily mode.")
    args = parser.parse_args()

    if not (args.daily or args.breaking or args.test):
        parser.print_help()
        raise SystemExit(1)

    client = _get_client()
    try:
        if args.daily:
            run_daily(client, dry_run=args.dry_run)
        if args.breaking:
            run_breaking(client)
        if args.test:
            run_test(client)
    except SystemExit:
        raise
    except Exception as exc:
        print(f"ERROR: Runner failed: {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
