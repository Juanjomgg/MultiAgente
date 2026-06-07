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
        with open(PIPELINE_STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"fase": "inicio", "videos_completados": [], "videos_pendientes": []}


def save_pipeline_status(status):
    with open(PIPELINE_STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2, ensure_ascii=False)


def run_phase_1():
    """Fase 1: Descubrimiento de nicho (secuencial)."""
    from agents.niche_hunter_scraper import run_scraper
    from agents.niche_hunter import run_niche_hunter
    from agents.niche_validator import run_niche_validator

    print(f"\n{'='*60}")
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
    """Procesa un vídeo: script → [seo + thumbnail en paralelo] → quality_controller."""
    from agents.script_writer import run_script_writer
    from agents.seo_optimizer import run_seo_optimizer
    from agents.thumbnail_conceptor import run_thumbnail_conceptor

    video_id = f"video_{video_index:02d}"
    print(f"\n🎬 Procesando {video_id}: {video_data['titulo']}")

    results = {}
    errors = {}

    script_file = os.path.join(DATA_DIR, "scripts", f"{video_id}.json")
    seo_file    = os.path.join(DATA_DIR, "seo", f"{video_id}.json")
    thumb_file  = os.path.join(DATA_DIR, "thumbnails", f"{video_id}_concept.json")

    # ── STEP 1: Script (must finish before SEO/Thumbnail) ──────────────────
    if os.path.exists(script_file):
        print(f"   ⏭️ Script already exists, skipping...")
        with open(script_file, "r", encoding="utf-8") as f:
            results["script"] = json.load(f)
    else:
        try:
            results["script"] = run_script_writer(video_data, video_id)
            print(f"   ✅ script done")
        except Exception as e:
            errors["script"] = str(e)
            print(f"   ❌ script failed: {e}")

    # ── STEP 2: SEO + Thumbnail in parallel (both benefit from script) ──────
    tasks = {}

    if os.path.exists(seo_file):
        print(f"   ⏭️ SEO already exists, skipping...")
        with open(seo_file, "r", encoding="utf-8") as f:
            results["seo"] = json.load(f)
    else:
        tasks["seo"] = (run_seo_optimizer, video_data, video_id)

    if os.path.exists(thumb_file):
        print(f"   ⏭️ Thumbnail already exists, skipping...")
        with open(thumb_file, "r", encoding="utf-8") as f:
            results["thumbnail"] = json.load(f)
    else:
        tasks["thumbnail"] = (run_thumbnail_conceptor, video_data, video_id)

    if tasks:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                executor.submit(func, vdata, vid): name
                for name, (func, vdata, vid) in tasks.items()
            }
            for future in as_completed(futures):
                agent_name = futures[future]
                try:
                    results[agent_name] = future.result()
                    print(f"   ✅ {agent_name} done")
                except Exception as e:
                    errors[agent_name] = str(e)
                    print(f"   ❌ {agent_name} failed: {e}")

    return {
        "video_id": video_id,
        "video_data": video_data,
        "results": results,
        "errors": errors,
        "status": "completado" if not errors else "parcial"
    }


def run_phase_3():
    """Fase 3: Producción de vídeos con loop de auto-mejora."""
    from agents.quality_controller import run_quality_check
    from agents.script_writer import run_script_writer
    from agents.seo_optimizer import run_seo_optimizer
    from agents.thumbnail_conceptor import run_thumbnail_conceptor

    MAX_MEJORAS = 2  # Máximo 2 rondas de mejora por vídeo

    print(f"\n{'='*60}")
    print("🎬 FASE 3: PRODUCCIÓN DE VÍDEOS")
    print(f"{'='*60}\n")

    # Cargar calendario
    with open(CONTENT_CALENDAR_FILE, "r", encoding="utf-8") as f:
        calendario = json.load(f)

    videos = calendario.get("calendario", [])
    status = load_pipeline_status()
    completados = set(status.get("videos_completados", []))

    for i, video in enumerate(videos, 1):
        video_id = f"video_{i:02d}"

        if video_id in completados:
            print(f"⏭️ {video_id} ya procesado, saltando...")
            continue

        # === GENERACIÓN INICIAL ===
        resultado = process_single_video(video, i)

        if resultado["status"] != "completado":
            print(f"   ⚠️ {video_id} tiene errores, saltando QC")
            continue

        # === LOOP DE MEJORA ===
        for ronda in range(MAX_MEJORAS + 1):  # 0=QC inicial, 1-2=mejoras
            print(f"\n🔍 Quality check para {video_id} (ronda {ronda})...")
            qc_result = run_quality_check(resultado)
            resultado["quality_check"] = qc_result

            veredicto = qc_result.get("veredicto", "REVISAR")

            if veredicto == "APROBADO":
                print(f"\n   🎉 {video_id} APROBADO en ronda {ronda}!")
                break

            if ronda >= MAX_MEJORAS:
                print(f"\n   ⚠️ {video_id} NO aprobado tras {MAX_MEJORAS} mejoras. Requiere revisión humana.")
                break

            # === APLICAR MEJORAS ===
            cambios = qc_result.get("cambios_requeridos", [])
            if not cambios:
                print(f"   ⚠️ Veredicto {veredicto} pero sin cambios específicos. Parando.")
                break

            # Agrupar feedback por área
            feedback_por_area = {}
            for cambio in cambios:
                area = cambio.get("area", "")
                if area not in feedback_por_area:
                    feedback_por_area[area] = []
                feedback_por_area[area].append(cambio)

            print(f"\n   🔧 Ronda {ronda + 1}: Mejorando {', '.join(feedback_por_area.keys())}...")

            # Mapeo área → agente
            area_to_agent = {
                "guion": ("script", run_script_writer),
                "hook": ("script", run_script_writer),  # hook es parte del guión
                "seo": ("seo", run_seo_optimizer),
                "thumbnail": ("thumbnail", run_thumbnail_conceptor),
            }

            # Eliminar outputs anteriores de las áreas a mejorar
            files_to_delete = {
                "script": os.path.join(DATA_DIR, "scripts", f"{video_id}.json"),
                "seo": os.path.join(DATA_DIR, "seo", f"{video_id}.json"),
                "thumbnail": os.path.join(DATA_DIR, "thumbnails", f"{video_id}_concept.json"),
            }

            agents_to_rerun = {}  # {agent_key: feedback_list}
            for area, fb_list in feedback_por_area.items():
                mapped = area_to_agent.get(area)
                if mapped:
                    agent_key, agent_func = mapped
                    if agent_key not in agents_to_rerun:
                        agents_to_rerun[agent_key] = {"func": agent_func, "feedback": []}
                    agents_to_rerun[agent_key]["feedback"].extend(fb_list)

            # Borrar outputs anteriores de agentes que se van a re-ejecutar
            for agent_key in agents_to_rerun:
                fpath = files_to_delete.get(agent_key)
                if fpath and os.path.exists(fpath):
                    os.remove(fpath)
                    print(f"   🗑️ Eliminado {fpath} para regenerar")

            # Re-ejecutar agentes con feedback en paralelo
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {}
                for agent_key, info in agents_to_rerun.items():
                    futures[executor.submit(
                        info["func"], video, video_id, info["feedback"]
                    )] = agent_key

                for future in as_completed(futures):
                    agent_key = futures[future]
                    try:
                        resultado["results"][agent_key] = future.result()
                        print(f"   ✅ {agent_key} mejorado para {video_id}")
                    except Exception as e:
                        print(f"   ❌ {agent_key} falló en mejora: {e}")

        # Guardar resultado final
        video_output_dir = os.path.join(DATA_DIR, "videos_output")
        os.makedirs(video_output_dir, exist_ok=True)
        with open(os.path.join(video_output_dir, f"{video_id}.json"), "w", encoding="utf-8") as f:
            json.dump(resultado, f, indent=2, ensure_ascii=False)

        # Actualizar estado
        if resultado.get("quality_check", {}).get("veredicto") == "APROBADO":
            completados.add(video_id)
            status["videos_completados"] = list(completados)
            save_pipeline_status(status)
        else:
            print(f"   ⚠️ {video_id} requiere revisión manual")

        # === CHECKPOINT HUMANO ===
        print(f"\n{'─'*40}")
        print(f"📋 {video_id} LISTO PARA REVISIÓN")
        print(f"   📄 Output: data/videos_output/{video_id}.json")
        print(f"   🏷️ Veredicto: {resultado.get('quality_check', {}).get('veredicto', 'N/A')}")
        print(f"   📈 Media: {resultado.get('quality_check', {}).get('media', 'N/A')}")
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