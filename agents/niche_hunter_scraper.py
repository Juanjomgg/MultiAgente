# agents/niche_hunter_scraper.py
import logging
from logging_setup import setup_logging
import requests
import json
import os
import time
from datetime import datetime, timedelta, timezone
from config import YOUTUBE_API_KEY, DATA_DIR
logger = logging.getLogger(__name__)

# === ARCHIVOS DE PROGRESO ===
COLLECTED_IDS_FILE = os.path.join(DATA_DIR, "collected_ids.txt")
CHECKED_IDS_FILE = os.path.join(DATA_DIR, "checked_ids.txt")
COMPLETED_SEARCHES_FILE = os.path.join(DATA_DIR, "completed_searches.txt")
QUALIFYING_CHANNELS_FILE = os.path.join(DATA_DIR, "qualifying_channels.json")

# === CONFIGURACIÓN ===
DAILY_QUOTA = 9000
TARGET_CHANNELS = 300
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"

# === 90 KEYWORDS ===
KEYWORDS = [
    # FINANCE (10)
    "personal finance tips", "stock market for beginners", "crypto investing",
    "real estate tips", "passive income ideas", "how to save money",
    "dividend stocks", "side hustle ideas", "financial independence", "budget tips",
    # TECH/AI (10)
    "AI tools tutorial", "ChatGPT tips", "productivity apps", "coding for beginners",
    "tech explained", "AI automation", "software tutorial", "machine learning basics",
    "no code tutorial", "tech tips",
    # HEALTH/FITNESS (10)
    "weight loss tips", "home workout routine", "gym beginner", "meal prep ideas",
    "healthy eating", "mental health tips", "yoga for beginners", "running for beginners",
    "build muscle fast", "healthy recipes easy",
    # LIFESTYLE (10)
    "minimalist lifestyle", "morning routine", "self improvement tips", "stoicism explained",
    "journaling tips", "productivity tips", "digital nomad life", "van life tour",
    "tiny house tour", "slow living",
    # BUSINESS (10)
    "dropshipping tutorial", "Amazon FBA beginner", "print on demand", "freelancing tips",
    "how to start agency", "SaaS startup", "ecommerce tips", "online business ideas",
    "how to grow youtube", "personal brand tips",
    # EDUCATION (10)
    "book summary", "learn language fast", "study tips", "history explained",
    "science explained", "philosophy explained", "economics explained", "law explained",
    "psychology explained", "facts explained",
    # ENTERTAINMENT/HOBBY (10)
    "chess tips beginner", "guitar lessons beginner", "drawing tutorial",
    "photography tips beginner", "film explained", "anime explained",
    "true crime story", "mystery explained", "comedy", "gaming tips",
    # CREATIVE (10)
    "interior design tips", "outfit ideas", "makeup tutorial", "hair care tips",
    "skincare routine", "DIY home", "home organization", "thrift haul",
    "art tutorial", "graphic design tutorial",
    # TRAVEL/FOOD (10)
    "travel vlog", "budget travel tips", "food review", "street food tour",
    "restaurant review", "cooking easy", "baking beginner", "international food",
    "city tour", "solo travel tips",
]

units_used = 0


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)
    for f in [COLLECTED_IDS_FILE, CHECKED_IDS_FILE, COMPLETED_SEARCHES_FILE]:
        if not os.path.exists(f):
            open(f, "w", encoding="utf-8").close()
    if not os.path.exists(QUALIFYING_CHANNELS_FILE):
        with open(QUALIFYING_CHANNELS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)


def load_lines(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def append_lines(filepath, lines):
    with open(filepath, "a", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")


def load_qualifying():
    with open(QUALIFYING_CHANNELS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_qualifying(channels):
    with open(QUALIFYING_CHANNELS_FILE, "w", encoding="utf-8") as f:
        json.dump(channels, f, indent=2, ensure_ascii=False)


def print_resume_status():
    completed = load_lines(COMPLETED_SEARCHES_FILE)
    collected = load_lines(COLLECTED_IDS_FILE)
    checked = load_lines(CHECKED_IDS_FILE)
    qualifying = load_qualifying()

    logger.info("\n📊 RESUME STATUS")
    logger.info(f"   Keywords searched: {len(completed)}/90")
    logger.info(f"   Channel IDs collected: {len(collected)}")
    logger.info(f"   IDs validated: {len(checked)}")
    logger.info(f"   Qualifying channels: {len(qualifying)}/{TARGET_CHANNELS}\n")

    return completed, collected, checked, qualifying


def search_videos(keyword):
    """Busca vídeos recientes por keyword y extrae channel IDs."""
    global units_used

    if units_used >= DAILY_QUOTA:
        return set()

    twelve_months_ago = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    params = {
        "part": "snippet",
        "type": "video",
        "q": keyword,
        "publishedAfter": twelve_months_ago,
        "publishedBefore": now,
        "order": "viewCount",
        "maxResults": 50,
        "relevanceLanguage": "en",
        "regionCode": "US",
        "key": YOUTUBE_API_KEY,
    }

    response = requests.get(f"{YOUTUBE_API_BASE}/search", params=params, timeout=30)
    units_used += 100
    logger.info(f"   Units used: {units_used}/{DAILY_QUOTA}")

    response.raise_for_status()
    data = response.json()

    channel_ids = set()
    for item in data.get("items", []):
        cid = item.get("snippet", {}).get("channelId")
        if cid:
            channel_ids.add(cid)

    return channel_ids


def validate_channels(channel_ids_to_check):
    """Valida canales en lotes de 50 contra los criterios."""
    global units_used

    twelve_months_ago = datetime.now(timezone.utc) - timedelta(days=365)
    qualifying = load_qualifying()
    checked = load_lines(CHECKED_IDS_FILE)

    # Filtrar los que ya están checkeados
    pending = [cid for cid in channel_ids_to_check if cid not in checked]
    batches = [pending[i:i+50] for i in range(0, len(pending), 50)]

    batch_num = 0
    for batch in batches:
        if units_used >= DAILY_QUOTA:
            logger.warning("⚠️ Cuota diaria alcanzada durante validación.")
            break

        batch_num += 1
        ids_str = ",".join(batch)

        params = {
            "part": "snippet,statistics",
            "id": ids_str,
            "key": YOUTUBE_API_KEY,
        }

        response = requests.get(f"{YOUTUBE_API_BASE}/channels", params=params, timeout=30)
        units_used += len(batch)  # 1 unit por canal
        logger.info(f"   Units used: {units_used}/{DAILY_QUOTA}")

        response.raise_for_status()
        data = response.json()

        passed = too_old = subs_low = subs_high = too_many_vids = 0

        for ch in data.get("items", []):
            snippet = ch.get("snippet", {})
            stats = ch.get("statistics", {})

            created = datetime.fromisoformat(snippet["publishedAt"].replace("Z", "+00:00"))
            subs = int(stats.get("subscriberCount", 0))
            videos = int(stats.get("videoCount", 0))

            if created < twelve_months_ago:
                too_old += 1
            elif subs < 20000:
                subs_low += 1
            elif subs > 400000:
                subs_high += 1
            elif videos > 150:
                too_many_vids += 1
            else:
                passed += 1
                qualifying.append({
                    "channel_id": ch["id"],
                    "title": snippet.get("title", ""),
                    "created": snippet["publishedAt"],
                    "subscribers": subs,
                    "videos": videos,
                    "views": int(stats.get("viewCount", 0)),
                    "category_keyword": "batch_validation",
                })

        # Marcar como checkeados
        append_lines(CHECKED_IDS_FILE, batch)

        logger.info(
            f"   Batch {batch_num}: checked {len(batch)} | "
            f"✅ {passed} passed | ⏰ {too_old} too old | "
            f"⬇️ {subs_low} subs low | ⬆️ {subs_high} subs high | "
            f"🎬 {too_many_vids} too many videos"
        )

        if len(qualifying) >= TARGET_CHANNELS:
            logger.info(f"🎯 ¡Objetivo de {TARGET_CHANNELS} canales alcanzado!")
            break

        time.sleep(0.2)

    save_qualifying(qualifying)
    return qualifying


def run_scraper():
    """Ejecuta el scraper completo con resume."""
    global units_used

    ensure_data_dir()
    completed, collected, checked, qualifying = print_resume_status()

    if len(qualifying) >= TARGET_CHANNELS:
        logger.info(f"✅ Ya tienes {len(qualifying)} canales. No es necesario buscar más.")
        return qualifying

    # === FASE 1: BÚSQUEDA ===
    logger.info("🔍 FASE 1: Buscando vídeos por keywords...\n")
    new_ids = set()

    for i, keyword in enumerate(KEYWORDS):
        if keyword in completed:
            continue
        if units_used >= DAILY_QUOTA:
            logger.warning("⚠️ Cuota diaria alcanzada. Ejecuta de nuevo mañana.")
            break

        logger.info(f"[{i+1}/90] Buscando: \"{keyword}\"")
        try:
            ids = search_videos(keyword)
            new_ids.update(ids)
            append_lines(COLLECTED_IDS_FILE, ids - collected)
            collected.update(ids)
            append_lines(COMPLETED_SEARCHES_FILE, [keyword])
            logger.info(f"   → {len(ids)} canales encontrados (total acumulado: {len(collected)})")
            time.sleep(0.3)
        except Exception as e:
            logger.error(f"   ❌ Error en \"{keyword}\": {e}")
            continue

    # === FASE 2: VALIDACIÓN ===
    logger.info(f"\n📋 FASE 2: Validando {len(collected) - len(checked)} canales pendientes...\n")
    qualifying = validate_channels(collected)

    # === RESUMEN FINAL ===
    logger.info(f"\n{'='*50}")
    logger.info(f"📊 RESUMEN FINAL")
    logger.info(f"   Keywords completadas: {len(load_lines(COMPLETED_SEARCHES_FILE))}/90")
    logger.info(f"   Canales recolectados: {len(collected)}")
    logger.info(f"   Canales validados: {len(load_lines(CHECKED_IDS_FILE))}")
    logger.info(f"   Canales qualifying: {len(qualifying)}/{TARGET_CHANNELS}")
    logger.info(f"   Quota usada: {units_used}/{DAILY_QUOTA}")

    if units_used >= DAILY_QUOTA:
        logger.warning("\n⚠️ Cuota diaria alcanzada. Ejecuta de nuevo mañana para continuar.")

    return qualifying


if __name__ == "__main__":
    setup_logging()
    run_scraper()