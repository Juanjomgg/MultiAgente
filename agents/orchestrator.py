# orchestrator.py
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

DATA_DIR = "data"
CONTENT_CALENDAR_FILE = os.path.join(DATA_DIR, "content_calendar.json")
PIPELINE_STATUS_FILE = os.path.join(DATA_DIR, "pipeline_status.json")


def load_pipeline_status():
    """Carga o inicializa el estado del pipeline."""
    if os.path.exists(PIPELINE_STATUS_FILE):
        with open(PIPELINE_STATUS_FILE, "r") as f:
            return json.load(f)
    return {"fase": "inicio", "videos_completados": [], "videos_pendientes": []}


def save_pipeline_status(status):
    with open(PIPELINE_STATUS_FILE, "w") as f:
        json.dump(status, f, indent=2, ensure_ascii=False)


def run_phase_1():
    """Fase 1: Descubrimiento de nicho (secuencial)."""
    from agents.niche_hunter_scraper import run_scraper
    from agents.niche_hunter import run_niche_hunter
    from agents.niche_validator import run_niche_validator

    print("\n{'='*60}")
    print("🚀 FASE 1: DESCUBRIMIENTO DE NICHO")
    print(f"{'='*60}\n")

    # Paso 1: Scraper
    print("── Paso 1/3: Scraping YouTube ──")
    qualifying = run_scraper()
    if not qualifying:
        print("⚠️ No hay canales qualifying aún. Ejecuta de nuevo mañana.")
        return None

    # Paso 2: Análisis de nichos
    print("\n── Paso 2/3: Análisis de nichos ──")
    nichos = run_niche_hunter()

    # Paso 3: Validación
    print("\n── Paso 3/3: Validación de nichos ──")
    validacion = run_niche_validator()

    ganador = validacion.get("nicho_ganador", "No definido")
    print(f"\n🏆 NICHO GANADOR: {ganador}")

    return validacion


def run_phase_2():
    """Fase 2: Estrategia de contenido (secuencial)."""
    from agents.content_strategist import run_content_strategist

    print(f"\n{'='*60}")
    print("📋 FASE 2: ESTRATEGIA DE CONTENIDO")
    print(f"{'='*60}\n")

    calendario = run_content_strategist()
    videos = calendario.get("calendario", [])
    print(f"\n📅 Calendario generado: {len(videos)} vídeos")

    return calendario


def process_single_video(video_data, video_index):
    """Procesa un vídeo: script + SEO + thumbnail en PARALELO."""
    from agents.script_writer import run_script_writer
    from agents.seo_optimizer import run_seo_optimizer
    from agents.thumbnail_conceptor import run_thumbnail_conceptor

    video_id = f"video_{video_index:02d}"
    print(f"\n🎬 Procesando {video_id}: {video_data['titulo']}")

    results = {}
    errors = {}

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(run_script_writer, video_data, video_id): "script",
            executor.submit(run_seo_optimizer, video_data, video_id): "seo",
            executor.submit(run_thumbnail_conceptor, video_data, video_id): "thumbnail",
        }

        for future in as_completed(futures):
            agent_name = futures[future]
            try:
                results[agent_name] = future.result()
                print(f"   ✅ {agent_name} completado para {video_id}")
            except Exception as e:
                errors[agent_name] = str(e)
                print(f"   ❌ {agent_name} falló para {video_id}: {e}")

    return {
        "video_id": video_id,
        "video_data": video_data,
        "results": results,
        "errors": errors,
        "status": "completado" if not errors else "parcial"
    }


def run_phase_3():
    """Fase 3: Producción de vídeos (paralelo por vídeo, secuencial entre vídeos)."""
    from agents.quality_controller import run_quality_check

    print(f"\n{'='*60}")
    print("🎬 FASE 3: PRODUCCIÓN DE VÍDEOS")
    print(f"{'='*60}\n")

    # Cargar calendario
    with open(CONTENT_CALENDAR_FILE, "r") as f:
        calendario = json.load(f)

    videos = calendario.get("calendario", [])
    status = load_pipeline_status()
    completados = set(status.get("videos_completados", []))

    for i, video in enumerate(videos, 1):
        video_id = f"video_{i:02d}"

        # Skip si ya está completado
        if video_id in completados:
            print(f"⏭️ {video_id} ya procesado, saltando...")
            continue

        # Procesar vídeo (script + SEO + thumbnail en paralelo)
        resultado = process_single_video(video, i)

        # Quality check
        if resultado["status"] == "completado":
            print(f"\n🔍 Quality check para {video_id}...")
            qc_result = run_quality_check(resultado)
            resultado["quality_check"] = qc_result

        # Guardar resultado individual
        video_output_dir = os.path.join(DATA_DIR, "videos_output")
        os.makedirs(video_output_dir, exist_ok=True)
        with open(os.path.join(video_output_dir, f"{video_id}.json"), "w") as f:
            json.dump(resultado, f, indent=2, ensure_ascii=False)

        # Actualizar estado
        completados.add(video_id)
        status["videos_completados"] = list(completados)
        save_pipeline_status(status)

        # === CHECKPOINT HUMANO ===
        print(f"\n{'─'*40}")
        print(f"📋 {video_id} LISTO PARA REVISIÓN")
        print(f"   📄 Output: data/videos_output/{video_id}.json")
        print(f"   Videos restantes: {len(videos) - i}")
        print(f"{'─'*40}")

        respuesta = input("\n¿Continuar con el siguiente vídeo? (s/n/salir): ").strip().lower()
        if respuesta == "salir":
            print("👋 Pipeline pausado. Puedes retomar ejecutando de nuevo.")
            return
        elif respuesta == "n":
            print(f"🔄 Puedes revisar y re-ejecutar {video_id} manualmente.")
            completados.discard(video_id)
            status["videos_completados"] = list(completados)
            save_pipeline_status(status)
            continue

    print(f"\n🎉 ¡Todos los vídeos procesados!")


def main():
    """Pipeline principal."""
    print(f"\n{'='*60}")
    print("🏭 YOUTUBE CHANNEL FACTORY — PIPELINE")
    print(f"{'='*60}")

    status = load_pipeline_status()
    print(f"\n📊 Estado actual: {status['fase']}")
    print(f"   Videos completados: {len(status.get('videos_completados', []))}")

    print("\n¿Qué fase ejecutar?")
    print("  1 → Fase 1: Descubrimiento de nicho (scraper + análisis + validación)")
    print("  2 → Fase 2: Estrategia de contenido (calendario 30 días)")
    print("  3 → Fase 3: Producción de vídeos (scripts + SEO + thumbnails)")
    print("  full → Ejecutar todo desde el principio")

    opcion = input("\nOpción: ").strip().lower()

    if opcion == "1" or opcion == "full":
        result = run_phase_1()
        if result is None and opcion != "full":
            return
        status["fase"] = "nicho_validado"
        save_pipeline_status(status)

    if opcion == "2" or opcion == "full":
        run_phase_2()
        status["fase"] = "calendario_generado"
        save_pipeline_status(status)

    if opcion == "3" or opcion == "full":
        status["fase"] = "produccion"
        save_pipeline_status(status)
        run_phase_3()


if __name__ == "__main__":
    main()