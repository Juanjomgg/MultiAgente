# agents/thumbnail_conceptor.py
import json
import os
import requests
from config import ABACUS_API_KEY
from llm_client import call_llm_json

DATA_DIR = "data"
THUMBNAILS_DIR = os.path.join(DATA_DIR, "thumbnails")


SYSTEM_PROMPT = """Eres un diseñador experto en thumbnails de YouTube que generan CTR alto (>8%).

Tu trabajo es crear el CONCEPTO VISUAL y un PROMPT de generación de imagen para cada thumbnail.

REGLAS DE THUMBNAILS CON ALTO CTR:
1. **Simplicidad**: Máximo 3 elementos visuales. Menos es más.
2. **Contraste**: Colores vibrantes que destaquen en móvil (pantalla pequeña)
3. **Texto**: Máximo 4-5 palabras, GRANDES, legibles en miniatura
4. **Emoción**: Debe provocar curiosidad, sorpresa o urgencia
5. **NO repetir el título**: El texto del thumbnail COMPLEMENTA el título
6. **Composición**: Regla de tercios, elemento principal a la izquierda o centro
7. **Faceless**: NO incluir caras humanas reales. Usar iconos, objetos, gráficos, símbolos
8. **Colores ganadores**: Amarillo/negro, rojo/blanco, azul/naranja (alto contraste)

ESTILOS QUE FUNCIONAN PARA FACELESS:
- Fondo de color sólido + objeto/icono central + texto grande
- Split screen (antes/después, vs, comparativa)
- Números grandes + elemento visual
- Flechas/indicadores que guían la mirada
- Gráficos/charts simplificados

Responde en JSON con esta estructura:
{
  "video_id": "string",
  "concepto": {
    "descripcion": "string (descripción del concepto visual)",
    "elementos_principales": ["string (máx 3 elementos)"],
    "esquema_colores": "string (colores principales)",
    "texto_overlay": "string (texto que aparece en la thumbnail, máx 5 palabras)",
    "composicion": "string (cómo se distribuyen los elementos)"
  },
  "prompt_imagen": "string (prompt detallado para generar la imagen con IA, en inglés)",
  "estilo": "string (flat design|3d render|minimalist|bold graphic|infographic)",
  "notas": ["string (consejos para maximizar CTR)"]
}"""


def generate_thumbnail_image(prompt: str, video_id: str) -> str:
    """Genera la imagen del thumbnail usando Ideogram 3.0 via Abacus API."""
    headers = {
        "Authorization": f"Bearer {ABACUS_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "ideogram",
        "prompt": prompt,
        "n": 1,
        "size": "1792x1024",  # ratio 16:9 para YouTube
    }

    try:
        response = requests.post(
            "https://routellm.abacus.ai/v1/images/generations",
            headers=headers,
            json=payload,
            timeout=120
        )
        response.raise_for_status()
        data = response.json()

        image_url = data["data"][0].get("url") or data["data"][0].get("b64_json")

        if image_url and image_url.startswith("http"):
            # Descargar imagen
            img_response = requests.get(image_url, timeout=60)
            img_path = os.path.join(THUMBNAILS_DIR, f"{video_id}_thumbnail.png")
            with open(img_path, "wb") as f:
                f.write(img_response.content)
            print(f"   🖼️ Imagen guardada: {img_path}")
            return img_path
        else:
            print("   ⚠️ Imagen generada en base64, guardando...")
            import base64
            img_path = os.path.join(THUMBNAILS_DIR, f"{video_id}_thumbnail.png")
            with open(img_path, "wb") as f:
                f.write(base64.b64decode(image_url))
            print(f"   🖼️ Imagen guardada: {img_path}")
            return img_path

    except Exception as e:
        print(f"   ❌ Error generando imagen: {e}")
        return None


def run_thumbnail_conceptor(video_data: dict, video_id: str) -> dict:
    """Genera concepto + imagen del thumbnail."""
    os.makedirs(THUMBNAILS_DIR, exist_ok=True)

    print(f"🎨 [Thumbnail] Diseñando thumbnail para {video_id}: {video_data.get('titulo', '')}")

    # Cargar texto de thumbnail del SEO si existe
    seo_file = os.path.join(DATA_DIR, "seo", f"{video_id}.json")
    texto_seo = ""
    if os.path.exists(seo_file):
        with open(seo_file, "r") as f:
            seo_data = json.load(f)
        texto_seo = seo_data.get("texto_thumbnail", "")

    user_prompt = f"""Diseña el thumbnail para este vídeo de YouTube:

TÍTULO: {video_data.get('titulo', '')}
FORMATO: {video_data.get('formato', '')}
DESCRIPCIÓN: {video_data.get('descripcion_breve', '')}
KEYWORDS: {', '.join(video_data.get('keywords_objetivo', []))}
TEXTO SUGERIDO POR SEO: {texto_seo if texto_seo else 'No disponible'}
VIDEO ID: {video_id}

Recuerda: canal FACELESS, NO caras humanas. El thumbnail debe ser impactante en móvil.
Genera un prompt de imagen MUY detallado y específico para Ideogram 3.0, optimizado para texto legible en la imagen."""

    result = call_llm_json(
        agent_name="thumbnail_conceptor",
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.7
    )

    result["video_id"] = video_id

    # Generar imagen
    prompt = result.get("prompt_imagen", "")
    if prompt:
        print(f"   🖌️ Generando imagen con Ideogram 3.0...")
        img_path = generate_thumbnail_image(prompt, video_id)
        result["imagen_path"] = img_path
    else:
        print("   ⚠️ No se generó prompt de imagen.")
        result["imagen_path"] = None

    # Guardar concepto
    output_file = os.path.join(THUMBNAILS_DIR, f"{video_id}_concept.json")
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"✅ [Thumbnail] Concepto guardado: {output_file}")
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
    resultado = run_thumbnail_conceptor(test_video, "video_test")
    print(json.dumps(resultado, indent=2, ensure_ascii=False))