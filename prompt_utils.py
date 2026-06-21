# prompt_utils.py
"""Utilidades de prompt compartidas entre agentes.

`format_qc_feedback` renderiza los `cambios_requeridos` del Quality Controller
como un bloque de instrucciones de revisión, para inyectarlo en el prompt de un
agente que se regenera. El esquema de cada cambio es: area / problema / solucion.
"""


def format_qc_feedback(feedback) -> str:
    """Convierte la lista de cambios del QC en instrucciones para el prompt.

    Devuelve "" si no hay feedback (es decir, es una generación inicial), de modo
    que llamar al agente sin feedback no altera su prompt original.
    """
    if not feedback:
        return ""

    lines = []
    for i, cambio in enumerate(feedback, 1):
        area = cambio.get("area", "?")
        problema = cambio.get("problema", "")
        solucion = cambio.get("solucion", "")
        lines.append(
            f"{i}. [{area}] PROBLEM: {problema}\n   REQUIRED FIX: {solucion}"
        )
    body = "\n".join(lines)

    return (
        "\n\n═══ REVISION REQUIRED (Quality Controller feedback) ═══\n"
        "This is a RE-GENERATION. A previous version was reviewed and flagged.\n"
        "You MUST address every point below and not repeat these mistakes:\n\n"
        f"{body}\n\n"
        "Apply these fixes precisely while preserving everything that already worked."
    )
