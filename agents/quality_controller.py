# agents/quality_controller.py
import json
import os
from llm_client import call_llm_json

DATA_DIR = "data"
QC_DIR = os.path.join(DATA_DIR, "quality_checks")


SYSTEM_PROMPT = """You are a senior YouTube creative director who has grown multiple faceless channels past 1M subscribers. Your job is to evaluate each video's assets BEFORE production and catch issues that kill retention and revenue.

You will receive the script, SEO data, and thumbnail concept. Evaluate with zero tolerance for mediocrity.

═══════════════════════════════════════════════
SCORING CRITERIA (1-10 each)
═══════════════════════════════════════════════

1. HOOK (0-30s retention)
   - Does the first sentence deliver EXACTLY what the thumbnail promised? (thumbnail-hook alignment)
   - Is there a pattern interrupt in the first 15 seconds?
   - Is there at least one open loop planted before 30 seconds?
   - Does the primary keyword appear within 30 seconds?
   - Score 1-4 if none of these. Score 7+ only if ALL are present.

2. OPEN LOOPS & TENSION
   - Are 2+ open loops planted in the first 90 seconds?
   - Are ALL open loops resolved before the CTA?
   - Does the script use the curiosity gap throughout?
   - Score 1-4 if no open loops. Score 8+ only if planted AND resolved properly.

3. PATTERN INTERRUPTS
   - Are there pattern interrupts every 90-120 seconds?
   - Are they genuinely disruptive (stat, rhetorical question, plot twist) or just filler?
   - Score below 6 if fewer than 3 pattern interrupts in a 10-min script.

4. 65% RESCUE
   - Is there a clear re-engagement moment at approximately 55-65% of the script?
   - Does it recontextualize earlier info, reveal something unexpected, or escalate tension?
   - Score max 5 if this section is absent or weak.

5. TTS OPTIMIZATION
   - Are sentences consistently under 15 words?
   - Are contractions used throughout?
   - Are pause markers (...) and emphasis (CAPS) used appropriately?
   - Are forbidden phrases absent ("In this video", "Hey guys", "Don't forget to subscribe")?
   - Score below 6 if TTS rules are frequently violated.

6. SEO ALIGNMENT
   - Does the title front-load the primary keyword?
   - Is the description compelling above the fold?
   - Does the thumbnail text COMPLEMENT (not repeat) the title?

7. THUMBNAIL CTR POTENTIAL
   - Is it simple (max 3 visual elements)?
   - Is text max 5 words and readable at mobile size?
   - Does it provoke curiosity, surprise, or urgency?
   - Is it 100% faceless?

8. OVERALL COHERENCE
   - Do the title, thumbnail text, hook, and content all deliver on the same promise?
   - Would a viewer who clicked feel the video delivered what it promised?

═══════════════════════════════════════════════
VERDICT THRESHOLDS
═══════════════════════════════════════════════
APPROVED  → average >= 7.0 AND no individual score below 5
REVISE    → average 5.0-6.9 OR any individual score below 5
REJECTED  → average < 5.0 OR hook score <= 3 OR open_loops score <= 3

For REVISE or REJECTED: provide EXACT changes, not vague suggestions.
BAD:  "Improve the hook"
GOOD: "Replace opening sentence with direct delivery of thumbnail promise. Current: 'X'. Change to: 'Y'."

Respond ONLY with valid JSON:
{
  "video_id": "string",
  "puntuaciones": {
    "hook": int,
    "open_loops": int,
    "pattern_interrupts": int,
    "rescate_65": int,
    "tts_optimization": int,
    "seo": int,
    "thumbnail": int,
    "coherencia": int
  },
  "media": float,
  "veredicto": "APPROVED|REVISE|REJECTED",
  "resumen": "string (2-3 sentences, brutally honest)",
  "puntos_fuertes": ["string"],
  "puntos_debiles": ["string"],
  "cambios_requeridos": [
    {
      "area": "string (hook|open_loops|pattern_interrupts|rescate_65|tts|seo|thumbnail|coherencia)",
      "problema": "string (specific, not vague)",
      "solucion": "string (exact change with before/after if possible)"
    }
  ]
}"""


def run_quality_check(video_result: dict) -> dict:
    """Runs quality check on a processed video."""
    os.makedirs(QC_DIR, exist_ok=True)

    video_id = video_result.get("video_id", "unknown")
    print(f"🔍 [Quality Controller] Reviewing {video_id}...")

    results = video_result.get("results", {})
    errors = video_result.get("errors", {})

    script_data = results.get("script", {})
    seo_data = results.get("seo", {})
    thumbnail_data = results.get("thumbnail", {})

    # Build script summary
    guion_resumen = ""
    if script_data:
        hook = script_data.get("hook", "")
        if isinstance(hook, dict):
            hook = hook.get("texto", "N/A")
        guion_resumen = f"""
HOOK TEXT (first 400 chars): {str(hook)[:400]}
TOTAL WORDS: {script_data.get('palabras_totales', 'N/A')}
HOOK TECHNIQUE: {script_data.get('tecnica_hook', 'N/A')}
OPEN LOOPS PLANTED: {json.dumps(script_data.get('open_loops_planted', []), ensure_ascii=False)}
PATTERN INTERRUPTS COUNT: {script_data.get('pattern_interrupts_count', 'N/A')}
HAS 65% RESCUE: {script_data.get('has_65_percent_rescue', 'N/A')}
RETENTION BUMPS: {json.dumps(script_data.get('retention_bumps', []), ensure_ascii=False)}
SCRIPT SAMPLE (first 800 chars): {script_data.get('guion_completo', '')[:800]}..."""

    # Build SEO summary
    seo_resumen = ""
    if seo_data:
        seo_resumen = f"""
RECOMMENDED TITLE: {seo_data.get('titulo_recomendado', 'N/A')}
ALL TITLE VARIANTS: {json.dumps(seo_data.get('titulos', []), ensure_ascii=False)}
PRIMARY KEYWORD: {seo_data.get('keyword_principal', 'N/A')}
SECONDARY KEYWORDS: {json.dumps(seo_data.get('keywords_secundarias', []), ensure_ascii=False)}
TAGS (first 10): {', '.join(seo_data.get('tags', [])[:10])}
THUMBNAIL TEXT: {seo_data.get('texto_thumbnail', 'N/A')}
DESCRIPTION (first 300 chars): {seo_data.get('descripcion', '')[:300]}..."""

    # Build thumbnail summary
    thumb_resumen = ""
    if thumbnail_data:
        concepto = thumbnail_data.get("concepto", {})
        thumb_resumen = f"""
CONCEPT: {concepto.get('descripcion', 'N/A')}
MAIN ELEMENTS: {', '.join(concepto.get('elementos_principales', []))}
COLOR SCHEME: {concepto.get('esquema_colores', 'N/A')}
OVERLAY TEXT: {concepto.get('texto_overlay', 'N/A')}
STYLE: {thumbnail_data.get('estilo', 'N/A')}
IMAGE GENERATED: {'Yes' if thumbnail_data.get('imagen_path') else 'No'}"""

    errores_info = ""
    if errors:
        errores_info = f"\n⚠️ FAILED AGENTS: {', '.join(errors.keys())} — score those areas max 3"

    user_prompt = f"""Evaluate this YouTube video's assets:

VIDEO ID: {video_id}
ORIGINAL VIDEO DATA: {json.dumps(video_result.get('video_data', {}), ensure_ascii=False)}

═══ SCRIPT ═══{guion_resumen if guion_resumen else ' NOT AVAILABLE (agent failed)'}

═══ SEO ═══{seo_resumen if seo_resumen else ' NOT AVAILABLE (agent failed)'}

═══ THUMBNAIL ═══{thumb_resumen if thumb_resumen else ' NOT AVAILABLE (agent failed)'}
{errores_info}

Check thumbnail-hook alignment specifically: does the first sentence of the script deliver what the thumbnail overlay text promises?
For cambios_requeridos: provide exact text replacements where possible, not generic advice."""

    result = call_llm_json(
        agent_name="quality_controller",
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.3
    )

    result["video_id"] = video_id

    # Calculate average
    puntuaciones = result.get("puntuaciones", {})
    if puntuaciones:
        valores = [v for v in puntuaciones.values() if isinstance(v, (int, float))]
        result["media"] = round(sum(valores) / len(valores), 1) if valores else 0

    veredicto = result.get("veredicto", "REVISE")

    # Print results — fixed: print IS inside the loop
    print(f"\n   {'─'*38}")
    print(f"   📊 QUALITY CHECK — {video_id}")
    print(f"   {'─'*38}")
    for k, v in puntuaciones.items():
        v_int = int(v) if isinstance(v, (str, float)) else v
        barra = "█" * v_int + "░" * (10 - v_int)
        print(f"   {k:20s} [{barra}] {v_int}/10")
    print(f"   {'─'*38}")
    print(f"   📈 Average: {result.get('media', 'N/A')}")

    emoji = {"APPROVED": "✅", "REVISE": "⚠️", "REJECTED": "❌"}.get(veredicto, "❓")
    print(f"   {emoji} Verdict: {veredicto}")
    print(f"   💬 {result.get('resumen', '')}")

    cambios = result.get("cambios_requeridos", [])
    if cambios:
        print(f"\n   🔧 Required changes:")
        for c in cambios:
            print(f"      • [{c.get('area', '?')}] {c.get('problema', '')}")
            print(f"        → {c.get('solucion', '')}")

    # Save
    output_file = os.path.join(QC_DIR, f"{video_id}_qc.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n   💾 Saved: {output_file}")
    return result


if __name__ == "__main__":
    import sys

    VIDEO_OUTPUT_DIR = os.path.join(DATA_DIR, "videos_output")

    video_num = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    video_id = f"video_{video_num:02d}"

    video_file = os.path.join(VIDEO_OUTPUT_DIR, f"{video_id}.json")
    if not os.path.exists(video_file):
        print(f"❌ {video_file} not found. Run the pipeline for {video_id} first.")
        sys.exit(1)

    with open(video_file, "r", encoding="utf-8") as f:
        video_result = json.load(f)

    print(f"🎯 Running Quality Check for {video_id}")
    resultado = run_quality_check(video_result)
    print(json.dumps(resultado, indent=2, ensure_ascii=False))