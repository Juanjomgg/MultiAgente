# agents/seo_optimizer.py
import logging
from logging_setup import setup_logging
import json
import os
from llm_client import call_llm_json
from prompt_utils import format_qc_feedback
from config import DATA_DIR
logger = logging.getLogger(__name__)

SEO_DIR = os.path.join(DATA_DIR, "seo")


SYSTEM_PROMPT = """You are a YouTube SEO expert who has ranked hundreds of videos on the first page. You understand that SEO is not keyword stuffing — it's matching search intent with precision.

═══════════════════════════════════════════════
TITLE RULES (max 60 chars)
═══════════════════════════════════════════════
- Primary keyword in the FIRST 3 words when possible
- For listicles: lead with the number ("7 Money Habits...")
- For informational: lead with the keyword, add curiosity ("Personal Finance Mistakes Most People Make")
- For commercial: lead with keyword, add qualifier ("Best Budget Apps: Ranked by a Finance Nerd")
- NO clickbait that the video doesn't deliver on
- Generate 3 variants with different angles — not just different word order
- Each variant should feel like a genuinely different creative choice

═══════════════════════════════════════════════
DESCRIPTION RULES (max 5000 chars)
═══════════════════════════════════════════════
ABOVE THE FOLD (first 2 lines — most important):
- Line 1: Primary keyword + compelling one-sentence summary (this is what appears in search previews)
- Line 2: Secondary keyword + specific value promise ("In this video you'll learn exactly how to...")
- These 2 lines determine whether someone clicks through from search

BODY:
- Timestamps/chapters (essential for watch time and search features)
- 3-4 natural keyword mentions — not stuffed, read naturally when spoken aloud
- One CTA for subscription (not begging — value-framed: "Subscribe if you want more X")
- 2 placeholder links to related videos: [Related: VIDEO_TITLE_HERE]

FOOTER:
- 3 hashtags maximum — one broad (#personalfinance), one niche (#budgettips), one trending if applicable

═══════════════════════════════════════════════
TAGS RULES (max 500 total chars)
═══════════════════════════════════════════════
Order: exact primary keyword → phrase variations → related topics → long-tail questions
Include: the most common misspelling of the primary keyword if it gets searches
Exclude: irrelevant broad tags (never tag "YouTube" or "how to" alone)

═══════════════════════════════════════════════
THUMBNAIL TEXT RULES
═══════════════════════════════════════════════
- Max 5 words — ideally 3
- Must COMPLEMENT the title (never repeat it word for word)
- Must create a curiosity gap WITH the title — together they're more powerful than either alone
- Should match the hook technique used in the script (stat→show the number, contrarian→use "WRONG", challenge→use "STOP")
- High contrast, reads at 120px wide (mobile thumbnail size)

Respond ONLY with valid JSON:
{
  "video_id": "string",
  "titulos": [
    {
      "texto": "string",
      "caracteres": int,
      "keyword_posicion": "string (word position of primary keyword)",
      "angulo": "string (what makes this title variant different)"
    }
  ],
  "titulo_recomendado": "string",
  "descripcion": "string",
  "tags": ["string"],
  "tags_caracteres_total": int,
  "texto_thumbnail": "string (max 5 words)",
  "hashtags": ["string (3 hashtags)"],
  "keyword_principal": "string",
  "keywords_secundarias": ["string"],
  "intencion_busqueda": "informational|commercial|navigational",
  "notas_seo": ["string"]
}"""


def extract_keywords(video_data: dict) -> tuple[str, list[str], str]:
    """
    Extracts primary keyword, secondary keywords, and search intent
    from either the new dict format or the old list format.
    Returns: (primary, secondaries, intent)
    """
    kw = video_data.get("keywords_objetivo", {})

    if isinstance(kw, dict):
        primary = kw.get("principal", "")
        secondaries = kw.get("secundarias", [])
        intent = kw.get("intencion", "informational")
    elif isinstance(kw, list):
        # Backward compatibility with old list format
        primary = kw[0] if kw else ""
        secondaries = kw[1:] if len(kw) > 1 else []
        intent = "informational"
    else:
        primary = ""
        secondaries = []
        intent = "informational"

    return primary, secondaries, intent


def run_seo_optimizer(video_data: dict, video_id: str, feedback: list | None = None,
                      script_data: dict | None = None) -> dict:
    """Generates complete SEO optimization for a video.

    Depends on the script: `script_data` is received in memory from the
    orchestrator; if absent (standalone run), it falls back to the cached file.
    If `feedback` (Quality Controller changes) is provided, this is a
    re-generation that must address those specific fixes.
    """
    os.makedirs(SEO_DIR, exist_ok=True)

    logger.info(f"🏷️ [SEO Optimizer] Optimizing {video_id}: {video_data.get('titulo', '')}")

    primary_kw, secondary_kws, intent = extract_keywords(video_data)

    # Script context: prefer the in-memory data passed by the orchestrator;
    # fall back to the cached file for standalone runs.
    if script_data is None:
        script_file = os.path.join(DATA_DIR, "scripts", f"{video_id}.json")
        if os.path.exists(script_file):
            with open(script_file, "r", encoding="utf-8") as f:
                script_data = json.load(f)
    script_context = ""
    if script_data:
        script_context = f"\nSCRIPT HOOK: {str(script_data.get('hook', ''))[:300]}\nSCRIPT SAMPLE: {script_data.get('guion_completo', '')[:400]}..."

    user_prompt = f"""Generate complete SEO optimization for this YouTube video:

TITLE: {video_data.get('titulo', '')}
FORMAT: {video_data.get('formato', '')}
ANGLE: {video_data.get('angulo', '')}
HOOK TECHNIQUE: {video_data.get('hook_tecnica', 'N/A')}
PRIMARY KEYWORD: {primary_kw}
SECONDARY KEYWORDS: {', '.join(secondary_kws)}
SEARCH INTENT: {intent}
DURATION: {video_data.get('duracion_estimada_min', 10)} minutes
THUMBNAIL CONCEPT (from strategist): {video_data.get('thumbnail_concepto', 'N/A')}
VIDEO DESCRIPTION: {video_data.get('descripcion_breve', '')}
VIDEO ID: {video_id}
{script_context}

SPECIFIC INSTRUCTIONS:
- Primary keyword "{primary_kw}" must appear in the first 3 words of the recommended title
- Search intent is {intent} — adjust title style accordingly
- Thumbnail text must pair with the hook technique "{video_data.get('hook_tecnica', '')}" (e.g. stat→show a number, contrarian→use "WRONG", challenge→use "STOP")
- If a thumbnail concept was provided ("{video_data.get('thumbnail_concepto', '')}"), build on it for the thumbnail text
- Description line 1 must include "{primary_kw}" and work as a standalone search snippet
- Include timestamps as placeholders: 0:00 Intro, 1:00 [First Section], etc."""

    user_prompt += format_qc_feedback(feedback)
    if feedback:
        logger.info(f"   🔧 Regenerating with {len(feedback)} QC fix(es)")

    result = call_llm_json(
        agent_name="seo_optimizer",
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.5
    )

    # Guardrail: title length
    for t in result.get("titulos", []):
        chars = len(t.get("texto", ""))
        t["caracteres"] = chars
        if chars > 60:
            logger.warning(f"   ⚠️ Title too long ({chars} chars): {t['texto']}")

    # Guardrail: tags 500 char limit
    tags = result.get("tags", [])
    while sum(len(t) for t in tags) > 500:
        tags.pop()
    result["tags"] = tags
    result["tags_caracteres_total"] = sum(len(t) for t in tags)

    # Guardrail: thumbnail text length
    thumb_text = result.get("texto_thumbnail", "")
    if len(thumb_text.split()) > 5:
        result["texto_thumbnail"] = " ".join(thumb_text.split()[:5])
        logger.warning(f"   ⚠️ Thumbnail text trimmed to 5 words: {result['texto_thumbnail']}")

    result["video_id"] = video_id
    result["intencion_busqueda"] = intent

    # Save
    output_file = os.path.join(SEO_DIR, f"{video_id}.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    logger.info(f"   ✅ [SEO Optimizer] Saved: {output_file}")
    logger.info(f"   🏷️  Title: {result.get('titulo_recomendado', 'N/A')}")
    logger.info(f"   🖼️  Thumbnail text: {result.get('texto_thumbnail', 'N/A')}")
    return result


if __name__ == "__main__":
    setup_logging()
    import sys

    CONTENT_CALENDAR_FILE = os.path.join(DATA_DIR, "content_calendar.json")

    video_num = int(sys.argv[1]) if len(sys.argv) > 1 else 1

    with open(CONTENT_CALENDAR_FILE, "r", encoding="utf-8") as f:
        calendario = json.load(f)

    videos = calendario.get("calendario", [])
    if video_num < 1 or video_num > len(videos):
        logger.error(f"❌ Video {video_num} doesn't exist. Range: 1-{len(videos)}")
        sys.exit(1)

    video_data = videos[video_num - 1]
    video_id = f"video_{video_num:02d}"

    logger.info(f"🎯 Running SEO Optimizer for {video_id}: {video_data.get('titulo', '')}")
    resultado = run_seo_optimizer(video_data, video_id)
    logger.info(json.dumps(resultado, indent=2, ensure_ascii=False))