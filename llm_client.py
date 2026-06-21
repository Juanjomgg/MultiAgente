# llm_client.py
import logging
import requests
import json
import time
from config import ABACUS_API_KEY, ABACUS_BASE_URL, AGENT_MODELS, AGENT_MAX_TOKENS
import usage_tracker
logger = logging.getLogger(__name__)


def call_llm(agent_name: str, system_prompt: str, user_prompt: str, 
             temperature: float = 0.7, retries: int = 2,
             json_mode: bool = False) -> str:
    """
    Llama al LLM asignado a un agente via Abacus.AI API.
    Incluye retry logic, validación básica, detección de truncamiento y, si
    json_mode=True, salida JSON nativa (response_format) con degradación
    automática cuando el endpoint no la soporta.
    """
    model = AGENT_MODELS.get(agent_name)
    max_tokens = AGENT_MAX_TOKENS.get(agent_name, 2000)

    if not model:
        raise ValueError(f"Agente '{agent_name}' no tiene modelo asignado en config.")

    headers = {
        "Authorization": f"Bearer {ABACUS_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if json_mode:
        # Salida JSON nativa del API (más fiable que pedirlo solo por prompt).
        payload["response_format"] = {"type": "json_object"}

    attempt = 0
    while attempt < retries:
        attempt += 1
        try:
            response = requests.post(
                ABACUS_BASE_URL, 
                headers=headers, 
                json=payload, 
                timeout=300
            )
            response.raise_for_status()
            data = response.json()
            choice = data["choices"][0]
            content = choice["message"]["content"]

            if choice.get("finish_reason") == "length":
                logger.warning(
                    f"⚠️ [{agent_name}] Respuesta truncada por max_tokens "
                    f"({max_tokens}). Considera subir AGENT_MAX_TOKENS."
                )

            if not content or len(content.strip()) < 10:
                raise ValueError("Respuesta vacía o demasiado corta del LLM.")

            usage_tracker.record(agent_name, model, data.get("usage", {}))
            logger.info(f"✅ [{agent_name}] Respuesta recibida ({len(content)} chars)")
            return content.strip()

        except (requests.RequestException, KeyError, ValueError) as e:
            # Si el endpoint no acepta response_format, degradamos a modo prompt
            # y reintentamos sin gastar este intento (solo puede ocurrir una vez).
            status = getattr(getattr(e, "response", None), "status_code", None)
            if "response_format" in payload and status in (400, 422):
                logger.warning(
                    f"⚠️ [{agent_name}] El endpoint no aceptó response_format; "
                    f"reintentando sin JSON mode nativo."
                )
                payload.pop("response_format", None)
                attempt -= 1
                continue

            logger.warning(f"⚠️ [{agent_name}] Intento {attempt}/{retries} falló: {e}")
            if attempt < retries:
                time.sleep(2 * attempt)  # backoff exponencial
            else:
                raise RuntimeError(
                    f"❌ [{agent_name}] Falló tras {retries} intentos: {e}"
                )

def _repair_json(text: str) -> dict | None:
    """Intenta reparar JSON truncado cerrando brackets/braces abiertos."""
    # Contar brackets abiertos
    open_braces = text.count('{') - text.count('}')
    open_brackets = text.count('[') - text.count(']')
    
    # Si hay un string sin cerrar, cerrarlo
    if text.rstrip().endswith('"') is False and text.count('"') % 2 != 0:
        text += '"'
    
    # Cerrar brackets y braces pendientes
    text += ']' * open_brackets
    text += '}' * open_braces
    
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None

def call_llm_json(agent_name: str, system_prompt: str, user_prompt: str,
                  temperature: float = 0.5, retries: int = 2) -> dict:
    """
    Igual que call_llm pero parsea la respuesta como JSON.
    Útil para agentes que deben devolver datos estructurados.
    """
    # Añadimos instrucción explícita de formato JSON al system prompt
    json_system = system_prompt + "\n\nIMPORTANTE: Responde ÚNICAMENTE con JSON válido. Sin texto adicional, sin markdown, sin ```json."
    
    raw = call_llm(agent_name, json_system, user_prompt, temperature, retries, json_mode=True)

    # Limpieza por si el modelo envuelve en markdown
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]  # quita primera línea ```json
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        # Intentar reparar JSON truncado
        logger.warning(f"⚠️ [{agent_name}] JSON truncado, intentando reparar...")
        repaired = _repair_json(cleaned)
        if repaired:
            return repaired
        raise ValueError(
            f"❌ [{agent_name}] No devolvió JSON válido: {e}\nRespuesta raw:\n{raw[:500]}"
        )