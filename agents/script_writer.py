# agents/script_writer.py
import logging
from logging_setup import setup_logging
import json
import os
from llm_client import call_llm, call_llm_json
from prompt_utils import format_qc_feedback
from config import DATA_DIR
logger = logging.getLogger(__name__)

SCRIPTS_DIR = os.path.join(DATA_DIR, "scripts")

SCRIPT_PROMPT = """You are a world-class YouTube scriptwriter specializing in FACELESS channels that achieve 50%+ average view duration. Your scripts are engineered — not just written — using proven psychological retention mechanics.

═══════════════════════════════════════════════
CORE PRINCIPLES (memorize these)
═══════════════════════════════════════════════

1. OPEN LOOPS are your #1 tool. Plant 2-3 unresolved questions or promises in the first 90 seconds. Resolve them ONLY near the end. The viewer stays because their brain cannot tolerate unresolved tension.
   BAD:  "Today we'll cover 7 money habits."
   GOOD: "By the end of this video you'll understand why the habit at #4 is statistically the one keeping most people poor — and it's probably not what you think."

2. THUMBNAIL-HOOK ALIGNMENT. The FIRST sentence must deliver exactly what the thumbnail promised. If the thumbnail says "STOP THESE NOW", the first words must address THOSE specific things. Mismatch = instant click-off.

3. PATTERN INTERRUPTS every 90-120 seconds. The human brain disengages at a predictable rhythm. Every 90-120 seconds you MUST change the format: a surprising statistic, a rhetorical question directed at the viewer, a hypothetical scenario, a "but here's where it gets weird" pivot, a dramatic contrast. Mark these as [PATTERN INTERRUPT].

4. THE 65% RESCUE. Most viewers drop at 60-70% of runtime. Plant a "SECOND HOOK" at the 55-60% mark: reveal something unexpected, tease the most surprising item is coming, or deliver a plot twist about something mentioned earlier. This is non-negotiable.

5. TTS-OPTIMIZED WRITING. This will be narrated by AI text-to-speech. Rules:
   - Maximum 15 words per sentence. Hard limit.
   - Use "..." for a 1-second pause, "......" for a 2-second pause
   - Write CAPS for a word that should be emphasized (e.g. "This is CRITICAL.")
   - No tongue-twister consonant clusters
   - No parenthetical asides — they sound robotic in TTS
   - Spell out numbers under 13 (say "seven" not "7")
   - Contractions are MANDATORY (say "don't", "you're", "it's" — not "do not", "you are")

6. KEYWORD IN FIRST 30 SECONDS. The primary SEO keyword must appear naturally in spoken dialogue within the first 30 seconds. YouTube indexes transcriptions.

7. CURIOSITY GAP MANAGEMENT. Never fully satisfy curiosity on any point until you're ready to move on. End every section with either an unresolved question or a bridge that makes the next section feel essential.

═══════════════════════════════════════════════
MANDATORY STRUCTURE
═══════════════════════════════════════════════

=== HOOK (0:00 - 0:30) ===
PURPOSE: Stop the scroll. Retain the viewer past 30 seconds (YouTube's first measurement point).
REQUIREMENTS:
- Sentence 1: Deliver on the thumbnail promise IMMEDIATELY
- Sentence 2-3: Shocking stat, provocative claim, or counterintuitive scenario that creates pattern interrupt
- Sentence 4-5: Plant the MAIN open loop ("By the end of this video you'll know X... and X will change Y")
- Include the primary keyword naturally within these 30 seconds
- NO "hey guys welcome back" — delete all filler openers

=== INTRO (0:30 - 1:00) ===
PURPOSE: Establish credibility and raise stakes WITHOUT slowing pace.
REQUIREMENTS:
- Stakes amplifier: make the viewer feel this PERSONALLY applies to them right now
- Plant a SECONDARY open loop (something interesting you'll reveal mid-video)
- Keep it under 90 words — any longer and it feels like padding

=== SECTION 1 ===
(Continue numbering for each body section)
PURPOSE: Content delivery with engineered retention.
REQUIREMENTS:
- Start with a mini-hook that makes THIS section feel essential
- [PATTERN INTERRUPT] marker at 90-120 second intervals throughout the body
- Specific examples, data points, or micro-stories — not vague generalizations
- End with a BRIDGE: "But here's where most people get this completely wrong..."
  or "What I'm about to show you in the next section will change how you see this..."

=== SECTION 2 ===
... (repeat pattern)

=== THE 65% RESCUE ===
PURPOSE: Re-engage viewers who are about to leave.
REQUIREMENTS:
- Signal something surprising is coming: "I saved the most counterintuitive one for here..."
- Or reveal something that recontextualizes earlier information
- Or deliver a mini-plot-twist: "Remember what I said at the beginning? Well..."
- Must feel like a natural escalation, not a desperate grab

=== CTA + CLOSING ===
PURPOSE: Resolve all open loops. Convert to subscriber.
REQUIREMENTS:
- Resolve EVERY open loop planted earlier — viewers feel satisfied
- Natural CTA (never beg): "If this was useful, the algorithm really does reward a like — it takes two seconds."
- Tease the NEXT video with a new open loop: "In my next video I'll cover X — and X is something most people in [niche] never figure out."
- Last sentence should be memorable — a punchy takeaway or challenge

═══════════════════════════════════════════════
PRODUCTION MARKERS (use throughout)
═══════════════════════════════════════════════

[B-ROLL: precise visual description]     ← what appears on screen
[TEXT ON SCREEN: exact text to show]     ← lower thirds, callouts
[TRANSITION]                             ← cut or fade between sections
[PAUSE 1s] or [PAUSE 2s]                ← silence for dramatic effect
[EMPHASIS: word or phrase]              ← direct TTS to stress this
[PATTERN INTERRUPT]                     ← marks a deliberate engagement reset
[OPEN LOOP: description]                ← marks where you plant a loop
[CLOSE LOOP: description]               ← marks where you resolve it
[65% RESCUE]                            ← marks the re-engagement moment
[MUSIC CUE: mood]                       ← background music direction

═══════════════════════════════════════════════
WRITING RULES
═══════════════════════════════════════════════

VOICE: Conversational, direct, second-person ("you", "your"). Like a smart friend explaining something important.
PACE: Fast. No padding. Every sentence earns its place.
SPECIFICITY: Always specific over vague. "73% of Americans" beats "most people". "$2,400 per year" beats "a lot of money".
EMOTION: Target frustration, curiosity, and aspiration — in that order.
FORBIDDEN PHRASES: "In this video", "Today we're going to", "Hey guys", "Don't forget to subscribe", "So basically", "It's important to note that", "As you can see"

Format the script with === SECTION NAME === headers separating each section.
Write in PLAIN TEXT — no JSON, no markdown, no asterisks. Pure narration-ready script."""


METADATA_PROMPT = """Analyze the following YouTube script and return ONLY this JSON (no extra text, no markdown):
{
  "duracion_estimada_min": int,
  "palabras_totales": int,
  "tecnica_hook": "string (which specific hook technique was used)",
  "open_loops_planted": ["string (brief description of each open loop)"],
  "pattern_interrupts_count": int,
  "has_65_percent_rescue": true,
  "retention_bumps": ["string (list of retention mechanics used)"],
  "notas_produccion": ["string (3-5 key production notes for the editor)"]
}"""


def parse_script_sections(raw_script: str) -> dict:
    """Parses the plain-text script into structured sections."""
    sections = {"hook": "", "intro": "", "secciones": [], "cta_cierre": ""}

    current_section = None
    current_text = []
    section_count = 0

    for line in raw_script.split("\n"):
        line_upper = line.strip().upper()

        if "HOOK" in line_upper and "===" in line:
            if current_section and current_text:
                _save_section(sections, current_section, current_text, section_count)
            current_section = "hook"
            current_text = []
        elif "INTRO" in line_upper and "===" in line:
            if current_section and current_text:
                _save_section(sections, current_section, current_text, section_count)
            current_section = "intro"
            current_text = []
        elif any(kw in line_upper for kw in ("CTA", "CLOSING", "CIERRE", "OUTRO")) and "===" in line:
            if current_section and current_text:
                _save_section(sections, current_section, current_text, section_count)
            current_section = "cta_cierre"
            current_text = []
        elif "===" in line and len(line.strip()) > 6:
            if current_section and current_text:
                _save_section(sections, current_section, current_text, section_count)
            section_count += 1
            current_section = f"seccion_{section_count}"
            current_text = [line.strip().replace("=", "").strip()]
        else:
            if current_section:
                current_text.append(line)

    # Save last section
    if current_section and current_text:
        _save_section(sections, current_section, current_text, section_count)

    return sections


def _save_section(sections, section_name, text_lines, count):
    """Saves a parsed section."""
    text = "\n".join(text_lines).strip()
    if section_name == "hook":
        sections["hook"] = text
    elif section_name == "intro":
        sections["intro"] = text
    elif section_name == "cta_cierre":
        sections["cta_cierre"] = text
    elif section_name.startswith("seccion_"):
        title = text_lines[0].strip() if text_lines else f"Section {count}"
        body = "\n".join(text_lines[1:]).strip() if len(text_lines) > 1 else text
        sections["secciones"].append({
            "numero": count,
            "titulo_seccion": title,
            "texto": body
        })


def run_script_writer(video_data: dict, video_id: str, feedback: list | None = None) -> dict:
    """Generates a complete YouTube script in 2 phases.

    If `feedback` (Quality Controller changes) is provided, this is a
    re-generation that must address those specific fixes.
    """
    os.makedirs(SCRIPTS_DIR, exist_ok=True)

    titulo = video_data.get('titulo', 'Sin título')
    duracion = video_data.get('duracion_estimada_min', 10)

    logger.info(f"✍️ [Script Writer] Generating script for {video_id}: {titulo}")

    # Normalize keywords — handle both dict and list formats
    kw = video_data.get('keywords_objetivo', {})
    if isinstance(kw, dict):
        primary_kw = kw.get('principal', '')
        secondary_kws = ', '.join(kw.get('secundarias', []))
    else:
        primary_kw = kw[0] if kw else ''
        secondary_kws = ', '.join(kw[1:]) if len(kw) > 1 else ''

    hook_tecnica = video_data.get('hook_tecnica', '')
    thumbnail_concepto = video_data.get('thumbnail_concepto', '')

    # === PHASE 1: Plain-text script ===
    user_prompt = f"""Write the complete YouTube script for this video:

TITLE: {titulo}
FORMAT: {video_data.get('formato', 'explicacion')}
ANGLE: {video_data.get('angulo', '')}
PRIMARY KEYWORD: {primary_kw}
SECONDARY KEYWORDS: {secondary_kws}
HOOK TECHNIQUE TO USE: {hook_tecnica} — apply this specific technique for the hook
HOOK SUGGESTION: {video_data.get('hook_inicial', '')}
THUMBNAIL CONCEPT (align hook with this visual): {thumbnail_concepto}
TARGET DURATION: {duracion} minutes (~{duracion * 150} words)
VIDEO DESCRIPTION: {video_data.get('descripcion_breve', '')}

REQUIREMENTS:
- Primary keyword "{video_data.get('keywords_objetivo', [''])[0]}" must appear in the first 30 seconds
- Plant at least 2 open loops in the first 90 seconds
- Include [PATTERN INTERRUPT] every 90-120 seconds
- Include [65% RESCUE] at approximately the {int(duracion * 0.6)}-minute mark
- All production markers ([B-ROLL], [TEXT ON SCREEN], etc.) must be present throughout
- TTS-optimized: max 15 words per sentence, contractions mandatory
- Write the COMPLETE script word-for-word, ready for AI voiceover narration"""

    user_prompt += format_qc_feedback(feedback)
    if feedback:
        logger.info(f"   🔧 Regenerating with {len(feedback)} QC fix(es)")

    logger.info(f"   📝 Phase 1: Generating plain-text script...")
    raw_script = call_llm(
        agent_name="script_writer",
        system_prompt=SCRIPT_PROMPT,
        user_prompt=user_prompt,
        temperature=0.8
    )

    # === PHASE 2: Lightweight metadata JSON ===
    logger.info(f"   📊 Phase 2: Extracting metadata...")
    try:
        metadata = call_llm_json(
            agent_name="seo_optimizer",  # cheaper model for metadata
            system_prompt=METADATA_PROMPT,
            user_prompt=f"Script to analyze:\n\n{raw_script[:3000]}",
            temperature=0.3
        )
    except Exception as e:
        logger.warning(f"   ⚠️ Metadata failed, using defaults: {e}")
        metadata = {
            "duracion_estimada_min": duracion,
            "tecnica_hook": "unknown",
            "open_loops_planted": [],
            "pattern_interrupts_count": 0,
            "has_65_percent_rescue": False,
            "retention_bumps": [],
            "notas_produccion": []
        }

    # === Structure result ===
    sections = parse_script_sections(raw_script)
    palabras = len(raw_script.split())
    min_palabras = duracion * 100

    if palabras < min_palabras:
        logger.warning(f"   ⚠️ Script short: {palabras} words (minimum: {min_palabras})")

    result = {
        "video_id": video_id,
        "titulo": titulo,
        "duracion_estimada_min": metadata.get("duracion_estimada_min", duracion),
        "palabras_totales": palabras,
        "tecnica_hook": metadata.get("tecnica_hook", ""),
        "open_loops_planted": metadata.get("open_loops_planted", []),
        "pattern_interrupts_count": metadata.get("pattern_interrupts_count", 0),
        "has_65_percent_rescue": metadata.get("has_65_percent_rescue", False),
        "hook": sections.get("hook", ""),
        "intro": sections.get("intro", ""),
        "secciones": sections.get("secciones", []),
        "cta_cierre": sections.get("cta_cierre", ""),
        "guion_completo": raw_script,
        "retention_bumps": metadata.get("retention_bumps", []),
        "notas_produccion": metadata.get("notas_produccion", [])
    }

    # Save
    output_file = os.path.join(SCRIPTS_DIR, f"{video_id}.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    logger.info(f"   ✅ [Script Writer] Saved: {output_file} ({palabras} words)")
    logger.info(f"   🔁 Open loops: {len(result['open_loops_planted'])} | Pattern interrupts: {result['pattern_interrupts_count']} | 65% rescue: {result['has_65_percent_rescue']}")
    return result


if __name__ == "__main__":
    setup_logging()
    import sys

    # BUG FIX: define CONTENT_CALENDAR_FILE BEFORE using it
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

    logger.info(f"🎯 Running Script Writer for {video_id}: {video_data.get('titulo', '')}")
    resultado = run_script_writer(video_data, video_id)