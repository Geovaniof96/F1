"""Configuração de logging da aplicação."""

import logging

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s - %(message)s"


def setup_logging(level: str = "INFO") -> None:
    """Configura o logger raiz.

    Args:
        level: Nome do nível de log (ex.: ``INFO``, ``DEBUG``).

    Raises:
        ValueError: Se o nível informado não existir.
    """
    numeric = logging.getLevelNamesMapping().get(level.upper())
    if numeric is None:
        raise ValueError(f"Nível de log inválido: {level}")
    logging.basicConfig(level=numeric, format=LOG_FORMAT, force=True)
