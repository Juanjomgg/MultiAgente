# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# === API KEYS (desde .env) ===
ABACUS_API_KEY = os.getenv("ABACUS_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

if not ABACUS_API_KEY:
    raise EnvironmentError("Falta ABACUS_API_KEY en el archivo .env")
if not YOUTUBE_API_KEY:
    raise EnvironmentError("Falta YOUTUBE_API_KEY en el archivo .env")

# === ABACUS LLM ENDPOINT ===
ABACUS_BASE_URL = "https://routellm.abacus.ai/v1/chat/completions"

# === ASIGNACIÓN AGENTE → MODELO ===
AGENT_MODELS = {
    "niche_hunter":       "gemini-3.5-flash",
    "niche_validator":    "accounts/fireworks/models/deepseek-v4-pro",
    "content_strategist": "claude-sonnet-4-6",
    "script_writer":      "claude-opus-4-7",
    "seo_optimizer":      "gpt-5.4-mini",
    "thumbnail_conceptor":"gpt-5.4-mini",
    "quality_controller": "claude-opus-4-6",
}

# === GUARDRAILS: LÍMITES DE TOKENS POR AGENTE ===
AGENT_MAX_TOKENS = {
    "niche_hunter":       2000,
    "niche_validator":    2500,
    "content_strategist": 3000,
    "script_writer":      6000,
    "seo_optimizer":      1500,
    "thumbnail_conceptor": 1000,
    "quality_controller": 3000,
}