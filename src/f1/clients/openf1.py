"""Cliente HTTP da API OpenF1, com retry, backoff exponencial e rate limit."""

import logging
import time
from types import TracebackType
from typing import Any, Protocol, Self

import requests

from f1.exceptions import OpenF1APIError

logger = logging.getLogger(__name__)

Record = dict[str, Any]

RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
HTTP_NOT_FOUND = 404
HTTP_BAD_REQUEST = 400


class ApiClient(Protocol):
    """Interface mínima de um cliente da OpenF1 (permite injetar fakes em testes)."""

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> list[Record]:
        """Consulta um endpoint e retorna a lista de registros."""
        ...


class OpenF1Client:
    """Cliente da API OpenF1.

    Faz novas tentativas com backoff exponencial em respostas 429/5xx, timeouts e
    falhas de conexão, e respeita um intervalo mínimo entre requisições.

    Args:
        base_url: URL base da API (ex.: ``https://api.openf1.org/v1``).
        timeout: Timeout de cada requisição, em segundos.
        max_retries: Número de novas tentativas após a primeira falha transitória.
        min_interval: Intervalo mínimo entre requisições, em segundos.
        backoff_factor: Base do backoff; a espera é ``backoff_factor * 2**tentativa``.
        session: `requests.Session` a reutilizar; se omitida, uma nova é criada.

    Example:
        >>> with OpenF1Client("https://api.openf1.org/v1") as client:  # doctest: +SKIP
        ...     client.get("sessions", {"year": 2024})
    """

    def __init__(  # noqa: PLR0913 - parâmetros de configuração explícitos e nomeados
        self,
        base_url: str,
        *,
        timeout: float = 30,
        max_retries: int = 3,
        min_interval: float = 0.5,
        backoff_factor: float = 1.0,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.min_interval = min_interval
        self.backoff_factor = backoff_factor
        self.session = session or requests.Session()
        self._last_request_at: float | None = None

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Fecha a sessão HTTP."""
        self.session.close()

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> list[Record]:
        """Consulta um endpoint da OpenF1.

        Args:
            endpoint: Nome do endpoint, sem barra (ex.: ``laps``).
            params: Filtros da query string (ex.: ``{"session_key": 9158}``).

        Returns:
            Registros retornados pela API. Lista vazia em caso de 404 ou sem resultados.

        Raises:
            OpenF1APIError: Em erro não transitório ou após esgotar as tentativas.
        """
        url = f"{self.base_url}/{endpoint.strip('/')}"
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            self._throttle()
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
            except (requests.Timeout, requests.ConnectionError) as err:
                last_error = err
                logger.warning(
                    "Falha de rede em %s (tentativa %d): %s",
                    endpoint,
                    attempt + 1,
                    err,
                    extra={"endpoint": endpoint, "attempt": attempt + 1},
                )
            else:
                status = response.status_code
                if status == HTTP_NOT_FOUND:
                    logger.warning(
                        "Sem resultados em %s %s", endpoint, params, extra={"endpoint": endpoint}
                    )
                    return []
                if status in RETRYABLE_STATUS:
                    last_error = requests.HTTPError(f"HTTP {status}", response=response)
                    logger.warning(
                        "HTTP %d em %s (tentativa %d)",
                        status,
                        endpoint,
                        attempt + 1,
                        extra={"endpoint": endpoint, "attempt": attempt + 1, "status": status},
                    )
                elif status >= HTTP_BAD_REQUEST:
                    raise OpenF1APIError(f"{endpoint}: HTTP {status} - {response.text[:200]}")
                else:
                    return self._parse(endpoint, response, params)

            if attempt < self.max_retries:
                time.sleep(self.backoff_factor * 2**attempt)

        raise OpenF1APIError(
            f"{endpoint}: falhou após {self.max_retries + 1} tentativas"
        ) from last_error

    def _throttle(self) -> None:
        """Espera o necessário para respeitar ``min_interval`` entre requisições."""
        if self._last_request_at is not None:
            wait = self.min_interval - (time.monotonic() - self._last_request_at)
            if wait > 0:
                time.sleep(wait)
        self._last_request_at = time.monotonic()

    @staticmethod
    def _parse(
        endpoint: str, response: requests.Response, params: dict[str, Any] | None
    ) -> list[Record]:
        try:
            data = response.json()
        except ValueError as err:
            raise OpenF1APIError(f"{endpoint}: resposta não é JSON válido") from err
        if not isinstance(data, list):
            raise OpenF1APIError(f"{endpoint}: resposta inesperada ({type(data).__name__})")
        if not data:
            logger.warning(
                "Sem resultados em %s %s", endpoint, params, extra={"endpoint": endpoint}
            )
        return data
