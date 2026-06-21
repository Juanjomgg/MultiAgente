# agents/niche_validator.py
import logging
from logging_setup import setup_logging
import json
import os
import time
from pytrends.request import TrendReq
from llm_client import call_llm_json
from config import DATA_DIR
logger = logging.getLogger(__name__)

NICHE_ANALYSIS_FILE = os.path.join(DATA_DIR, "niche_analysis.json")
VALIDATED_NICHES_FILE = os.path.join(DATA_DIR, "validated_niches.json")


def load_niches():
    """Carga los nichos propuestos por el Niche Hunter."""
    with open(NICHE_ANALYSIS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    nichos = data.get("nichos", [])
    if not nichos:
        raise ValueError("❌ No hay nichos en niche_analysis.json.")
    return nichos


def get_trends_data(keywords, timeframe="today 12-m", geo="US"):
    """Consulta Google Trends para una lista de keywords (máx 5 por consulta)."""
    pytrends = TrendReq(hl="en-US", tz=360)
    results = {}

    # Google Trends acepta máximo 5 keywords por consulta
    batches = [keywords[i:i+5] for i in range(0, len(keywords), 5)]

    for batch in batches:
        try:
            pytrends.build_payload(batch, timeframe=timeframe, geo=geo)
            interest = pytrends.interest_over_time()

            if not interest.empty:
                for kw in batch:
                    if kw in interest.columns:
                        values = interest[kw].tolist()
                        results[kw] = {
                            "promedio": round(sum(values) / len(values), 1),
                            "maximo": max(values),
                            "minimo": min(values),
                            "tendencia": "creciente" if values[-1] > values[0] else "decreciente" if values[-1] < values[0] else "estable",
                            "estabilidad": round(1 - (max(values) - min(values)) / max(max(values), 1), 2)
                        }
            time.sleep(2)  # evitar rate limiting
        except Exception as e:
            logger.warning(f"   ⚠️ Error en Google Trends para {batch}: {e}")
            for kw in batch:
                results[kw] = {"error": str(e)}

    return results


def run_niche_validator() -> dict:
    """Valida los nichos con Google Trends + análisis LLM."""
    logger.info("📊 [Niche Validator] Cargando nichos...")
    nichos = load_niches()

    # === FASE 1: Google Trends ===
    logger.info(f"📈 [Niche Validator] Consultando Google Trends para {len(nichos)} nichos...")

    # Extraer keywords de búsqueda de cada nicho
    keywords = [n["nombre"].lower() for n in nichos]
    trends_data = get_trends_data(keywords)

    # Añadir datos de trends a cada nicho
    for nicho in nichos:
        key = nicho["nombre"].lower()
        nicho["google_trends"] = trends_data.get(key, {"error": "no data"})

    logger.info("✅ [Niche Validator] Datos de Google Trends obtenidos.")

    # === FASE 2: Validación con LLM ===
    logger.info("🧠 [Niche Validator] Analizando con LLM...")

    system_prompt = """Eres un analista de datos experto en YouTube y marketing digital.
Te voy a pasar nichos propuestos junto con datos REALES de Google Trends.

Tu trabajo es VALIDAR cada nicho y dar un veredicto final. Para cada nicho evalúa:

1. **Consistencia de datos**: ¿Los datos de Google Trends confirman la demanda?
2. **Estabilidad**: ¿El interés es constante o tiene picos estacionales? (evergreen real)
3. **Tendencia**: ¿Está creciendo, estable o decayendo?
4. **Riesgo**: Factores que podrían hacer que el nicho falle
5. **Veredicto**: APROBADO / APROBADO CON RESERVAS / RECHAZADO
6. **Puntuación ajustada**: 1-100 (ajustada con datos reales)
7. **Recomendación**: Consejo específico si se elige este nicho

Responde en JSON:
{
  "nichos_validados": [
    {
      "nombre": "string",
      "consistencia_datos": "string",
      "estabilidad": "string",
      "tendencia": "creciente|estable|decreciente",
      "riesgos": ["string"],
      "veredicto": "APROBADO|APROBADO CON RESERVAS|RECHAZADO",
      "puntuacion_ajustada": int,
      "recomendacion": "string"
    }
  ],
  "top_3_recomendados": ["string (nombre del nicho)"],
  "nicho_ganador": "string (el mejor nicho)",
  "justificacion_ganador": "string (por qué es el mejor)"
}

Sé crítico. Si los datos de Trends no respaldan un nicho, recházalo sin importar lo bien que suene."""

    user_prompt = f"""Valida los siguientes nichos usando los datos reales de Google Trends adjuntos:

{json.dumps(nichos, indent=2, ensure_ascii=False)}

Analiza críticamente cada uno y dame tu veredicto final con el nicho ganador."""

    result = call_llm_json(
        agent_name="niche_validator",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.3  # baja temperatura para análisis riguroso
    )

    # Guardrail: verificar estructura
    validados = result.get("nichos_validados", [])
    if not validados:
        raise ValueError("❌ Niche Validator no devolvió validaciones.")

    ganador = result.get("nicho_ganador", "No definido")

    # Guardar resultados
    with open(VALIDATED_NICHES_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    logger.info(f"✅ [Niche Validator] Validación completa. Guardado en {VALIDATED_NICHES_FILE}")
    logger.info(f"🏆 Nicho ganador: {ganador}")

    return result


if __name__ == "__main__":
    setup_logging()
    resultado = run_niche_validator()
    logger.info(json.dumps(resultado, indent=2, ensure_ascii=False))