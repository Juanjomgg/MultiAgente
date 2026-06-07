# agents/content_strategist.py
import json
import os
from collections import Counter
from llm_client import call_llm_json

DATA_DIR = "data"
VALIDATED_NICHES_FILE = os.path.join(DATA_DIR, "validated_niches.json")
CONTENT_CALENDAR_FILE = os.path.join(DATA_DIR, "content_calendar.json")

HOOK_TECHNIQUES = [
    "stat",           # Shocking statistic: "73% of people who do X never achieve Y"
    "contrarian",     # "Everything you know about X is wrong"
    "scenario",       # "In 2019, a man did X. What happened next changed everything."
    "challenge",      # Direct challenge: "You're doing X wrong. Here's proof."
    "counterintuitive", # "The less you do X, the more Y you get"
    "reveal",         # "I'm going to show you what most [experts] don't want you to know"
    "urgency",        # "Right now, while you're watching this, X is happening to you"
    "cliffhanger",    # "Before I tell you the answer, you need to understand why most people get this catastrophically wrong"
]


def load_winning_niche():
    """Loads the winning niche from the Niche Validator."""
    with open(VALIDATED_NICHES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    ganador_nombre = data.get("nicho_ganador")
    if not ganador_nombre:
        raise ValueError("❌ No winning niche in validated_niches.json.")

    nicho_completo = None
    for n in data.get("nichos_validados", []):
        if n.get("nombre") == ganador_nombre:
            nicho_completo = n
            break

    return {
        "nombre": ganador_nombre,
        "justificacion": data.get("justificacion_ganador", ""),
        "top_3": data.get("top_3_recomendados", []),
        "detalle": nicho_completo
    }


SYSTEM_PROMPT = """You are an elite YouTube content strategist who has built multiple faceless channels from 0 to 500K+ subscribers. You think in systems, not individual videos.

Your job: create a 30-video content calendar that functions as a MACHINE — each video feeds the algorithm, builds on the previous ones, and is engineered to rank.

═══════════════════════════════════════════════
STRATEGIC RULES
═══════════════════════════════════════════════

1. FIRST 10 VIDEOS = ALGORITHM TRAINING
   These must target the highest-volume keywords in the niche. YouTube needs to understand what the channel is about. No experimental formats — use proven formats (listicle, how-to) with high-volume keywords.

2. PILLAR STRATEGY (mandatory)
   Group all 30 videos into exactly 4-5 content pillars. Each pillar is a sub-topic cluster. YouTube's algorithm rewards channels that own a topic cluster — not channels that post randomly.
   Example for personal finance: Pillar 1=Budgeting, Pillar 2=Investing, Pillar 3=Income, Pillar 4=Mindset
   Each pillar must have 5-8 videos. The algorithm uses this to recommend your videos to viewers of similar channels.

3. ANGLE UNIQUENESS (non-negotiable)
   Every video must have a DIFFERENT angle. Before assigning an angle, ask: "If someone already watched a video titled X on this topic, why would they still watch THIS?" The answer IS the angle.
   WEAK angle: "Tips for saving money"
   STRONG angle: "Why people with budgets save LESS than people without them (counterintuitive study)"

4. HOOK TECHNIQUE ROTATION
   Use a variety of hook techniques across the 30 videos. Max 5 uses of any single technique.
   Available techniques: stat, contrarian, scenario, challenge, counterintuitive, reveal, urgency, cliffhanger
   The hook_inicial must be: max 15 words, TTS-ready (contractions, no complex words), and must PLANT AN OPEN LOOP.

5. SEARCH INTENT MAPPING
   Every video needs a primary keyword mapped to a search intent:
   - informational: "how does X work", "what is X"
   - commercial: "best X", "X review", "X vs Y"
   - navigational: brand/tool-specific queries
   First 10 videos = informational (higher volume). Mix commercial in videos 11-30.

6. THUMBNAIL ALIGNMENT FROM DAY ONE
   Each video entry must include a thumbnail_concepto (3-5 words) that pairs visually with the hook. The script writer will use this to ensure thumbnail-hook alignment — the #1 retention factor in the first 30 seconds.

7. PROGRESSION LOGIC
   Videos 1-10: Broad topics, maximum volume, prove the channel to the algorithm
   Videos 11-20: Specific sub-topics, build authority within each pillar
   Videos 21-30: Niche-deep, high-CPM topics, monetization-optimized content

═══════════════════════════════════════════════
CHANNEL STRATEGY OUTPUT
═══════════════════════════════════════════════

"estrategia_canal": {
  "nombre_canal_sugerido": "string (3 options separated by |, each under 30 chars, memorable, niche-clear)",
  "descripcion_canal": "string (1 sentence, what the channel does for the viewer)",
  "propuesta_valor": "string (why this channel over the 1000 others in this niche)",
  "pilares_contenido": [
    {
      "id": "string (pilar_1, pilar_2...)",
      "nombre": "string",
      "descripcion": "string (1 sentence)",
      "porcentaje_contenido": int,
      "keywords_cluster": ["string (5 core keywords for this pillar)"]
    }
  ],
  "frecuencia_publicacion": "string",
  "mejor_horario_publicacion": "string (based on US audience)",
  "tono_y_estilo": "string"
}

═══════════════════════════════════════════════
CALENDAR ITEM OUTPUT (repeat x30)
═══════════════════════════════════════════════

{
  "dia": int,
  "titulo": "string (English, max 60 chars, primary keyword in first 3 words if possible)",
  "pilar": "string (must match one of the pilar IDs above)",
  "formato": "listicle|how-to|explicacion|comparativa|historia|caso_estudio",
  "angulo": "string (1 sentence: what makes this video different from every other video on this topic)",
  "keywords_objetivo": {
    "principal": "string (highest volume keyword, used in title)",
    "secundarias": ["string (3-4 related long-tail keywords)"],
    "intencion": "informational|commercial|navigational"
  },
  "duracion_estimada_min": int,
  "hook_tecnica": "stat|contrarian|scenario|challenge|counterintuitive|reveal|urgency|cliffhanger",
  "hook_inicial": "string (max 15 words, uses the specified technique, plants an open loop, TTS-ready with contractions)",
  "thumbnail_concepto": "string (3-5 words describing a high-CTR visual that pairs with this hook, faceless)",
  "descripcion_breve": "string (1-2 sentences, what value the viewer gets)"
}

CRITICAL: Generate ALL 30 videos. No placeholders. Verify before responding that:
- No two videos share the same angle
- No hook technique is used more than 5 times
- Each pilar has at least 5 videos
- Videos 1-10 all target informational intent with high-volume keywords"""


def validate_calendar(calendario: list) -> list:
    """
    Guardrails: checks angle uniqueness and hook technique distribution.
    Returns a list of warnings.
    """
    warnings = []

    # Check hook technique distribution
    tecnicas = [v.get("hook_tecnica", "unknown") for v in calendario]
    counts = Counter(tecnicas)
    for tecnica, count in counts.items():
        if count > 5:
            warnings.append(f"⚠️  Hook technique '{tecnica}' used {count} times (max 5). Consider diversifying.")

    # Check for duplicate angles (simple keyword overlap check)
    angulos = [v.get("angulo", "").lower() for v in calendario]
    for i, a1 in enumerate(angulos):
        for j, a2 in enumerate(angulos):
            if i >= j:
                continue
            # Simple overlap: if 4+ consecutive words match, flag it
            words1 = set(a1.split())
            words2 = set(a2.split())
            overlap = words1 & words2
            if len(overlap) > 6 and len(words1) > 3:
                warnings.append(
                    f"⚠️  Videos {i+1} and {j+1} may have overlapping angles. "
                    f"Shared words: {', '.join(list(overlap)[:5])}"
                )

    # Check pilar distribution
    pilares = [v.get("pilar", "unknown") for v in calendario]
    pilar_counts = Counter(pilares)
    for pilar, count in pilar_counts.items():
        if count < 4:
            warnings.append(f"⚠️  Pilar '{pilar}' has only {count} videos — too thin for algorithm clustering.")

    # Check first 10 are informational
    for i, v in enumerate(calendario[:10]):
        kw = v.get("keywords_objetivo", {})
        if isinstance(kw, dict) and kw.get("intencion") != "informational":
            warnings.append(f"⚠️  Video {i+1} is not informational intent — algorithm training phase requires informational.")

    return warnings


def run_content_strategist() -> dict:
    """Runs the Content Strategist and generates the editorial calendar."""
    print("🗓️ [Content Strategist] Loading winning niche...")
    niche_data = load_winning_niche()
    print(f"📌 [Content Strategist] Niche: {niche_data['nombre']}")

    user_prompt = f"""Create a 30-video content calendar for a FACELESS English-language YouTube channel in this niche:

WINNING NICHE: {niche_data['nombre']}
JUSTIFICATION: {niche_data['justificacion']}
VALIDATION DATA: {json.dumps(niche_data['detalle'], indent=2, ensure_ascii=False) if niche_data['detalle'] else 'Not available'}

REQUIREMENTS:
- 30 videos, one per day
- All titles in English, max 60 characters
- 100% faceless format
- First 10 videos: informational intent, highest-volume keywords
- Every hook_inicial: max 15 words, plants an open loop, uses the specified hook_tecnica
- No two videos share the same angle
- Hook techniques distributed: no single technique used more than 5 times
- Each pilar minimum 5 videos
- thumbnail_concepto must be 3-5 words describing a faceless visual

Available hook techniques: {', '.join(HOOK_TECHNIQUES)}

Generate the complete channel strategy and all 30 calendar entries. No placeholders."""

    result = call_llm_json(
        agent_name="content_strategist",
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.7
    )

    calendario = result.get("calendario", [])

    # Normalize keywords_objetivo: handle both dict and list formats
    for video in calendario:
        kw = video.get("keywords_objetivo", {})
        if isinstance(kw, list):
            # LLM returned a list instead of dict — normalize it
            video["keywords_objetivo"] = {
                "principal": kw[0] if kw else "",
                "secundarias": kw[1:] if len(kw) > 1 else [],
                "intencion": "informational"
            }

    # Guardrail: count check
    if len(calendario) < 30:
        print(f"⚠️ [Content Strategist] Only {len(calendario)}/30 videos generated.")

    # Guardrail: validate calendar quality
    if calendario:
        warnings = validate_calendar(calendario)
        if warnings:
            print(f"\n⚠️ [Content Strategist] Calendar quality warnings:")
            for w in warnings:
                print(f"   {w}")
        else:
            print(f"✅ [Content Strategist] Calendar passed all quality checks.")

    # Save
    with open(CONTENT_CALENDAR_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n✅ [Content Strategist] Calendar generated: {len(calendario)} videos.")
    print(f"   Saved to {CONTENT_CALENDAR_FILE}")

    estrategia = result.get("estrategia_canal", {})
    if estrategia:
        print(f"   📺 Channel names: {estrategia.get('nombre_canal_sugerido', 'N/A')}")
        print(f"   💎 Value prop: {estrategia.get('propuesta_valor', 'N/A')}")
        pilares = estrategia.get("pilares_contenido", [])
        for p in pilares:
            cluster = ', '.join(p.get('keywords_cluster', [])[:3])
            print(f"   📌 {p['nombre']} ({p.get('porcentaje_contenido', '?')}%) — {cluster}...")

    # Print hook technique distribution
    if calendario:
        tecnicas = Counter(v.get("hook_tecnica", "unknown") for v in calendario)
        print(f"\n   🎣 Hook technique distribution:")
        for t, c in sorted(tecnicas.items(), key=lambda x: -x[1]):
            bar = "█" * c
            print(f"      {t:20s} {bar} ({c})")

    return result


if __name__ == "__main__":
    resultado = run_content_strategist()
    print(json.dumps(resultado, indent=2, ensure_ascii=False))