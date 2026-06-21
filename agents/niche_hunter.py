# agents/niche_hunter.py
import logging
from logging_setup import setup_logging
import json
import os
from llm_client import call_llm_json
from config import DATA_DIR
logger = logging.getLogger(__name__)

QUALIFYING_CHANNELS_FILE = os.path.join(DATA_DIR, "qualifying_channels.json")
NICHE_RESULTS_FILE = os.path.join(DATA_DIR, "niche_analysis.json")


def load_channels():
    """Carga los canales qualifying y genera un resumen agrupado por categoría."""
    with open(QUALIFYING_CHANNELS_FILE, "r", encoding="utf-8") as f:
        channels = json.load(f)

    if not channels:
        raise ValueError("❌ No hay canales en qualifying_channels.json. Ejecuta primero el scraper.")

    return channels


def build_channel_summary(channels):
    """Construye un resumen compacto de los canales para el LLM."""
    # Agrupar por keyword/categoría
    summary_lines = []
    for ch in channels:
        summary_lines.append(
            f"- {ch['title']} | Subs: {ch['subscribers']:,} | "
            f"Videos: {ch['videos']} | Views: {ch['views']:,} | "
            f"Creado: {ch['created'][:10]}"
        )

    return f"Total canales analizados: {len(channels)}\n\n" + "\n".join(summary_lines)


SYSTEM_PROMPT = """Eres un experto en análisis de mercado para YouTube. 
Te voy a pasar datos REALES de canales de YouTube que han crecido rápido (20K-400K subs en menos de 12 meses con menos de 150 vídeos).

Tu trabajo es analizar estos canales y detectar los NICHOS más rentables y replicables para un canal FACELESS en INGLÉS producido con IA.

Para cada nicho que identifiques DEBES incluir:
1. **Nombre del nicho**: Claro y específico (no genérico)
2. **Descripción**: 2-3 frases explicando el nicho
3. **Canales de referencia**: Canales reales de los datos que pertenecen a este nicho
4. **Demanda**: alta/media/baja (basado en las views de los canales)
5. **Competencia**: alta/media/baja
6. **CPM estimado USD**: Rango realista
7. **Monetización extra**: Oportunidades más allá de AdSense
8. **Evergreen score**: 1-10
9. **Viabilidad faceless**: Por qué funciona sin mostrar la cara
10. **Viabilidad IA**: Qué herramientas de IA se usarían para producirlo
11. **Puntuación final**: 1-100 considerando todos los factores

CRITERIOS OBLIGATORIOS:
- CPM estimado > $5
- Evergreen score >= 7
- 100% faceless y producible con IA
- Audiencia angloparlante (US principalmente)

Responde en JSON con esta estructura:
{
  "analisis_general": "string (resumen de tendencias observadas en los datos)",
  "nichos": [
    {
      "nombre": "string",
      "descripcion": "string",
      "canales_referencia": ["string"],
      "demanda": "alta|media|baja",
      "competencia": "alta|media|baja",
      "cpm_estimado_usd": "string",
      "monetizacion_extra": ["string"],
      "evergreen_score": int,
      "viabilidad_faceless": "string",
      "viabilidad_ia": "string",
      "puntuacion_final": int,
      "justificacion": "string"
    }
  ]
}

Ordena los nichos de mayor a menor puntuación final. Propón entre 5 y 10 nichos."""


def run_niche_hunter() -> dict:
    """Ejecuta el Niche Hunter: analiza canales reales y propone nichos."""
    logger.info("🔍 [Niche Hunter] Cargando canales qualifying...")
    channels = load_channels()

    logger.info(f"📊 [Niche Hunter] Analizando {len(channels)} canales con LLM...")
    channel_summary = build_channel_summary(channels)

    user_prompt = f"""Analiza los siguientes canales de YouTube que han crecido rápidamente en los últimos 12 meses.
Identifica los nichos más rentables y replicables para un canal faceless en inglés producido con IA.

DATOS REALES DE CANALES:
{channel_summary}

Basándote en estos datos reales, propón los mejores nichos ordenados por puntuación."""

    result = call_llm_json(
        agent_name="niche_hunter",
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.7
    )

    # Guardrail: validar
    nichos = result.get("nichos", [])
    if not nichos:
        raise ValueError("❌ Niche Hunter no devolvió ningún nicho.")

    nichos_validos = [n for n in nichos if n.get("evergreen_score", 0) >= 7]
    if not nichos_validos:
        raise ValueError("❌ Ningún nicho cumple evergreen_score >= 7.")

    # Ordenar por puntuación
    nichos_validos.sort(key=lambda x: x.get("puntuacion_final", 0), reverse=True)
    result["nichos"] = nichos_validos

    # Guardar resultados
    with open(NICHE_RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    logger.info(f"✅ [Niche Hunter] {len(nichos_validos)} nichos identificados. Guardado en {NICHE_RESULTS_FILE}")
    return result


if __name__ == "__main__":
    setup_logging()
    resultado = run_niche_hunter()
    logger.info(json.dumps(resultado, indent=2, ensure_ascii=False))