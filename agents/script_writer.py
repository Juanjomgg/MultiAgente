# agents/script_writer.py
import json
import os
from llm_client import call_llm_json

DATA_DIR = "data"
SCRIPTS_DIR = os.path.join(DATA_DIR, "scripts")


SYSTEM_PROMPT = """Eres un guionista experto en YouTube con millones de views acumuladas. Escribes guiones para canales FACELESS en INGLÉS que maximizan retención y engagement.

ESTRUCTURA OBLIGATORIA DEL GUIÓN:

1. **HOOK (0:00 - 0:30)**: Los primeros 30 segundos son CRÍTICOS.
   - Abre con una pregunta impactante, dato sorprendente o afirmación provocadora
   - Genera curiosidad inmediata — el espectador DEBE querer saber más
   - Incluye un "pattern interrupt" (algo inesperado)
   - Promete el valor que obtendrá si se queda

2. **INTRO (0:30 - 1:00)**: Contexto rápido
   - Establece credibilidad del tema
   - Anticipa lo que viene sin revelarlo todo

3. **CUERPO (1:00 - fin-2:00)**: Contenido principal
   - Divide en secciones claras con transiciones
   - Cada 2-3 minutos incluye un "retention bump" (dato curioso, pregunta retórica, cliffhanger interno)
   - Usa storytelling cuando sea posible
   - Lenguaje conversacional, como si hablaras con un amigo
   - Frases cortas y directas — NO texto académico

4. **CTA + CIERRE (últimos 2 min)**:
   - Resumen del valor entregado
   - Call to action natural (suscripción, like, comentario)
   - Teaser del próximo vídeo o pregunta abierta

REGLAS DE ESCRITURA:
- Todo en INGLÉS
- Tono: conversacional, energético, claro
- Frases de máximo 15 palabras cuando sea posible
- Incluye indicaciones de [B-ROLL], [TEXTO EN PANTALLA], [TRANSICIÓN] para el editor
- Incluye [PAUSA] donde el narrador debe hacer pausa dramática
- NO uses jerga técnica sin explicarla
- Cada sección debe tener un mini-hook que enganche para la siguiente

Responde en JSON con esta estructura:
{
  "video_id": "string",
  "titulo": "string",
  "duracion_estimada_min": int,
  "palabras_totales": int,
  "hook": {
    "texto": "string (el guión del hook palabra por palabra)",
    "tecnica_usada": "string (qué técnica de hook se usó)"
  },
  "intro": {
    "texto": "string"
  },
  "secciones": [
    {
      "numero": int,
      "titulo_seccion": "string",
      "texto": "string (guión completo de la sección)",
      "retention_bump": "string (el elemento de retención incluido)",
      "notas_visuales": "string (qué debe verse en pantalla)"
    }
  ],
  "cta_cierre": {
    "texto": "string"
  },
  "guion_completo": "string (todo el guión unido, listo para locutar)",
  "notas_produccion": ["string (notas para el editor/productor)"]
}"""


def run_script_writer(video_data: dict, video_id: str) -> dict:
    """Genera el guión completo para un vídeo."""
    os.makedirs(SCRIPTS_DIR, exist_ok=True)

    print(f"✍️ [Script Writer] Generando guión para {video_id}: {video_data.get('titulo', 'Sin título')}")

    user_prompt = f"""Escribe el guión completo para este vídeo de YouTube:

TÍTULO: {video_data.get('titulo', '')}
FORMATO: {video_data.get('formato', 'explicacion')}
ÁNGULO: {video_data.get('angulo', '')}
KEYWORDS OBJETIVO: {', '.join(video_data.get('keywords_objetivo', []))}
DURACIÓN OBJETIVO: {video_data.get('duracion_estimada_min', 10)} minutos
HOOK SUGERIDO: {video_data.get('hook_inicial', '')}
DESCRIPCIÓN: {video_data.get('descripcion_breve', '')}
VIDEO ID: {video_id}

Escribe un guión completo, palabra por palabra, listo para ser narrado por una voz IA.
El guión debe durar aproximadamente {video_data.get('duracion_estimada_min', 10)} minutos 
(aprox. {video_data.get('duracion_estimada_min', 10) * 150} palabras).

Recuerda: canal FACELESS en INGLÉS. Incluye todas las indicaciones visuales [B-ROLL], [TEXTO EN PANTALLA], etc."""

    result = call_llm_json(
        agent_name="script_writer",
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.8
    )

    # Guardrail: validar que el guión tiene contenido suficiente
    guion = result.get("guion_completo", "")
    palabras = len(guion.split())

    min_palabras = video_data.get("duracion_estimada_min", 10) * 100  # mínimo 100 palabras/min
    if palabras < min_palabras:
        print(f"⚠️ [Script Writer] Guión corto: {palabras} palabras (mínimo esperado: {min_palabras})")

    result["palabras_totales"] = palabras
    result["video_id"] = video_id

    # Guardar
    output_file = os.path.join(SCRIPTS_DIR, f"{video_id}.json")
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"✅ [Script Writer] Guión guardado: {output_file} ({palabras} palabras)")
    return result


if __name__ == "__main__":
    # Test con datos de ejemplo
    test_video = {
        "titulo": "7 Money Habits That Keep You Poor",
        "formato": "listicle",
        "angulo": "Hábitos financieros comunes que parecen inofensivos pero destruyen tu riqueza",
        "keywords_objetivo": ["money habits", "financial mistakes", "personal finance tips"],
        "duracion_estimada_min": 1,
        "hook_inicial": "You're losing money right now and you don't even know it.",
        "descripcion_breve": "7 everyday money habits that seem harmless but are secretly keeping you broke."
    }
    
    resultado = run_script_writer(test_video, "video_test")
    print(json.dumps(resultado, indent=2, ensure_ascii=False))