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
    "Reuters/BBC": "http://feeds.bbci.co.uk/news/world/rss.xml",
    "TechCrunch": "https://techcrunch.com/feed/",
    "WIRED": "https://es.wired.com/feed/rss", 
    "Agencia SINC": "https://www.agenciasinc.es/rss/feed/noticias",
    "Nature": "https://www.nature.com/nature.rss",
    "La Vanguardia (Deportes)": "https://www.lavanguardia.com/rss/deportes.xml",
    "Diari Ara (Esports)": "https://www.ara.cat/rss/esports/",
    "Barça Blaugranes": "https://www.barcablaugranes.com/rss/current.xml"
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
def fetch_news(limit_per_source=15):
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

    system_prompt = """Ets un analista executiu de primer nivell. Et proporcionaré una llista amb les últimes notícies de diferents mitjans (en anglès i castellà). 
    La teva tasca és analitzar-les, **seleccionar només les notícies més rellevants i de major impacte**, i generar un resum executiu concís en format HTML net.
    
    IMPORTANT: Tota la teva resposta, incloent-hi els títols traduïts i l'anàlisi, HA D'ESTAR ÍNTEGRAMENT EN CATALÀ.
    
    Estructura l'HTML exactament amb aquestes seccions (fent servir etiquetes <h2> i <h3>):
    Notícies generals de Catalunya
    Notícies generals d'Espanya
    Geopolítica
    Macroeconomia
    Economia de mercat
    Tecnologia
    Ciència
    FC Barcelona i Esport
    
    Regles per al resum:
    - Fes un sedàs de la llista proporcionada: descarta les notícies menors, redundants o poc rellevants. Queda't només amb el gra.
    - Agrupa els articles seleccionats en les 8 categories esmentades. Si una categoria no té notícies rellevants, indica-ho breument (ex: "Sense novetats destacables avui.").
    - Afegeix una breu frase analítica sobre *per què* és important aquesta notícia o quin impacte té.
    - Identifica tendències comunes si diferents fonts parlen del mateix tema.
    - Mantingues un to estrictament neutral, objectiu i analític (fins i tot per a l'esport).
    - Inclou el nom de la font original i un hipervincle (enllaç) a l'article complet.
    - Retorna NOMÉS codi HTML vàlid. No l'embolcallis en blocs de codi markdown com ```html.
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
        return "<p>Error generant el resum. Si us plau, revisa els logs.</p>"

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

    subject = f"Resum Executiu | {datetime.now().strftime('%b %d, %Y - %H:%M %Z')}"
    
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient

    full_html = f"""
    <html>
      <head>
        <style>
          /* Imports fallback fonts for email clients that support web fonts */
          @import url('https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,700;1,400&family=UnifrakturMaguntia&display=swap');
        </style>
      </head>
      <body style="font-family: 'Cheltenham', 'ITC Cheltenham', 'Lora', Georgia, serif; line-height: 1.6; color: #1a1a1a; max-width: 800px; margin: auto; background-color: #fdfbf7;">
        
        <div style="padding: 40px 20px 20px; text-align: center; border-bottom: 2px solid #b8974a;">
            <h1 style="margin: 0; font-family: 'Chomsky', 'UnifrakturMaguntia', 'Old English Text MT', blackletter, serif; font-size: 48px; font-weight: normal; color: #111;">Daily Executive Briefing</h1>
            
            <div style="margin-top: 25px; border-top: 1px solid #b8974a; border-bottom: 1px solid #b8974a; padding: 6px 0;">
                <p style="margin: 0; font-size: 12px; color: #333; text-transform: uppercase; letter-spacing: 1px; font-family: 'Helvetica Neue', Helvetica, sans-serif;">{datetime.now().strftime('%A, %B %d, %Y')}</p>
            </div>
        </div>
        
        <div style="padding: 30px 20px; font-size: 16px;">
            {html_body}
        </div>
        
        <div style="padding: 20px; text-align: center; font-size: 12px; color: #666; border-top: 1px solid #b8974a;">
            <p style="margin: 0; font-style: italic;">Automated Briefing powered by Python & Gemini AI.</p>
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
