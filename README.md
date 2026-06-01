# Pulse Abilify Intelligence Agent

## What this does

Pulse is a fully automated pharmaceutical intelligence agent system for Abilify (aripiprazole) as adjunctive therapy in MDD. It includes:

- **Research Agent**: scans 11 monitored topics daily using Anthropic Claude with web search.
- **Validation Agent**: strictly verifies every signal with URL reachability, date checks, and secondary Claude validation.
- **Brief Generator**: builds a styled HTML email for the Medical Affairs audience.
- **Breaking News Agent**: scans every 2 hours for priority alerts and KOL activity.

## Setup (~15 minutes)

1. Create a private GitHub repository, for example `pulse-abilify`.
2. From the local `pulse-abilify` folder, push the code to GitHub:
   ```bash
   cd '/Users/styree/Documents/Projects/Daily Update/pulse-abilify'
   git init
   git add .
   git commit -m "Initial Pulse Abilify agent project"
   git branch -M main
   git remote add origin https://github.com/<your-username>/pulse-abilify.git
   git push -u origin main
   ```
3. Confirm the repo contains `main.py`, `agents/`, `kol_watchlist.json`, and `.github/workflows/pulse.yml`.
4. Get an Anthropic API key from `https://console.anthropic.com`.
5. Create a Gmail App Password:
   1. Sign in to your Google Account.
   2. Go to `Security`.
   3. Under "Signing in to Google", select `App passwords`.
   4. Choose `Mail` as the app and `Other` or `Custom name` such as `Pulse Agent`.
   5. Generate the 16-character App Password and copy it.
6. In GitHub, add the following repository secrets:
   - `ANTHROPIC_API_KEY`
   - `GMAIL_SENDER`
   - `GMAIL_APP_PASSWORD`
7. Run test mode first locally or in GitHub Actions: `python main.py --test`.
8. Edit `kol_watchlist.json` with your KOL names, titles, affiliations, relevance, and notes.

## Costs

| Service | Cost |
|---|---|
| GitHub Actions | Free tier included |
| Anthropic API | ~$3–8/month depending on usage |
| Gmail | Free with App Password |

## Adjusting the schedule

- Daily brief is scheduled for `0 13 * * *`, which is 1pm UTC / 8am ET during standard time.
- Breaking news runs every 2 hours with `0 */2 * * *`.
- Edit `.github/workflows/pulse.yml` if you need a different UTC cron schedule.

## Troubleshooting

- **No email received**: verify `GMAIL_SENDER` and `GMAIL_APP_PASSWORD`, and check spam folders.
- **Auth failures**: confirm the Gmail App Password is active and the Gmail address is correct.
- **Validation flagging everything**: signals may have invalid URLs, dates, or need clearer source metadata.

## File reference

| File | Purpose |
|---|---|
| `main.py` | Orchestrates daily, breaking, and test run modes |
| `agents/research_agent.py` | Searches web and returns structured topic signals |
| `agents/validation_agent.py` | Applies strict URL/date/verification checks |
| `agents/brief_generator.py` | Generates styled HTML email briefs |
| `agents/breaking_news_agent.py` | Runs breaking news scans and sends alerts |
| `agents/email_sender.py` | Sends emails via Gmail SMTP |
| `kol_watchlist.json` | User-editable list of KOLs for alerts |
| `.github/workflows/pulse.yml` | GitHub Actions schedules and jobs |
| `requirements.txt` | Python dependency list |
| `CLAUDE.md` | Claude project context placeholder |
