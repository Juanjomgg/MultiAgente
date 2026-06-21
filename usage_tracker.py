# usage_tracker.py
"""Acumula el uso de tokens (y coste opcional) de las llamadas al LLM.

`call_llm` registra cada respuesta aquí; el orquestador imprime un resumen al
final de cada fase. El coste solo se calcula para los modelos presentes en
MODEL_PRICING (config.py); el resto se reporta sin coste (solo tokens).
"""
import logging
import threading

try:
    from config import MODEL_PRICING
except Exception:  # config puede fallar si falta .env; no es crítico aquí
    MODEL_PRICING = {}

logger = logging.getLogger(__name__)

_lock = threading.Lock()
# agent -> {"model", "calls", "prompt_tokens", "completion_tokens", "total_tokens"}
_usage: dict = {}


def record(agent_name: str, model: str, usage: dict) -> None:
    """Registra el `usage` de una respuesta del LLM (no falla si viene vacío)."""
    if not usage:
        return
    prompt = int(usage.get("prompt_tokens", 0) or 0)
    completion = int(usage.get("completion_tokens", 0) or 0)
    total = int(usage.get("total_tokens", prompt + completion) or 0)
    with _lock:
        entry = _usage.get(agent_name)
        if entry is None:
            entry = {"model": model, "calls": 0, "prompt_tokens": 0,
                     "completion_tokens": 0, "total_tokens": 0}
            _usage[agent_name] = entry
        entry["model"] = model
        entry["calls"] += 1
        entry["prompt_tokens"] += prompt
        entry["completion_tokens"] += completion
        entry["total_tokens"] += total


def _cost(model: str, prompt_tokens: int, completion_tokens: int):
    """Coste USD si el modelo tiene precios en MODEL_PRICING; si no, None.

    MODEL_PRICING[model] = {"input": USD_por_1M, "output": USD_por_1M}
    """
    price = MODEL_PRICING.get(model)
    if not price:
        return None
    return ((prompt_tokens / 1_000_000) * price.get("input", 0)
            + (completion_tokens / 1_000_000) * price.get("output", 0))


def snapshot() -> dict:
    """Copia del estado actual (para tests o serialización)."""
    with _lock:
        return {a: dict(e) for a, e in _usage.items()}


def reset() -> None:
    """Reinicia el acumulador (p. ej. al empezar una fase)."""
    with _lock:
        _usage.clear()


def print_summary(title: str = "USO DE TOKENS") -> None:
    """Imprime un resumen agregado por agente y el total."""
    items = snapshot()
    if not items:
        return

    logger.info(f"\n{'='*64}")
    logger.info(f"📊 {title}")
    logger.info(f"{'='*64}")
    logger.info(f"   {'Agente':<20}{'Llam.':>6}{'In':>11}{'Out':>11}{'Total':>12}{'USD':>10}")

    tot_p = tot_c = tot_t = 0
    tot_cost = 0.0
    any_cost = False
    for agent, e in sorted(items.items(), key=lambda kv: -kv[1]["total_tokens"]):
        cost = _cost(e["model"], e["prompt_tokens"], e["completion_tokens"])
        tot_p += e["prompt_tokens"]
        tot_c += e["completion_tokens"]
        tot_t += e["total_tokens"]
        cost_str = "—"
        if cost is not None:
            any_cost = True
            tot_cost += cost
            cost_str = f"${cost:.4f}"
        logger.info(f"   {agent:<20}{e['calls']:>6}{e['prompt_tokens']:>11,}"
                    f"{e['completion_tokens']:>11,}{e['total_tokens']:>12,}{cost_str:>10}")

    logger.info(f"   {'-'*60}")
    total_cost_str = f"${tot_cost:.4f}" if any_cost else "—"
    logger.info(f"   {'TOTAL':<20}{'':>6}{tot_p:>11,}{tot_c:>11,}{tot_t:>12,}{total_cost_str:>10}")
    logger.info(f"{'='*64}")
