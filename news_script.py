import os
import time
import logging
import feedparser
import smtplib
import difflib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import google.generativeai as genai

# ==========================================
# 1. CONFIGURATION & LOGGING
# ==========================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# RSS Feed URLs
FEEDS = {
    "La Vanguardia": "https://www.lavanguardia.com/rss/home.xml",
    "El País": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada",
    "Financial Times": "https://www.ft.com/?format=rss",
    "Bloomberg": "https://feeds.bloomberg.com/markets/news.rss", 
    "Reuters": "https://yahoo.com/news/rss/world" 
}

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def get_secret(key):
    """Fetches secrets safely from OS env vars (for GitHub Actions)."""
    if os.getenv(key):
        return os.getenv(key)
    logger.error(f"Secret {key} not found.")
    return None

def is_similar(title1, title2, threshold=0.8):
    """Checks if two titles are highly similar to prevent duplicates."""
    return difflib.SequenceMatcher(None, title1.lower(), title2.lower()).ratio() > threshold

# ==========================================
# 3. NEWS COLLECTION & DEDUPLICATION
# ==========================================
def fetch_news(limit_per_source=7):
    """Fetches, parses, and deduplicates news from predefined RSS feeds."""
    logger.info("Starting news collection...")
    all_articles = []
    seen_titles = []

    for source, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)
            count = 0
            for entry in feed.entries:
                if count >= limit_per_source:
                    break
                
                title = entry.get('title', 'No Title')
                
                if any(is_similar(title, seen) for seen in seen_titles):
                    continue
                
                seen_titles.append(title)
                all_articles.append({
                    "source": source,
                    "title": title,
                    "description": entry.get('summary', 'No description available.')[:200],
                    "link": entry.get('link', ''),
                    "date": entry.get('published', datetime.now().strftime('%Y-%m-%d'))
                })
                count += 1
            logger.info(f"Fetched {count} articles from {source}.")
        except Exception as e:
            logger.error(f"Failed to fetch from {source}: {e}")

    return all_articles

# ==========================================
# 4. GEMINI AI INTEGRATION
# ==========================================
def generate_executive_briefing(articles):
    """Sends structured articles to Gemini API to generate an HTML briefing."""
    logger.info("Sending data to Gemini API...")
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Missing Gemini API Key.")

    # Configure the Gemini SDK
    genai.configure(api_key=api_key)

    raw_text = "\n\n".join([f"Source: {a['source']}\nTitle: {a['title']}\nSummary: {a['description']}\nLink: {a['link']}" for a in articles])

    system_prompt = """You are a top-tier executive briefer. I will provide a list of the latest news articles. 
    Your task is to generate a concise, 5-10 minute executive briefing formatted in clean HTML.
    
    Structure the HTML exactly with these sections (using <h2> and <h3> tags):
    1. Spain & Catalonia Developments
    2. Global Economics & Markets
    3. Corporate & Geopolitics
    
    Rules for the briefing:
    - Group the provided articles into the above categories.
    - Highlight the most important developments.
    - Add a brief analytical sentence on *why* the story matters.
    - Identify any cross-source trends.
    - Maintain a strictly neutral, objective, and analytical tone.
    - Include the source name and a hyperlink to the article.
    - Output ONLY valid HTML code. Do not wrap it in markdown code blocks like ```html.
    """

    try:
        # Using Gemini 3.0 Flash
        model = genai.GenerativeModel(
            model_name='gemini-3-flash-preview',
            system_instruction=system_prompt
        )
        response = model.generate_content(
            raw_text,
            generation_config=genai.types.GenerationConfig(temperature=0.2)
        )
        
        html_content = response.text
        # Clean up markdown formatting if the LLM adds it
        return html_content.replace("```html", "").replace("```", "").strip()
    except Exception as e:
        logger.error(f"Gemini API failed: {e}")
        return "<p>Error generating briefing. Please check logs.</p>"

# ==========================================
# 5. EMAIL DELIVERY
# ==========================================
def send_email(html_body):
    """Sends the HTML email via Gmail SMTP."""
    logger.info("Preparing to send email...")
    sender = get_secret("EMAIL_ADDRESS")
    password = get_secret("EMAIL_APP_PASSWORD")
    recipient = get_secret("RECIPIENT_EMAIL")

    if not all([sender, password, recipient]):
        raise ValueError("Missing email credentials.")

    subject = f"Executive Briefing | {datetime.now().strftime('%b %d, %Y - %H:%M %Z')}"
    
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient

    full_html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: auto;">
        <div style="background-color: #f4f4f4; padding: 20px; text-align: center; border-bottom: 3px solid #0056b3;">
            <h1 style="margin: 0; color: #0056b3;">Daily Executive Briefing</h1>
            <p style="margin: 0; font-size: 14px; color: #666;">{datetime.now().strftime('%A, %B %d, %Y')}</p>
        </div>
        <div style="padding: 20px;">
            {html_body}
        </div>
        <div style="background-color: #f4f4f4; padding: 10px; text-align: center; font-size: 12px; color: #999;">
            <p>Automated Briefing powered by Python & Gemini AI.</p>
        </div>
      </body>
    </html>
    """
    
    msg.attach(MIMEText(full_html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, recipient, msg.as_string())
        logger.info("Email sent successfully!")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")

# ==========================================
# 6. MAIN EXECUTION
# ==========================================
def job():
    """Main execution flow."""
    logger.info("--- Starting Executive Briefing Job ---")
    articles = fetch_news()
    if articles:
        briefing_html = generate_executive_briefing(articles)
        send_email(briefing_html)
    else:
        logger.warning("No articles fetched. Skipping API and Email.")
    logger.info("--- Job Complete ---")

if __name__ == "__main__":
    job()