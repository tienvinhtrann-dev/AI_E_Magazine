"""
Shared application extensions (singletons).
Imported by routes and services that need the scheduler or AI generator.
"""
import os
from dotenv import load_dotenv

from ai.article_generator import SimpleArticleGenerator
from apscheduler.schedulers.background import BackgroundScheduler

load_dotenv(override=True)

# AI Article Generator singleton
groq_api_key = os.getenv('GROQ_API_KEY')
article_generator = SimpleArticleGenerator(api_key=groq_api_key)

# APScheduler singleton (started by app_simple.py at launch)
scheduler = BackgroundScheduler(daemon=True)
