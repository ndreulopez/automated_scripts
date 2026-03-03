# Executive News Briefing Automation

This repository contains an automated pipeline that curates, synthesizes, and delivers a twice-daily executive news briefing directly to your inbox.

By leveraging Python, RSS feeds, and the Gemini AI API, the script pulls the latest articles from top-tier publications, filters out duplicate stories, and uses an AI model to draft a clean, categorized HTML email summary. The entire process is automated using GitHub Actions.

## Features

* **Multi-Source Aggregation:** Pulls RSS feeds from La Vanguardia, El País, Financial Times, Bloomberg, and Reuters.
* **Smart Deduplication:** Uses fuzzy string matching to identify and skip highly similar headlines.
* **AI-Powered Summarization:** Feeds the raw news data to Gemini to generate categorized, analytical summaries in an executive tone.
* **HTML Email Delivery:** Formats the AI output into a responsive HTML email and sends it via Gmail SMTP.
* **Zero-Maintenance Automation:** Scheduled via a GitHub Actions cron job to run seamlessly in the background.

---

## Project Structure

* `news_script.py`: The core Python script that handles fetching, AI processing, and email delivery.
* `.github/workflows/schedule.yml`: The GitHub Actions workflow file defining the execution schedule and environment.
* 
`requirements.txt`: The Python dependencies required for the script (`feedparser==6.0.11` and `google-generativeai==0.8.3`).



---

## Setup & Configuration

To fork this project and run it yourself, you will need to set up a few credentials and configure your GitHub repository secrets.

### 1. Retrieve API Keys and Passwords

* **Gemini API Key:** Obtain a free API key from Google AI Studio.
* **Gmail App Password:** If using Gmail to send the emails, you must generate an "App Password" from your Google Account security settings (standard passwords will not work).

### 2. Configure GitHub Secrets

Navigate to your repository on GitHub, go to **Settings > Secrets and variables > Actions**, and add the following repository secrets:

* `GEMINI_API_KEY`: Your Google Gemini API key.
* `EMAIL_ADDRESS`: The email address sending the briefing.
* `EMAIL_APP_PASSWORD`: The 16-character App Password for the sender email.
* `RECIPIENT_EMAIL`: The email address that should receive the briefing.

---

## Automation Schedule

The workflow is managed by `schedule.yml` and runs **Monday through Friday at 06:00 and 18:00 UTC** (07:00 and 19:00 CET / 08:00 and 20:00 CEST), and on **Saturdays and Sundays at 08:00 UTC** (09:00 CET / 10:00 CEST).

You can also trigger the script manually at any time:

1. Go to the **Actions** tab in your repository.
2. Click on **Twice Weekly News Briefing** on the left sidebar.
3. Click the **Run workflow** dropdown on the right side of the screen.

---

## Running Locally

If you want to test the script on your local machine before pushing to GitHub:

1. Clone the repository.
2. Install the required dependencies using pip (`pip install -r requirements.txt`).
3. Export the required environment variables in your terminal.
4. Run the script using `python news_script.py`.