"""Entrypoint de linha de comando ``f1-extract`` (só orquestra)."""

import argparse
from collections.abc import Sequence

from f1.clients.openf1 import OpenF1Client
from f1.config.settings import Settings, get_settings
from f1.extract.endpoints import ENDPOINTS
from f1.load.local import LocalWriter
from f1.pipeline import DEFAULT_ENDPOINTS, RunSummary, run
from f1.utils.logging import setup_logging


def _endpoint_list(value: str) -> list[str]:
    names = [n.strip() for n in value.split(",") if n.strip()]
    invalid = [n for n in names if n not in ENDPOINTS]
    if invalid or not names:
        raise argparse.ArgumentTypeError(
            f"endpoints inválidos: {', '.join(invalid) or value!r}. Válidos: {', '.join(ENDPOINTS)}"
        )
    return names


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Interpreta os argumentos de linha de comando.

    Args:
        argv: Argumentos (padrão: ``sys.argv[1:]``).

    Returns:
        Namespace com ``year``, ``endpoints``, ``session_key`` e ``log_level``.
    """
    parser = argparse.ArgumentParser(
        prog="f1-extract", description="Extrai dados históricos da OpenF1 para data/."
    )
    parser.add_argument("--year", type=int, required=True, help="Temporada (ex.: 2024).")
    parser.add_argument(
        "--endpoints",
        type=_endpoint_list,
        default=list(DEFAULT_ENDPOINTS),
        help=f"Lista separada por vírgula. Padrão: {','.join(DEFAULT_ENDPOINTS)}.",
    )
    parser.add_argument(
        "--session-key", type=int, default=None, help="Restringe a uma única sessão."
    )
    parser.add_argument("--log-level", default=None, help="Sobrescreve F1_LOG_LEVEL.")
    return parser.parse_args(argv)


def extract(
    settings: Settings,
    year: int,
    endpoints: Sequence[str] = DEFAULT_ENDPOINTS,
    session_key: int | None = None,
) -> RunSummary:
    """Monta o cliente e o writer a partir da configuração e executa o pipeline.

    Usado pelo CLI e pelo dashboard (botões de download).

    Args:
        settings: Configuração da aplicação.
        year: Temporada.
        endpoints: Endpoints a extrair.
        session_key: Restringe a uma única sessão.

    Returns:
        Resumo da execução.
    """
    with OpenF1Client(
        settings.api_base_url,
        timeout=settings.request_timeout,
        max_retries=settings.max_retries,
        min_interval=settings.min_interval_seconds,
    ) as client:
        return run(
            year,
            client,
            LocalWriter(settings.data_dir),
            endpoints=endpoints,
            session_key=session_key,
        )


def main(argv: Sequence[str] | None = None) -> int:
    """Executa a extração a partir da linha de comando.

    Args:
        argv: Argumentos (padrão: ``sys.argv[1:]``).

    Returns:
        ``0`` se tudo foi extraído, ``1`` se alguma unidade falhou.
    """
    args = parse_args(argv)
    settings = get_settings()
    setup_logging(args.log_level or settings.log_level)
    summary = extract(settings, args.year, args.endpoints, args.session_key)
    return 0 if summary.ok else 1
