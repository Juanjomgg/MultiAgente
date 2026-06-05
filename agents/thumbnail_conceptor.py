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


# CAMBIA la parte que genera la imagen con Ideogram.
# En vez de usar /v1/images/generations, usa /v1/chat/completions con modalities

def generate_thumbnail_image(prompt: str, video_id: str) -> str:
    """Genera la imagen del thumbnail usando Ideogram via Abacus API."""
    import base64
    
    headers = {
        "Authorization": f"Bearer {ABACUS_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "ideogram",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "modalities": ["image"],
        "image_config": {
            "num_images": 1,
            "aspect_ratio": "16x9"  # YouTube thumbnail ratio
        }
    }

    try:
        response = requests.post(
            "https://routellm.abacus.ai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=180
        )
        response.raise_for_status()
        data = response.json()

        message = data["choices"][0]["message"]
        images = message.get("images", [])

        if images:
            img_data = images[0]
            img_url = None
            img_b64 = None

            if isinstance(img_data, dict):
                url_info = img_data.get("image_url", {})
                url_str = url_info.get("url", "")
                if url_str.startswith("data:image"):
                    # Base64 inline
                    img_b64 = url_str.split(",", 1)[1]
                elif url_str.startswith("http"):
                    img_url = url_str
            elif isinstance(img_data, str):
                if img_data.startswith("http"):
                    img_url = img_data
                else:
                    img_b64 = img_data

            img_path = os.path.join(THUMBNAILS_DIR, f"{video_id}_thumbnail.png")

            if img_b64:
                with open(img_path, "wb") as f:
                    f.write(base64.b64decode(img_b64))
                print(f"   🖼️ Imagen guardada (base64): {img_path}")
                return img_path
            elif img_url:
                img_response = requests.get(img_url, timeout=60)
                with open(img_path, "wb") as f:
                    f.write(img_response.content)
                print(f"   🖼️ Imagen guardada (url): {img_path}")
                return img_path

        print(f"   ⚠️ No se encontró imagen en la respuesta")
        print(f"   Debug: {json.dumps(message, indent=2)[:300]}")
        return None

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
        with open(seo_file, "r", encoding="utf-8") as f:
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
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"✅ [Thumbnail] Concepto guardado: {output_file}")
    return result


if __name__ == "__main__":
    import sys

    CONTENT_CALENDAR_FILE = os.path.join(DATA_DIR, "content_calendar.json")

    video_num = int(sys.argv[1]) if len(sys.argv) > 1 else 1

    with open(CONTENT_CALENDAR_FILE, "r", encoding="utf-8") as f:
        calendario = json.load(f)

    videos = calendario.get("calendario", [])
    if video_num < 1 or video_num > len(videos):
        print(f"❌ Vídeo {video_num} no existe. Rango: 1-{len(videos)}")
        sys.exit(1)

    video_data = videos[video_num - 1]
    video_id = f"video_{video_num:02d}"

    print(f"🎯 Ejecutando Thumbnail Conceptor para {video_id}: {video_data.get('titulo', '')}")
    resultado = run_thumbnail_conceptor(video_data, video_id)
    print(json.dumps(resultado, indent=2, ensure_ascii=False))