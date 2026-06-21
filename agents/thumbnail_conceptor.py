# agents/thumbnail_conceptor.py
import logging
from logging_setup import setup_logging
import json
import os
import base64
import requests
from config import ABACUS_API_KEY, DATA_DIR
from llm_client import call_llm_json
from prompt_utils import format_qc_feedback
logger = logging.getLogger(__name__)

THUMBNAILS_DIR = os.path.join(DATA_DIR, "thumbnails")

# Hook technique → visual style mapping
HOOK_VISUAL_MAP = {
    "stat": {
        "style": "giant number as hero element taking 50% of frame, clean minimal background, number rendered in bold impact typography",
        "colors": "dark background (#1a1a2e), bright yellow or white number, high contrast",
        "text_treatment": "the stat number dominates — surrounding text is secondary and small",
        "composition": "number centered or left-aligned, supporting text bottom or right"
    },
    "contrarian": {
        "style": "bold red WRONG stamp or large red X over a common belief, crossed-out visual element",
        "colors": "red and black dominant (#c0392b, #1a1a1a), white text for contrast",
        "text_treatment": "aggressive, confrontational — use bold caps, possibly with strikethrough element",
        "composition": "diagonal red stamp overlapping main element, creates visual tension"
    },
    "scenario": {
        "style": "split screen divided by a clean vertical or diagonal line — before state left, after state right",
        "colors": "left side muted/desaturated, right side vibrant — creates instant visual contrast",
        "text_treatment": "BEFORE / AFTER labels or two contrasting short phrases on each side",
        "composition": "strong center divider, equal visual weight both sides, icons or symbols not faces"
    },
    "challenge": {
        "style": "bold arrow or pointing element directing attention to the main text, direct confrontational layout",
        "colors": "orange and black (#e67e22, #1a1a1a) or yellow and black for maximum CTR",
        "text_treatment": "imperative language — STOP, DO THIS, FIX THIS — large and unmissable",
        "composition": "arrow from edge pointing inward toward text, creates movement and urgency"
    },
    "counterintuitive": {
        "style": "unexpected visual juxtaposition — two opposing elements side by side with VS or question mark",
        "colors": "blue and orange contrast (#2980b9, #e67e22) — maximally opposite on color wheel",
        "text_treatment": "question mark as visual anchor, or short paradoxical phrase",
        "composition": "two elements in tension, question mark or VS as bridge between them"
    },
    "reveal": {
        "style": "spotlight or beam of light on central element, rest of frame in darkness — theatrical reveal composition",
        "colors": "dark vignette background (#0d0d0d), warm spotlight (#f39c12 to #ffffff), element in center glow",
        "text_treatment": "minimal text — let the visual do the work, text in bright spotlight area",
        "composition": "central element illuminated, radiating light effect, text within lit zone"
    },
    "urgency": {
        "style": "bold warning colors, clock or countdown element, alarm/warning iconography",
        "colors": "red dominant (#e74c3c, #c0392b), white text, possible yellow accent for warning",
        "text_treatment": "all caps, exclamation optional, creates time pressure feeling",
        "composition": "warning icon top-left or top-right, text large and centered, red fills background"
    },
    "cliffhanger": {
        "style": "partially obscured or blurred key element with large question mark overlay, creates irresistible curiosity",
        "colors": "dark mysterious palette (#1a1a2e, #16213e), with one bright teaser element",
        "text_treatment": "incomplete sentence or ellipsis — 'You Won't Believe...' or '???'",
        "composition": "blurred/pixelated focal element center, question marks surrounding, moody atmosphere"
    }
}


SYSTEM_PROMPT = """You are an expert YouTube thumbnail designer who consistently achieves 8-12% CTR on faceless channels. You understand that a thumbnail has ONE job: make someone stop scrolling and click.

Your thumbnails work because they follow a precise visual system — not because they look pretty.

═══════════════════════════════════════════════
CTR PRINCIPLES
═══════════════════════════════════════════════

1. THE 3-ELEMENT RULE: Maximum 3 visual elements. Viewers decide in 0.3 seconds — complexity kills clicks.

2. MOBILE-FIRST: 60%+ of YouTube views are on mobile. If text isn't readable at 120px wide, it doesn't exist. Test mentally: shrink the thumbnail to a postage stamp — what survives?

3. HOOK-THUMBNAIL ALIGNMENT: The thumbnail and the video's hook technique must feel like the same promise. A stat hook pairs with a giant number. A contrarian hook needs a red X or WRONG stamp. This alignment is what makes the click feel satisfying.

4. TITLE COMPLEMENT: The thumbnail text and video title must create a CURIOSITY GAP together — neither makes full sense without the other. Together they form one compelling message.
   BAD:  Title: "7 Money Habits That Keep You Poor" + Thumbnail: "7 HABITS" (repetition)
   GOOD: Title: "7 Money Habits That Keep You Poor" + Thumbnail: "STOP #3" (creates a mystery)

5. COLOR PSYCHOLOGY: Pick 2 colors maximum. High contrast wins. Yellow/black, red/white, blue/orange — these combinations are scientifically tested for attention capture.

6. NO FACES: This is a faceless channel. Use icons, objects, symbols, charts, text, and abstract elements. Faceless thumbnails that perform: bold text on solid color, before/after splits, stat callouts, warning/alarm iconography.

═══════════════════════════════════════════════
IDEOGRAM PROMPT ENGINEERING
═══════════════════════════════════════════════

Ideogram 3.0 renders text INSIDE images better than any other model. Exploit this.

Structure your Ideogram prompt as:
"YouTube thumbnail, [specific style], [background description], [main visual element], bold text '[EXACT TEXT]' [position and styling], [typography details], [color scheme with specific colors], no human faces, no photorealistic people, high contrast, professional, 16:9 aspect ratio"

Ideogram responds well to:
- Specific typography: "bold condensed sans-serif", "impact font style", "thick stroke outline on text"
- Specific colors: "deep navy blue #1a1a2e background" rather than just "dark blue"
- Clear composition: "text centered", "element bottom-right", "split vertically"
- Style adjectives: "flat design", "bold graphic", "minimalist", "poster style"

Respond ONLY with valid JSON:
{
  "video_id": "string",
  "concepto": {
    "descripcion": "string (1-2 sentences describing the visual concept)",
    "elementos_principales": ["string (max 3 elements)"],
    "esquema_colores": "string (specific colors with hex codes)",
    "texto_overlay": "string (exact text on thumbnail, max 5 words)",
    "composicion": "string (how elements are arranged)"
  },
  "prompt_imagen": "string (complete Ideogram-optimized prompt, 80-150 words, in English)",
  "estilo": "flat design|bold graphic|minimalist|poster style|3d render",
  "justificacion_ctr": "string (why this specific concept will generate high CTR)",
  "notas": ["string (2-3 production notes)"]
}"""


def get_hook_visual_context(hook_tecnica: str) -> str:
    """Returns visual guidance for the given hook technique."""
    mapping = HOOK_VISUAL_MAP.get(hook_tecnica, {})
    if not mapping:
        return ""
    return f"""
HOOK TECHNIQUE VISUAL GUIDE for '{hook_tecnica}':
- Style: {mapping['style']}
- Colors: {mapping['colors']}
- Text treatment: {mapping['text_treatment']}
- Composition: {mapping['composition']}"""


def generate_thumbnail_image(prompt: str, video_id: str) -> str | None:
    """Generates thumbnail image using Ideogram via Abacus API."""
    headers = {
        "Authorization": f"Bearer {ABACUS_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "ideogram",
        "messages": [{"role": "user", "content": prompt}],
        "modalities": ["image"],
        "image_config": {
            "num_images": 1,
            "aspect_ratio": "16x9"
        }
    }

    try:
        response = requests.post(
            "https://routellm.abacus.ai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=180
        )
        response.raise_for_status()
        data = response.json()

        message = data["choices"][0]["message"]
        images = message.get("images", [])

        if not images:
            logger.warning(f"   ⚠️ No image in response. Keys: {list(message.keys())}")
            return None

        img_data = images[0]
        img_b64 = None
        img_url = None

        if isinstance(img_data, dict):
            url_str = img_data.get("image_url", {}).get("url", "")
            if url_str.startswith("data:image"):
                img_b64 = url_str.split(",", 1)[1]
            elif url_str.startswith("http"):
                img_url = url_str
        elif isinstance(img_data, str):
            img_url = img_data if img_data.startswith("http") else None
            img_b64 = img_data if not img_data.startswith("http") else None

        img_path = os.path.join(THUMBNAILS_DIR, f"{video_id}_thumbnail.png")

        if img_b64:
            with open(img_path, "wb") as f:
                f.write(base64.b64decode(img_b64))
            logger.info(f"   🖼️ Image saved (base64): {img_path}")
            return img_path
        elif img_url:
            img_response = requests.get(img_url, timeout=60)
            with open(img_path, "wb") as f:
                f.write(img_response.content)
            logger.info(f"   🖼️ Image saved (url): {img_path}")
            return img_path

        return None

    except Exception as e:
        logger.error(f"   ❌ Image generation error: {e}")
        return None


def run_thumbnail_conceptor(video_data: dict, video_id: str, feedback: list | None = None,
                            seo_data: dict | None = None) -> dict:
    """Generates concept + image for the thumbnail.

    Depends on the SEO output: `seo_data` is received in memory from the
    orchestrator; if absent (standalone run), it falls back to the cached file.
    If `feedback` (Quality Controller changes) is provided, this is a
    re-generation that must address those specific fixes.
    """
    os.makedirs(THUMBNAILS_DIR, exist_ok=True)

    titulo = video_data.get('titulo', '')
    hook_tecnica = video_data.get('hook_tecnica', '')
    thumbnail_concepto = video_data.get('thumbnail_concepto', '')

    logger.info(f"🎨 [Thumbnail] Designing thumbnail for {video_id}: {titulo}")

    # SEO context: prefer the in-memory data passed by the orchestrator;
    # fall back to the cached file for standalone runs.
    if seo_data is None:
        seo_file = os.path.join(DATA_DIR, "seo", f"{video_id}.json")
        if os.path.exists(seo_file):
            with open(seo_file, "r", encoding="utf-8") as f:
                seo_data = json.load(f)
    texto_seo = ""
    titulo_seo = ""
    if seo_data:
        texto_seo = seo_data.get("texto_thumbnail", "")
        titulo_seo = seo_data.get("titulo_recomendado", "")

    # Get hook visual context
    hook_visual = get_hook_visual_context(hook_tecnica)

    user_prompt = f"""Design the thumbnail for this YouTube video:

TITLE: {titulo}
SEO TITLE (recommended): {titulo_seo if titulo_seo else titulo}
FORMAT: {video_data.get('formato', '')}
ANGLE: {video_data.get('angulo', '')}
HOOK TECHNIQUE: {hook_tecnica}
STRATEGIST THUMBNAIL CONCEPT: {thumbnail_concepto if thumbnail_concepto else 'Not provided'}
SEO THUMBNAIL TEXT: {texto_seo if texto_seo else 'Not provided'}
DESCRIPTION: {video_data.get('descripcion_breve', '')}
VIDEO ID: {video_id}
{hook_visual}

DESIGN REQUIREMENTS:
- Max 3 visual elements (no faces, no real people)
- Thumbnail text must COMPLEMENT the title — not repeat it
- Text must be readable at 120px wide (mobile size)
- Use the hook technique visual guide above for style and color decisions
- If a strategist concept was provided ("{thumbnail_concepto}"), use it as the visual anchor
- If SEO thumbnail text was provided ("{texto_seo}"), use it as the overlay text unless you have a stronger option

Write a detailed Ideogram 3.0 prompt (80-150 words) that specifies: exact text, typography style, colors with hex codes, composition, style. Be specific — Ideogram performs best with precise instructions."""

    user_prompt += format_qc_feedback(feedback)
    if feedback:
        logger.info(f"   🔧 Regenerating with {len(feedback)} QC fix(es)")

    result = call_llm_json(
        agent_name="thumbnail_conceptor",
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.7
    )

    result["video_id"] = video_id
    result["hook_tecnica"] = hook_tecnica

    # Generate image
    prompt = result.get("prompt_imagen", "")
    if prompt:
        logger.info(f"   🖌️ Generating image with Ideogram 3.0 (technique: {hook_tecnica})...")
        img_path = generate_thumbnail_image(prompt, video_id)
        result["imagen_path"] = img_path
    else:
        logger.warning("   ⚠️ No image prompt generated.")
        result["imagen_path"] = None

    # Save concept
    output_file = os.path.join(THUMBNAILS_DIR, f"{video_id}_concept.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    concepto = result.get("concepto", {})
    logger.info(f"   ✅ [Thumbnail] Saved: {output_file}")
    logger.info(f"   🎨 Text: '{concepto.get('texto_overlay', 'N/A')}' | Colors: {concepto.get('esquema_colores', 'N/A')}")
    logger.info(f"   💡 CTR rationale: {result.get('justificacion_ctr', 'N/A')}")
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

    logger.info(f"🎯 Running Thumbnail Conceptor for {video_id}: {video_data.get('titulo', '')}")
    resultado = run_thumbnail_conceptor(video_data, video_id)
    logger.info(json.dumps(resultado, indent=2, ensure_ascii=False))