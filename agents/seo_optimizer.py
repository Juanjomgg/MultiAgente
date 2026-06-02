# agents/seo_optimizer.py
import json
import os
from llm_client import call_llm_json

DATA_DIR = "data"
SEO_DIR = os.path.join(DATA_DIR, "seo")


SYSTEM_PROMPT = """Eres un experto en YouTube SEO con años de experiencia posicionando vídeos en el top de búsquedas.

Tu trabajo es optimizar cada vídeo para MÁXIMA visibilidad orgánica en YouTube.

REGLAS SEO PARA YOUTUBE:
1. **Título** (máx 60 caracteres):
   - Keyword principal al inicio
   - Número si es listicle
   - Genera curiosidad o promete beneficio
   - NO clickbait engañoso — debe cumplir lo que promete
   - Genera 3 variantes para elegir

2. **Descripción** (máx 5000 caracteres):
   - Primera línea: resumen potente con keyword (aparece en preview)
   - Primeras 2-3 líneas son las más importantes (above the fold)
   - Incluye timestamps/capítulos
   - Keywords naturales repartidas (NO keyword stuffing)
   - CTA a suscripción
   - Links a vídeos relacionados (placeholder)
   - 2-3 hashtags relevantes al final

3. **Tags** (máx 500 caracteres total):
   - Keyword principal exacta
   - Variaciones long-tail
   - Keywords relacionadas
   - 15-20 tags ordenados por relevancia
   - Incluye errores comunes de escritura si aplica

4. **Texto para thumbnail**:
   - Máximo 4-5 palabras
   - Alto contraste, legible en móvil
   - Complementa el título (NO lo repite)
   - Genera curiosidad visual

Todo en INGLÉS.

Responde en JSON con esta estructura:
{
  "video_id": "string",
  "titulos": [
    {
      "texto": "string",
      "caracteres": int,
      "keyword_posicion": "string (dónde está la keyword principal)"
    }
  ],
  "titulo_recomendado": "string (el mejor de los 3)",
  "descripcion": "string (descripción completa lista para copiar)",
  "tags": ["string"],
  "tags_caracteres_total": int,
  "texto_thumbnail": "string (4-5 palabras para la miniatura)",
  "hashtags": ["string (3 hashtags)"],
  "keyword_principal": "string",
  "keywords_secundarias": ["string"],
  "notas_seo": ["string (consejos adicionales para este vídeo)"]
}"""


def run_seo_optimizer(video_data: dict, video_id: str) -> dict:
    """Genera la optimización SEO completa para un vídeo."""
    os.makedirs(SEO_DIR, exist_ok=True)

    print(f"🏷️ [SEO Optimizer] Optimizando {video_id}: {video_data.get('titulo', '')}")

    # Cargar guión si existe para contexto extra
    script_file = os.path.join(DATA_DIR, "scripts", f"{video_id}.json")
    script_context = ""
    if os.path.exists(script_file):
        with open(script_file, "r") as f:
            script_data = json.load(f)
        script_context = f"\nRESUMEN DEL GUIÓN: {script_data.get('guion_completo', '')[:500]}..."

    user_prompt = f"""Optimiza el SEO para este vídeo de YouTube:

TÍTULO ORIGINAL: {video_data.get('titulo', '')}
FORMATO: {video_data.get('formato', '')}
KEYWORDS OBJETIVO: {', '.join(video_data.get('keywords_objetivo', []))}
DESCRIPCIÓN DEL VÍDEO: {video_data.get('descripcion_breve', '')}
HOOK: {video_data.get('hook_inicial', '')}
DURACIÓN: {video_data.get('duracion_estimada_min', 10)} minutos
VIDEO ID: {video_id}
{script_context}

Genera la optimización SEO completa: 3 variantes de título, descripción con timestamps, tags y texto para thumbnail."""

    result = call_llm_json(
        agent_name="seo_optimizer",
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.5
    )

    # Guardrails
    titulos = result.get("titulos", [])
    for t in titulos:
        if t.get("caracteres", 0) > 60:
            print(f"⚠️ [SEO] Título demasiado largo ({t['caracteres']} chars): {t['texto']}")

    tags = result.get("tags", [])
    tags_total = sum(len(t) for t in tags)
    if tags_total > 500:
        print(f"⚠️ [SEO] Tags exceden 500 chars ({tags_total}). Recortando...")
        while sum(len(t) for t in tags) > 500:
            tags.pop()
        result["tags"] = tags

    result["video_id"] = video_id
    result["tags_caracteres_total"] = sum(len(t) for t in tags)

    # Guardar
    output_file = os.path.join(SEO_DIR, f"{video_id}.json")
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"✅ [SEO Optimizer] Guardado: {output_file}")
    return result


if __name__ == "__main__":
    test_video = {
        "titulo": "7 Money Habits That Keep You Poor",
        "formato": "listicle",
        "keywords_objetivo": ["money habits", "financial mistakes", "personal finance tips"],
        "duracion_estimada_min": 10,
        "hook_inicial": "You're losing money right now and you don't even know it.",
        "descripcion_breve": "7 everyday money habits that seem harmless but are secretly keeping you broke."
    }
    resultado = run_seo_optimizer(test_video, "video_test")
    print(json.dumps(resultado, indent=2, ensure_ascii=False))