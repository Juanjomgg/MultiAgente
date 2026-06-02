# llm_client.py
import requests
import json
import time
from config import ABACUS_API_KEY, ABACUS_BASE_URL, AGENT_MODELS, AGENT_MAX_TOKENS


def call_llm(agent_name: str, system_prompt: str, user_prompt: str, 
             temperature: float = 0.7, retries: int = 2) -> str:
    """
    Llama al LLM asignado a un agente via Abacus.AI API.
    Incluye retry logic y validación básica.
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

    for attempt in range(1, retries + 1):
        try:
            response = requests.post(
                ABACUS_BASE_URL, 
                headers=headers, 
                json=payload, 
                timeout=120
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]

            if not content or len(content.strip()) < 10:
                raise ValueError("Respuesta vacía o demasiado corta del LLM.")

            print(f"✅ [{agent_name}] Respuesta recibida ({len(content)} chars)")
            return content.strip()

        except (requests.RequestException, KeyError, ValueError) as e:
            print(f"⚠️ [{agent_name}] Intento {attempt}/{retries} falló: {e}")
            if attempt < retries:
                time.sleep(2 * attempt)  # backoff exponencial
            else:
                raise RuntimeError(
                    f"❌ [{agent_name}] Falló tras {retries} intentos: {e}"
                )


def call_llm_json(agent_name: str, system_prompt: str, user_prompt: str,
                  temperature: float = 0.5, retries: int = 2) -> dict:
    """
    Igual que call_llm pero parsea la respuesta como JSON.
    Útil para agentes que deben devolver datos estructurados.
    """
    # Añadimos instrucción explícita de formato JSON al system prompt
    json_system = system_prompt + "\n\nIMPORTANTE: Responde ÚNICAMENTE con JSON válido. Sin texto adicional, sin markdown, sin ```json."
    
    raw = call_llm(agent_name, json_system, user_prompt, temperature, retries)

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
        raise ValueError(
            f"❌ [{agent_name}] No devolvió JSON válido: {e}\nRespuesta raw:\n{raw[:500]}"
        )