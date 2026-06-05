# agents/script_writer.py
import json
import os
from llm_client import call_llm, call_llm_json

DATA_DIR = "data"
SCRIPTS_DIR = os.path.join(DATA_DIR, "scripts")

SCRIPT_PROMPT = """Eres un guionista experto en YouTube con millones de views acumuladas. Escribes guiones para canales FACELESS en INGLÉS que maximizan retención y engagement.

ESTRUCTURA OBLIGATORIA DEL GUIÓN:

=== HOOK (0:00 - 0:30) ===
- Abre con pregunta impactante, dato sorprendente o afirmación provocadora
- Genera curiosidad inmediata
- Incluye un "pattern interrupt"
- Promete el valor que obtendrá si se queda

=== INTRO (0:30 - 1:00) ===
- Contexto rápido, establece credibilidad

=== CUERPO (1:00 - fin-2:00) ===
- Divide en secciones claras con transiciones
- Cada 2-3 minutos incluye un "retention bump"
- Usa storytelling, lenguaje conversacional
- Frases cortas y directas

=== CTA + CIERRE (últimos 2 min) ===
- Resumen del valor, call to action natural, teaser

REGLAS:
- Todo en INGLÉS
- Tono conversacional, energético, claro
- Incluye indicaciones: [B-ROLL: descripción], [TEXTO EN PANTALLA: texto], [TRANSICIÓN], [PAUSA]
- Separa cada sección con === NOMBRE DE SECCIÓN ===
- NO uses JSON. Escribe el guión como texto plano, listo para locutar."""

METADATA_PROMPT = """Analiza el siguiente guión y devuelve SOLO este JSON (sin texto extra):
{
  "duracion_estimada_min": int,
  "palabras_totales": int,
  "tecnica_hook": "string (qué técnica de hook se usó)",
  "num_secciones": int,
  "retention_bumps": ["string (lista de retention bumps usados)"],
  "notas_produccion": ["string (3-5 notas clave para el editor)"]
}"""


def parse_script_sections(raw_script: str) -> dict:
    """Parsea el guión en texto plano a secciones estructuradas."""
    sections = {"hook": "", "intro": "", "secciones": [], "cta_cierre": ""}
    
    current_section = None
    current_text = []
    section_count = 0
    
    for line in raw_script.split("\n"):
        line_upper = line.strip().upper()
        
        if "HOOK" in line_upper and "===" in line:
            if current_section and current_text:
                _save_section(sections, current_section, current_text, section_count)
            current_section = "hook"
            current_text = []
        elif "INTRO" in line_upper and "===" in line:
            if current_section and current_text:
                _save_section(sections, current_section, current_text, section_count)
            current_section = "intro"
            current_text = []
        elif ("CTA" in line_upper or "CIERRE" in line_upper or "CLOSING" in line_upper or "OUTRO" in line_upper) and "===" in line:
            if current_section and current_text:
                _save_section(sections, current_section, current_text, section_count)
            current_section = "cta_cierre"
            current_text = []
        elif "===" in line and len(line.strip()) > 6:
            if current_section and current_text:
                _save_section(sections, current_section, current_text, section_count)
            section_count += 1
            current_section = f"seccion_{section_count}"
            current_text = [line.strip().replace("=", "").strip()]
        else:
            if current_section:
                current_text.append(line)
    
    # Guardar última sección
    if current_section and current_text:
        _save_section(sections, current_section, current_text, section_count)
    
    return sections


def _save_section(sections, section_name, text_lines, count):
    """Guarda una sección parseada."""
    text = "\n".join(text_lines).strip()
    if section_name == "hook":
        sections["hook"] = text
    elif section_name == "intro":
        sections["intro"] = text
    elif section_name == "cta_cierre":
        sections["cta_cierre"] = text
    elif section_name.startswith("seccion_"):
        title = text_lines[0].strip() if text_lines else f"Sección {count}"
        body = "\n".join(text_lines[1:]).strip() if len(text_lines) > 1 else text
        sections["secciones"].append({
            "numero": count,
            "titulo_seccion": title,
            "texto": body
        })


def run_script_writer(video_data: dict, video_id: str) -> dict:
    """Genera el guión completo para un vídeo en 2 fases."""
    os.makedirs(SCRIPTS_DIR, exist_ok=True)

    titulo = video_data.get('titulo', 'Sin título')
    duracion = video_data.get('duracion_estimada_min', 10)
    print(f"✍️ [Script Writer] Generando guión para {video_id}: {titulo}")

    # === FASE 1: Guión en texto plano ===
    user_prompt = f"""Escribe el guión completo para este vídeo de YouTube:

TÍTULO: {titulo}
FORMATO: {video_data.get('formato', 'explicacion')}
ÁNGULO: {video_data.get('angulo', '')}
KEYWORDS OBJETIVO: {', '.join(video_data.get('keywords_objetivo', []))}
DURACIÓN OBJETIVO: {duracion} minutos ({duracion * 150} palabras aprox.)
HOOK SUGERIDO: {video_data.get('hook_inicial', '')}
DESCRIPCIÓN: {video_data.get('descripcion_breve', '')}

Escribe el guión COMPLETO, palabra por palabra, listo para ser narrado.
Canal FACELESS en INGLÉS. Incluye [B-ROLL], [TEXTO EN PANTALLA], [PAUSA], [TRANSICIÓN]."""

    print(f"   📝 Fase 1: Generando guión en texto plano...")
    raw_script = call_llm(
        agent_name="script_writer",
        system_prompt=SCRIPT_PROMPT,
        user_prompt=user_prompt,
        temperature=0.8
    )

    # === FASE 2: Metadata en JSON (llamada ligera) ===
    print(f"   📊 Fase 2: Extrayendo metadata...")
    try:
        metadata = call_llm_json(
            agent_name="seo_optimizer",  # modelo más barato para metadata
            system_prompt=METADATA_PROMPT,
            user_prompt=f"Guión a analizar:\n\n{raw_script[:3000]}",  # solo inicio para ahorrar tokens
            temperature=0.3
        )
    except Exception as e:
        print(f"   ⚠️ Metadata falló, usando valores por defecto: {e}")
        metadata = {
            "duracion_estimada_min": duracion,
            "tecnica_hook": "desconocida",
            "num_secciones": 0,
            "retention_bumps": [],
            "notas_produccion": []
        }

    # === Estructurar resultado ===
    sections = parse_script_sections(raw_script)
    palabras = len(raw_script.split())

    result = {
        "video_id": video_id,
        "titulo": titulo,
        "duracion_estimada_min": metadata.get("duracion_estimada_min", duracion),
        "palabras_totales": palabras,
        "tecnica_hook": metadata.get("tecnica_hook", ""),
        "hook": sections.get("hook", ""),
        "intro": sections.get("intro", ""),
        "secciones": sections.get("secciones", []),
        "cta_cierre": sections.get("cta_cierre", ""),
        "guion_completo": raw_script,
        "retention_bumps": metadata.get("retention_bumps", []),
        "notas_produccion": metadata.get("notas_produccion", [])
    }

    min_palabras = duracion * 100
    if palabras < min_palabras:
        print(f"   ⚠️ Guión corto: {palabras} palabras (mínimo: {min_palabras})")

    # Guardar
    output_file = os.path.join(SCRIPTS_DIR, f"{video_id}.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"   ✅ [Script Writer] Guión guardado: {output_file} ({palabras} palabras)")
    return result


if __name__ == "__main__":
    import sys
    
    video_num = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    
    with open(CONTENT_CALENDAR_FILE, "r", encoding="utf-8") as f:
        calendario = json.load(f)
    
    CONTENT_CALENDAR_FILE = os.path.join(DATA_DIR, "content_calendar.json")
    videos = calendario.get("calendario", [])
    if video_num < 1 or video_num > len(videos):
        print(f"❌ Vídeo {video_num} no existe. Rango: 1-{len(videos)}")
        sys.exit(1)
    
    video_data = videos[video_num - 1]
    video_id = f"video_{video_num:02d}"
    resultado = run_script_writer(video_data, video_id)