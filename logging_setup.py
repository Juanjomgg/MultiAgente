# logging_setup.py
"""Configuración central de logging para el pipeline.

setup_logging() instala dos handlers en el root logger:
  - consola (stdout): formato limpio (solo el mensaje), para conservar la
    experiencia de CLI actual.
  - fichero (DATA_DIR/logs/pipeline_<timestamp>.log): formato detallado con
    timestamp, nivel y módulo, para depurar runs largos.

Es idempotente: llamarla varias veces no duplica handlers.
"""
import logging
import os
import sys
from datetime import datetime

try:
    from config import DATA_DIR
except Exception:  # config puede fallar si falta .env; no es crítico aquí
    DATA_DIR = "data"

_configured = False


def setup_logging(level: int = logging.INFO, log_dir: str | None = None) -> str | None:
    """Configura logging de consola + fichero. Devuelve la ruta del log o None."""
    global _configured
    if _configured:
        return None

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)  # los handlers filtran; el root deja pasar todo

    # Consola: formato limpio (como los print actuales).
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(console)

    # Fichero: formato detallado con timestamp y nivel.
    log_path = None
    try:
        log_dir = log_dir or os.path.join(DATA_DIR, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, f"pipeline_{datetime.now():%Y%m%d_%H%M%S}.log")
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        root.addHandler(file_handler)
    except Exception as e:
        root.warning(f"No se pudo crear el fichero de log: {e}")

    _configured = True
    if log_path:
        root.info(f"📝 Log de esta sesión: {log_path}")
    return log_path
