# constants.py
"""Contrato compartido entre el Quality Controller y el Orquestador.

Fuente ÚNICA de verdad para los valores que cruzan la frontera entre el agente
que los EMITE (quality_controller) y el que los CONSUME (orchestrator).
Mantenerlos aquí hace imposible que el contrato se desincronice entre idiomas.
"""
from enum import Enum


class Verdict(str, Enum):
    """Veredictos posibles del Quality Controller."""
    APPROVED = "APPROVED"
    REVISE = "REVISE"
    REJECTED = "REJECTED"


class QCArea(str, Enum):
    """Áreas que el Quality Controller puede marcar como mejorables."""
    HOOK = "hook"
    OPEN_LOOPS = "open_loops"
    PATTERN_INTERRUPTS = "pattern_interrupts"
    RESCATE_65 = "rescate_65"
    TTS = "tts"
    SEO = "seo"
    THUMBNAIL = "thumbnail"
    COHERENCIA = "coherencia"


class AgentKey(str, Enum):
    """Claves internas de los agentes regenerables (coinciden con results[...])."""
    SCRIPT = "script"
    SEO = "seo"
    THUMBNAIL = "thumbnail"


# Mapeo área de QC → agente que debe regenerarse.
# Todas las áreas que dependen del guión se regeneran con el script_writer.
AREA_TO_AGENT: dict[QCArea, AgentKey] = {
    QCArea.HOOK: AgentKey.SCRIPT,
    QCArea.OPEN_LOOPS: AgentKey.SCRIPT,
    QCArea.PATTERN_INTERRUPTS: AgentKey.SCRIPT,
    QCArea.RESCATE_65: AgentKey.SCRIPT,
    QCArea.TTS: AgentKey.SCRIPT,
    QCArea.COHERENCIA: AgentKey.SCRIPT,
    QCArea.SEO: AgentKey.SEO,
    QCArea.THUMBNAIL: AgentKey.THUMBNAIL,
}

# Representaciones para inyectar en los prompts. Evita hardcodear los valores
# en el texto del prompt y que se desincronicen del enum.
VERDICT_ENUM_STR = "|".join(v.value for v in Verdict)
QC_AREA_ENUM_STR = "|".join(a.value for a in QCArea)


def normalize_verdict(value) -> Verdict:
    """Coacciona el veredicto devuelto por el LLM al enum.

    Devuelve Verdict.REVISE si el valor no es reconocible, de modo que un
    veredicto malformado nunca apruebe ni rechace un vídeo por accidente.
    """
    try:
        return Verdict(str(value).strip().upper())
    except (ValueError, AttributeError):
        return Verdict.REVISE


def agent_for_area(area) -> AgentKey | None:
    """Devuelve el agente que debe regenerarse para un área del QC.

    Devuelve None si el área no es reconocible (el orquestador la ignora).
    Tolera variaciones de mayúsculas/espacios en la respuesta del LLM.
    """
    try:
        return AREA_TO_AGENT.get(QCArea(str(area).strip().lower()))
    except (ValueError, AttributeError):
        return None
