# test_connection.py
from llm_client import call_llm

respuesta = call_llm(
    agent_name="seo_optimizer",
    system_prompt="Eres un asistente útil.",
    user_prompt="Responde solo: CONEXIÓN OK"
)
print(respuesta)