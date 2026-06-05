# agents/quality_controller.py
import json
import os
from llm_client import call_llm_json

DATA_DIR = "data"
QC_DIR = os.path.join(DATA_DIR, "quality_checks")


SYSTEM_PROMPT = """Eres un director creativo senior de YouTube con experiencia en canales que superan el millón de suscriptores. Tu trabajo es revisar y evaluar la calidad de cada vídeo ANTES de producirlo.

Recibirás el guión, SEO y concepto de thumbnail de un vídeo. Debes evaluarlo de forma CRÍTICA y HONESTA.

CRITERIOS DE EVALUACIÓN (puntúa cada uno de 1 a 10):

1. **HOOK (retención 0-30s)**: ¿El hook es lo suficientemente potente para retener en los primeros 30 segundos?
2. **GUIÓN (calidad narrativa)**: ¿El guión es interesante, bien estructurado y mantiene la atención?
3. **SEO (descubribilidad)**: ¿El título, tags y descripción están bien optimizados?
4. **THUMBNAIL (CTR potencial)**: ¿El concepto de thumbnail generará clicks?
5. **COHERENCIA**: ¿Todo encaja entre sí? (título + thumbnail + contenido)
6. **VALOR (para el espectador)**: ¿El vídeo aporta valor real?

VEREDICTO:
- **APROBADO** (puntuación media >= 7): Listo para producción
- **REVISAR** (media 5-6.9): Necesita mejoras específicas
- **RECHAZADO** (media < 5): Rehacer desde cero

Si el veredicto es REVISAR o RECHAZADO, indica EXACTAMENTE qué cambiar y cómo.

Responde en JSON:
{
  "video_id": "string",
  "puntuaciones": {
    "hook": int,
    "guion": int,
    "seo": int,
    "thumbnail": int,
    "coherencia": int,
    "valor": int
  },
  "media": float,
  "veredicto": "APROBADO|REVISAR|RECHAZADO",
  "resumen": "string (evaluación general en 2-3 frases)",
  "puntos_fuertes": ["string"],
  "puntos_debiles": ["string"],
  "cambios_requeridos": [
    {
      "area": "string (hook|guion|seo|thumbnail)",
      "problema": "string",
      "solucion": "string (cambio concreto y específico)"
    }
  ]
}"""


def run_quality_check(video_result: dict) -> dict:
    """Ejecuta el quality check sobre un vídeo procesado."""
    os.makedirs(QC_DIR, exist_ok=True)

    video_id = video_result.get("video_id", "unknown")
    print(f"🔍 [Quality Controller] Revisando {video_id}...")

    results = video_result.get("results", {})
    errors = video_result.get("errors", {})

    # Recopilar datos de cada agente
    script_data = results.get("script", {})
    seo_data = results.get("seo", {})
    thumbnail_data = results.get("thumbnail", {})

    # Construir resumen para el QC
    guion_resumen = ""
    if script_data:
        hook = script_data.get('hook', '')
        if isinstance(hook, dict):
            hook = hook.get('texto', 'N/A')
        guion_resumen = f"""
HOOK: {str(hook)[:300]}
SECCIONES: {len(script_data.get('secciones', []))}
PALABRAS TOTALES: {script_data.get('palabras_totales', 'N/A')}
GUIÓN (primeros 500 chars): {script_data.get('guion_completo', '')[:500]}..."""

    seo_resumen = ""
    if seo_data:
        seo_resumen = f"""
TÍTULO RECOMENDADO: {seo_data.get('titulo_recomendado', 'N/A')}
VARIANTES: {json.dumps(seo_data.get('titulos', []), ensure_ascii=False)}
KEYWORD PRINCIPAL: {seo_data.get('keyword_principal', 'N/A')}
TAGS: {', '.join(seo_data.get('tags', [])[:10])}
TEXTO THUMBNAIL: {seo_data.get('texto_thumbnail', 'N/A')}"""

    thumb_resumen = ""
    if thumbnail_data:
        concepto = thumbnail_data.get("concepto", {})
        thumb_resumen = f"""
CONCEPTO: {concepto.get('descripcion', 'N/A')}
ELEMENTOS: {', '.join(concepto.get('elementos_principales', []))}
COLORES: {concepto.get('esquema_colores', 'N/A')}
TEXTO OVERLAY: {concepto.get('texto_overlay', 'N/A')}
ESTILO: {thumbnail_data.get('estilo', 'N/A')}"""

    errores_info = ""
    if errors:
        errores_info = f"\n⚠️ AGENTES QUE FALLARON: {', '.join(errors.keys())}"

    user_prompt = f"""Evalúa la calidad de este vídeo de YouTube:

VIDEO ID: {video_id}
DATOS ORIGINALES: {json.dumps(video_result.get('video_data', {}), ensure_ascii=False)}

═══ GUIÓN ═══{guion_resumen if guion_resumen else ' NO DISPONIBLE (agente falló)'}

═══ SEO ═══{seo_resumen if seo_resumen else ' NO DISPONIBLE (agente falló)'}

═══ THUMBNAIL ═══{thumb_resumen if thumb_resumen else ' NO DISPONIBLE (agente falló)'}
{errores_info}

Evalúa críticamente. Si algún agente falló, refleja eso en la puntuación de esa área (máximo 3).
Sé específico en los cambios requeridos."""

    result = call_llm_json(
        agent_name="quality_controller",
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.3
    )

    result["video_id"] = video_id

    # Calcular media si no la incluyó
    puntuaciones = result.get("puntuaciones", {})
    if puntuaciones:
        valores = [v for v in puntuaciones.values() if isinstance(v, (int, float))]
        result["media"] = round(sum(valores) / len(valores), 1) if valores else 0

    veredicto = result.get("veredicto", "REVISAR")

    # Mostrar resultado
    print(f"\n   {'─'*35}")
    print(f"   📊 QUALITY CHECK — {video_id}")
    print(f"   {'─'*35}")
    for k, v in puntuaciones.items():
        v = int(v) if isinstance(v, (str, float)) else v
    print(f"   {'─'*35}")
    print(f"   📈 Media: {result.get('media', 'N/A')}")

    emoji = {"APROBADO": "✅", "REVISAR": "⚠️", "RECHAZADO": "❌"}.get(veredicto, "❓")
    print(f"   {emoji} Veredicto: {veredicto}")
    print(f"   💬 {result.get('resumen', '')}")

    cambios = result.get("cambios_requeridos", [])
    if cambios:
        print(f"\n   🔧 Cambios requeridos:")
        for c in cambios:
            print(f"      • [{c.get('area', '?')}] {c.get('problema', '')}")
            print(f"        → {c.get('solucion', '')}")

    # Guardar
    output_file = os.path.join(QC_DIR, f"{video_id}_qc.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n   💾 Guardado: {output_file}")
    return result

# CAMBIA TODO EL BLOQUE if __name__ POR:

if __name__ == "__main__":
    import sys

    VIDEO_OUTPUT_DIR = os.path.join(DATA_DIR, "videos_output")

    video_num = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    video_id = f"video_{video_num:02d}"

    video_file = os.path.join(VIDEO_OUTPUT_DIR, f"{video_id}.json")
    if not os.path.exists(video_file):
        print(f"❌ No existe {video_file}. Ejecuta primero el pipeline para {video_id}.")
        sys.exit(1)

    with open(video_file, "r", encoding="utf-8") as f:
        video_result = json.load(f)

    print(f"🎯 Ejecutando Quality Check para {video_id}")
    resultado = run_quality_check(video_result)
    print(json.dumps(resultado, indent=2, ensure_ascii=False))