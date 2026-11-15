# Job Alert Bot (Full Stack, junior level)

Twice a day (9:00 AM and 4:00 PM IST) this bot looks for new jobs in
**Coimbatore, Chennai, Bangalore and Remote** and sends only the NEW ones to your Telegram.
It also keeps a `jobs_tracker.csv` you can open in Excel / Google Sheets.

Sources: Adzuna India API + Remotive (remote). It does NOT scrape LinkedIn or Naukri
(against their terms, and gets accounts blocked) - use their saved alerts instead (see bottom).

## One-time setup (about 15 minutes)

### 1. Telegram bot
1. In Telegram, open **@BotFather** -> send `/newbot` -> follow steps -> copy the **bot token**.
2. Open your new bot and send it any message (e.g. "hi").
3. In a browser open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
   and copy the number at `"chat":{"id": ...}`. That is your **chat id**.

### 2. Adzuna API keys (optional)`r`nRegister at https://developer.adzuna.com/ and verify your email. If the site asks for card details, skip it: do not enter a card. The bot still works without Adzuna and uses the free Remotive remote-jobs feed. Add `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` only if you receive keys without payment.

### 3. GitHub repo
1. Create a new **private** repository on GitHub.
2. Upload everything from this folder (keep the `.github/workflows/job-alert.yml` path exactly).
3. Repo -> **Settings -> Secrets and variables -> Actions -> New repository secret**. Add these secrets:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `ADZUNA_APP_ID` (optional)`r`n   - `ADZUNA_APP_KEY` (optional)
4. Go to the **Actions** tab -> **Job Alert** -> **Run workflow**. In a minute you should get a Telegram message.

After that it runs by itself every day.

## Customise
Edit the top of `job_alert.py`:
- `LOCATIONS`, `SEARCH_TERMS` - what to search
- `ROLE_KEYWORDS` / `EXCLUDE_TITLE` - title filters
- `MAX_MIN_YEARS` - skip jobs asking for this many years or more (default 3)

## Notes
- GitHub pauses scheduled workflows if a repo has no activity for 60 days. The bot commits
  `seen_jobs.json` whenever it finds new jobs, which usually keeps it alive. If alerts stop,
  open the Actions tab and re-enable the workflow.
- Test locally without Telegram: `pip install -r requirements.txt` then
  `ADZUNA_APP_ID=xxx ADZUNA_APP_KEY=yyy python job_alert.py` (prints results instead of sending).

## Also do this manually (5 minutes, big impact)
Create saved searches with **daily email/app alerts** (keywords: Full Stack Developer, MERN, React Developer, Node.js Developer; locations: Coimbatore, Chennai, Bangalore, Remote; experience 0-2 years):
- LinkedIn Jobs: https://www.linkedin.com/jobs/ (turn on "Job alert")
- Naukri: https://www.naukri.com/ (save search + email alert)
- Indeed: https://in.indeed.com/ (email alert)
- Instahyre, Cutshort, Wellfound for startup roles

