# orchestrator.py
import logging
from logging_setup import setup_logging
import json
import os
import argparse
from constants import Verdict, AgentKey, agent_for_area
from config import DATA_DIR
import usage_tracker
logger = logging.getLogger(__name__)

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

    logger.info(f"\n{'='*60}")
    logger.info("🚀 FASE 1: DESCUBRIMIENTO DE NICHO")
    logger.info(f"{'='*60}\n")
    usage_tracker.reset()

    # Paso 1: Scraper
    logger.info("── Paso 1/3: Scraping YouTube ──")
    qualifying = run_scraper()
    if not qualifying:
        logger.warning("⚠️ No hay canales qualifying aún. Ejecuta de nuevo mañana.")
        return None

    # Paso 2: Análisis de nichos
    logger.info("\n── Paso 2/3: Análisis de nichos ──")
    nichos = run_niche_hunter()

    # Paso 3: Validación
    logger.info("\n── Paso 3/3: Validación de nichos ──")
    validacion = run_niche_validator()

    ganador = validacion.get("nicho_ganador", "No definido")
    logger.info(f"\n🏆 NICHO GANADOR: {ganador}")

    usage_tracker.print_summary("USO DE TOKENS — FASE 1")
    return validacion


def run_phase_2():
    """Fase 2: Estrategia de contenido (secuencial)."""
    from agents.content_strategist import run_content_strategist

    logger.info(f"\n{'='*60}")
    logger.info("📋 FASE 2: ESTRATEGIA DE CONTENIDO")
    logger.info(f"{'='*60}\n")
    usage_tracker.reset()

    calendario = run_content_strategist()
    videos = calendario.get("calendario", [])
    logger.info(f"\n📅 Calendario generado: {len(videos)} vídeos")

    usage_tracker.print_summary("USO DE TOKENS — FASE 2")
    return calendario


def process_single_video(video_data, video_index):
    """Procesa un vídeo siguiendo la cadena de dependencias script → seo → thumbnail.

    Los datos fluyen en memoria entre agentes; los archivos JSON son solo
    persistencia/caché para poder reanudar (saltar) el trabajo ya hecho.
    """
    from agents.script_writer import run_script_writer
    from agents.seo_optimizer import run_seo_optimizer
    from agents.thumbnail_conceptor import run_thumbnail_conceptor

    video_id = f"video_{video_index:02d}"
    logger.info(f"\n🎬 Procesando {video_id}: {video_data['titulo']}")

    results = {}
    errors = {}

    script_file = os.path.join(DATA_DIR, "scripts", f"{video_id}.json")
    seo_file    = os.path.join(DATA_DIR, "seo", f"{video_id}.json")
    thumb_file  = os.path.join(DATA_DIR, "thumbnails", f"{video_id}_concept.json")

    # ── STEP 1: Script (sin dependencia previa) ────────────────────────────
    script_data = None
    if os.path.exists(script_file):
        logger.info(f"   ⏭️ Script already exists, skipping...")
        with open(script_file, "r", encoding="utf-8") as f:
            results["script"] = json.load(f)
        script_data = results["script"]
    else:
        try:
            results["script"] = run_script_writer(video_data, video_id)
            script_data = results["script"]
            logger.info(f"   ✅ script done")
        except Exception as e:
            errors["script"] = str(e)
            logger.error(f"   ❌ script failed: {e}")

    # ── STEP 2: SEO (depende del script — lo recibe en memoria) ────────────
    seo_data = None
    if os.path.exists(seo_file):
        logger.info(f"   ⏭️ SEO already exists, skipping...")
        with open(seo_file, "r", encoding="utf-8") as f:
            results["seo"] = json.load(f)
        seo_data = results["seo"]
    else:
        try:
            results["seo"] = run_seo_optimizer(video_data, video_id, script_data=script_data)
            seo_data = results["seo"]
            logger.info(f"   ✅ seo done")
        except Exception as e:
            errors["seo"] = str(e)
            logger.error(f"   ❌ seo failed: {e}")

    # ── STEP 3: Thumbnail (depende del SEO para alinear título/texto) ──────
    if os.path.exists(thumb_file):
        logger.info(f"   ⏭️ Thumbnail already exists, skipping...")
        with open(thumb_file, "r", encoding="utf-8") as f:
            results["thumbnail"] = json.load(f)
    else:
        try:
            results["thumbnail"] = run_thumbnail_conceptor(video_data, video_id, seo_data=seo_data)
            logger.info(f"   ✅ thumbnail done")
        except Exception as e:
            errors["thumbnail"] = str(e)
            logger.error(f"   ❌ thumbnail failed: {e}")

    return {
        "video_id": video_id,
        "video_data": video_data,
        "results": results,
        "errors": errors,
        "status": "completado" if not errors else "parcial"
    }


def run_phase_3(auto: bool = False):
    """Fase 3: Producción de vídeos con loop de auto-mejora.

    Si auto=True (modo desatendido), no pide confirmación entre vídeos.
    """
    from agents.quality_controller import run_quality_check
    from agents.script_writer import run_script_writer
    from agents.seo_optimizer import run_seo_optimizer
    from agents.thumbnail_conceptor import run_thumbnail_conceptor

    MAX_MEJORAS = 2  # Máximo 2 rondas de mejora por vídeo

    logger.info(f"\n{'='*60}")
    logger.info("🎬 FASE 3: PRODUCCIÓN DE VÍDEOS")
    logger.info(f"{'='*60}\n")
    usage_tracker.reset()

    # Cargar calendario
    with open(CONTENT_CALENDAR_FILE, "r", encoding="utf-8") as f:
        calendario = json.load(f)

    videos = calendario.get("calendario", [])
    status = load_pipeline_status()
    completados = set(status.get("videos_completados", []))

    for i, video in enumerate(videos, 1):
        video_id = f"video_{i:02d}"

        if video_id in completados:
            logger.info(f"⏭️ {video_id} ya procesado, saltando...")
            continue

        # === GENERACIÓN INICIAL ===
        resultado = process_single_video(video, i)

        if resultado["status"] != "completado":
            logger.warning(f"   ⚠️ {video_id} tiene errores, saltando QC")
            continue

        # === LOOP DE MEJORA ===
        for ronda in range(MAX_MEJORAS + 1):  # 0=QC inicial, 1-2=mejoras
            logger.info(f"\n🔍 Quality check para {video_id} (ronda {ronda})...")
            qc_result = run_quality_check(resultado)
            resultado["quality_check"] = qc_result

            veredicto = qc_result.get("veredicto", Verdict.REVISE.value)

            if veredicto == Verdict.APPROVED:
                logger.info(f"\n   🎉 {video_id} APROBADO en ronda {ronda}!")
                break

            if ronda >= MAX_MEJORAS:
                logger.warning(f"\n   ⚠️ {video_id} NO aprobado tras {MAX_MEJORAS} mejoras. Requiere revisión humana.")
                break

            # === APLICAR MEJORAS ===
            cambios = qc_result.get("cambios_requeridos", [])
            if not cambios:
                logger.warning(f"   ⚠️ Veredicto {veredicto} pero sin cambios específicos. Parando.")
                break

            # Agrupar feedback por área
            feedback_por_area = {}
            for cambio in cambios:
                area = cambio.get("area", "")
                if area not in feedback_por_area:
                    feedback_por_area[area] = []
                feedback_por_area[area].append(cambio)

            logger.info(f"\n   🔧 Ronda {ronda + 1}: Mejorando {', '.join(feedback_por_area.keys())}...")

            # Mapeo agente → función. El área→agente vive en constants.py
            # (AREA_TO_AGENT) para que QC y orquestador no se desincronicen.
            agent_funcs = {
                AgentKey.SCRIPT: run_script_writer,
                AgentKey.SEO: run_seo_optimizer,
                AgentKey.THUMBNAIL: run_thumbnail_conceptor,
            }

            # Eliminar outputs anteriores de las áreas a mejorar
            files_to_delete = {
                AgentKey.SCRIPT.value: os.path.join(DATA_DIR, "scripts", f"{video_id}.json"),
                AgentKey.SEO.value: os.path.join(DATA_DIR, "seo", f"{video_id}.json"),
                AgentKey.THUMBNAIL.value: os.path.join(DATA_DIR, "thumbnails", f"{video_id}_concept.json"),
            }

            agents_to_rerun = {}  # {agent_key: {"func", "feedback"}}
            for area, fb_list in feedback_por_area.items():
                agent = agent_for_area(area)
                if agent is None:
                    logger.warning(f"   ⚠️ Área '{area}' sin agente asociado, se ignora.")
                    continue
                agent_key = agent.value
                if agent_key not in agents_to_rerun:
                    agents_to_rerun[agent_key] = {"func": agent_funcs[agent], "feedback": []}
                agents_to_rerun[agent_key]["feedback"].extend(fb_list)

            # Borrar outputs anteriores de agentes que se van a re-ejecutar
            for agent_key in agents_to_rerun:
                fpath = files_to_delete.get(agent_key)
                if fpath and os.path.exists(fpath):
                    os.remove(fpath)
                    logger.info(f"   🗑️ Eliminado {fpath} para regenerar")

            # Re-ejecutar en orden de dependencia (script → seo → thumbnail),
            # pasando los datos frescos en memoria. Secuencial por diseño: el
            # SEO depende del script y el thumbnail del SEO, así que se lee el
            # resultado más reciente justo antes de cada paso.
            def _rerun(agent_key, **dep_kwargs):
                info = agents_to_rerun.get(agent_key)
                if not info:
                    return
                try:
                    resultado["results"][agent_key] = info["func"](
                        video, video_id, info["feedback"], **dep_kwargs
                    )
                    logger.info(f"   ✅ {agent_key} mejorado para {video_id}")
                except Exception as e:
                    logger.error(f"   ❌ {agent_key} falló en mejora: {e}")

            _rerun(AgentKey.SCRIPT.value)
            _rerun(AgentKey.SEO.value, script_data=resultado["results"].get("script"))
            _rerun(AgentKey.THUMBNAIL.value, seo_data=resultado["results"].get("seo"))

        # Guardar resultado final
        video_output_dir = os.path.join(DATA_DIR, "videos_output")
        os.makedirs(video_output_dir, exist_ok=True)
        with open(os.path.join(video_output_dir, f"{video_id}.json"), "w", encoding="utf-8") as f:
            json.dump(resultado, f, indent=2, ensure_ascii=False)

        # Actualizar estado
        if resultado.get("quality_check", {}).get("veredicto") == Verdict.APPROVED:
            completados.add(video_id)
            status["videos_completados"] = list(completados)
            save_pipeline_status(status)
        else:
            logger.warning(f"   ⚠️ {video_id} requiere revisión manual")

        # === CHECKPOINT HUMANO ===
        logger.info(f"\n{'─'*40}")
        logger.info(f"📋 {video_id} LISTO PARA REVISIÓN")
        logger.info(f"   📄 Output: data/videos_output/{video_id}.json")
        logger.info(f"   🏷️ Veredicto: {resultado.get('quality_check', {}).get('veredicto', 'N/A')}")
        logger.info(f"   📈 Media: {resultado.get('quality_check', {}).get('media', 'N/A')}")
        logger.info(f"   Videos restantes: {len(videos) - i}")
        logger.info(f"{'─'*40}")

        if auto:
            logger.info("   ▶️ Modo desatendido: siguiente vídeo automáticamente.")
            continue

        respuesta = input("\n¿Continuar con el siguiente vídeo? (s/n/salir): ").strip().lower()
        if respuesta == "salir":
            logger.info("👋 Pipeline pausado. Puedes retomar ejecutando de nuevo.")
            usage_tracker.print_summary("USO DE TOKENS — FASE 3 (parcial)")
            return
        elif respuesta == "n":
            logger.info(f"🔄 Puedes revisar y re-ejecutar {video_id} manualmente.")
            completados.discard(video_id)
            status["videos_completados"] = list(completados)
            save_pipeline_status(status)
            continue

    logger.info(f"\n🎉 ¡Todos los vídeos procesados!")
    usage_tracker.print_summary("USO DE TOKENS — FASE 3")


def _parse_args():
    """CLI: permite ejecutar sin menú y de forma desatendida.

    --phase {1,2,3,full} (o env PIPELINE_PHASE): salta el menú interactivo.
    -y/--yes (o env AUTO_APPROVE=1): no pide confirmación entre vídeos.
    """
    parser = argparse.ArgumentParser(
        description="YouTube Channel Factory — pipeline multiagente"
    )
    parser.add_argument(
        "--phase", choices=["1", "2", "3", "full"],
        default=os.getenv("PIPELINE_PHASE"),
        help="Fase a ejecutar. Si se omite, se pregunta por menú.",
    )
    parser.add_argument(
        "-y", "--yes", action="store_true",
        default=os.getenv("AUTO_APPROVE", "").lower() in ("1", "true", "yes", "y"),
        help="Modo desatendido: no pide confirmación entre vídeos (Fase 3).",
    )
    return parser.parse_args()


def main():
    """Pipeline principal."""
    setup_logging()
    args = _parse_args()
    auto = args.yes

    logger.info(f"\n{'='*60}")
    logger.info("🏭 YOUTUBE CHANNEL FACTORY — PIPELINE")
    logger.info(f"{'='*60}")

    status = load_pipeline_status()
    logger.info(f"\n📊 Estado actual: {status['fase']}")
    logger.info(f"   Videos completados: {len(status.get('videos_completados', []))}")

    opcion = args.phase
    if opcion:
        logger.info(f"\n▶️ Fase '{opcion}' seleccionada (no interactivo)"
                    f"{' · auto-aprobación ON' if auto else ''}")
    else:
        logger.info("\n¿Qué fase ejecutar?")
        logger.info("  1 → Fase 1: Descubrimiento de nicho (scraper + análisis + validación)")
        logger.info("  2 → Fase 2: Estrategia de contenido (calendario 30 días)")
        logger.info("  3 → Fase 3: Producción de vídeos (scripts + SEO + thumbnails)")
        logger.info("  full → Ejecutar todo desde el principio")
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
        run_phase_3(auto=auto)


if __name__ == "__main__":
    main()