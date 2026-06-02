# agents/content_strategist.py
import json
import os
from llm_client import call_llm_json

DATA_DIR = "data"
VALIDATED_NICHES_FILE = os.path.join(DATA_DIR, "validated_niches.json")
CONTENT_CALENDAR_FILE = os.path.join(DATA_DIR, "content_calendar.json")


def load_winning_niche():
    """Carga el nicho ganador del Niche Validator."""
    with open(VALIDATED_NICHES_FILE, "r") as f:
        data = json.load(f)

    ganador_nombre = data.get("nicho_ganador")
    justificacion = data.get("justificacion_ganador", "")
    top_3 = data.get("top_3_recomendados", [])

    if not ganador_nombre:
        raise ValueError("❌ No hay nicho ganador en validated_niches.json.")

    # Buscar datos completos del nicho ganador
    nicho_completo = None
    for n in data.get("nichos_validados", []):
        if n.get("nombre") == ganador_nombre:
            nicho_completo = n
            break

    return {
        "nombre": ganador_nombre,
        "justificacion": justificacion,
        "top_3": top_3,
        "detalle": nicho_completo
    }


SYSTEM_PROMPT = """Eres un estratega de contenido experto en YouTube con años de experiencia haciendo crecer canales faceless en inglés.

Tu trabajo es crear un CALENDARIO EDITORIAL DE 30 DÍAS (un vídeo por día) para un canal nuevo en el nicho que te indiquen.

REGLAS ESTRATÉGICAS:
1. **Los primeros 10 vídeos** deben ser temas con ALTO volumen de búsqueda (para captar tráfico orgánico rápido)
2. **Mezcla de formatos**: listicles, how-to, explicaciones, comparativas, historias
3. **Progresión de dificultad**: empieza con temas amplios, ve a específicos
4. **Títulos optimizados para CTR**: usa números, curiosidad, beneficio claro
5. **Cada vídeo debe tener un ángulo único** — no repetir enfoques
6. **Duración sugerida**: entre 8-15 minutos (sweet spot para monetización)
7. **Todos los títulos en INGLÉS** (audiencia US)
8. **Pilar content strategy**: agrupa vídeos en 4-5 pilares temáticos para que el algoritmo entienda el canal

Responde en JSON con esta estructura:
{
  "estrategia_canal": {
    "nombre_canal_sugerido": "string (3 opciones separadas por |)",
    "descripcion_canal": "string",
    "pilares_contenido": [
      {
        "nombre": "string",
        "descripcion": "string",
        "porcentaje_contenido": int
      }
    ],
    "frecuencia_publicacion": "string",
    "mejor_horario_publicacion": "string",
    "tono_y_estilo": "string"
  },
  "calendario": [
    {
      "dia": int,
      "titulo": "string (en inglés, optimizado para CTR)",
      "pilar": "string (a qué pilar pertenece)",
      "formato": "string (listicle|how-to|explicacion|comparativa|historia|caso_estudio)",
      "angulo": "string (qué hace único a este vídeo)",
      "keywords_objetivo": ["string (3-5 keywords SEO)"],
      "duracion_estimada_min": int,
      "hook_inicial": "string (primera frase del vídeo para retención, en inglés)",
      "descripcion_breve": "string (de qué trata el vídeo en 1-2 frases)"
    }
  ]
}"""


def run_content_strategist() -> dict:
    """Ejecuta el Content Strategist y genera el calendario editorial."""
    print("🗓️ [Content Strategist] Cargando nicho ganador...")
    niche_data = load_winning_niche()

    print(f"📌 [Content Strategist] Nicho: {niche_data['nombre']}")

    user_prompt = f"""Crea un calendario editorial de 30 días para un canal de YouTube FACELESS en INGLÉS sobre el siguiente nicho:

NICHO GANADOR: {niche_data['nombre']}
JUSTIFICACIÓN: {niche_data['justificacion']}
DETALLES DE VALIDACIÓN: {json.dumps(niche_data['detalle'], indent=2, ensure_ascii=False) if niche_data['detalle'] else 'No disponible'}

REQUISITOS:
- 30 vídeos (1 por día)
- Todos los títulos en INGLÉS
- Formato 100% faceless
- Optimizados para búsqueda orgánica (SEO)
- Los primeros 10 vídeos deben atacar keywords de ALTO volumen
- Incluye hooks iniciales potentes para cada vídeo (en inglés)
- Agrupa en pilares de contenido coherentes

Genera el calendario completo con los 30 vídeos."""

    result = call_llm_json(
        agent_name="content_strategist",
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.7
    )

    # Guardrail: validar estructura
    calendario = result.get("calendario", [])
    if len(calendario) < 30:
        print(f"⚠️ [Content Strategist] Solo generó {len(calendario)}/30 vídeos.")

    estrategia = result.get("estrategia_canal")
    if not estrategia:
        print("⚠️ [Content Strategist] No incluyó estrategia de canal.")

    # Guardar resultados
    with open(CONTENT_CALENDAR_FILE, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"✅ [Content Strategist] Calendario generado: {len(calendario)} vídeos.")
    print(f"   Guardado en {CONTENT_CALENDAR_FILE}")

    if estrategia:
        print(f"   📺 Nombres sugeridos: {estrategia.get('nombre_canal_sugerido', 'N/A')}")
        pilares = estrategia.get("pilares_contenido", [])
        for p in pilares:
            print(f"   📌 Pilar: {p['nombre']} ({p.get('porcentaje_contenido', '?')}%)")

    return result


if __name__ == "__main__":
    resultado = run_content_strategist()
    print(json.dumps(resultado, indent=2, ensure_ascii=False))