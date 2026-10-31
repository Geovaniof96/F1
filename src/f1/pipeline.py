"""Orquestração extract -> transform -> load."""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from f1.clients.openf1 import ApiClient, Record
from f1.exceptions import F1Error
from f1.extract.endpoints import ENDPOINTS, EndpointSpec, Scope, get_spec
from f1.extract.openf1 import fetch_by_meeting, fetch_by_session, fetch_meetings, fetch_sessions
from f1.load.base import Partition, Writer
from f1.transform.normalize import normalize

logger = logging.getLogger(__name__)

DEFAULT_ENDPOINTS: tuple[str, ...] = tuple(ENDPOINTS)
CALENDAR_ENDPOINTS: tuple[str, ...] = ("meetings", "sessions")
SESSION_ENDPOINTS: tuple[str, ...] = tuple(
    name for name, spec in ENDPOINTS.items() if spec.scope is not Scope.YEAR
)


@dataclass
class RunSummary:
    """Resumo de uma execução.

    Attributes:
        endpoints: Endpoints processados.
        partitions: Partições gravadas (com pelo menos um registro).
        rows: Linhas tratadas gravadas.
        failures: Descrição de cada unidade (endpoint + partição) que falhou.
    """

    endpoints: list[str] = field(default_factory=list)
    partitions: int = 0
    rows: int = 0
    failures: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """``True`` se nenhuma unidade falhou."""
        return not self.failures


def run(  # noqa: PLR0913 - dependências injetadas e filtros explícitos
    year: int,
    client: ApiClient,
    writer: Writer,
    *,
    endpoints: Sequence[str] = DEFAULT_ENDPOINTS,
    session_key: int | None = None,
    extracted_at: datetime | None = None,
) -> RunSummary:
    """Extrai, trata e grava os endpoints pedidos para uma temporada.

    ``meetings`` e ``sessions`` são sempre gravados para o ano inteiro. Os demais
    endpoints são buscados por sessão (ou por meeting, no caso de ``weather``),
    opcionalmente restritos a ``session_key``. A falha de uma unidade é registrada
    e contada sem interromper as demais.

    Args:
        year: Temporada.
        client: Cliente da OpenF1.
        writer: Destino dos dados.
        endpoints: Endpoints a extrair (padrão: todos os suportados).
        session_key: Restringe os endpoints por sessão/meeting a uma única sessão.
        extracted_at: Momento da extração (padrão: agora, em UTC).

    Returns:
        Resumo da execução.

    Raises:
        ValueError: Se algum endpoint não for suportado.
    """
    specs = [get_spec(name) for name in dict.fromkeys(endpoints)]
    extracted_at = extracted_at or datetime.now(UTC)
    summary = RunSummary(endpoints=[s.name for s in specs])
    ctx = _Context(year, client, writer, extracted_at, summary)

    if "meetings" in summary.endpoints:
        ctx.process(get_spec("meetings"), Partition(year), lambda: fetch_meetings(client, year))

    needs_sessions = any(s.name == "sessions" or s.scope is not Scope.YEAR for s in specs)
    all_sessions = (
        ctx.load_sessions(write="sessions" in summary.endpoints) if needs_sessions else []
    )
    sessions = [s for s in all_sessions if s.get("session_key") is not None]
    if session_key is not None:
        sessions = [s for s in sessions if s["session_key"] == session_key]
        if all_sessions and not sessions:
            summary.failures.append(f"sessions: session_key={session_key} não encontrada em {year}")
            logger.error("session_key=%s não encontrada em %s", session_key, year)

    meeting_keys = sorted({s["meeting_key"] for s in sessions if s.get("meeting_key") is not None})
    for spec in specs:
        if spec.scope is Scope.MEETING:
            for meeting in meeting_keys:
                ctx.process(
                    spec,
                    Partition(year, meeting_key=meeting),
                    _bind(fetch_by_meeting, client, spec.name, meeting),
                )
        elif spec.scope is Scope.SESSION:
            for session in sessions:
                ctx.process(
                    spec,
                    Partition(year, session.get("meeting_key"), session["session_key"]),
                    _bind(fetch_by_session, client, spec.name, session["session_key"]),
                )

    logger.info(
        "Extração concluída: %d endpoints, %d partições, %d linhas, %d falhas",
        len(summary.endpoints),
        summary.partitions,
        summary.rows,
        len(summary.failures),
        extra={"year": year, "rows": summary.rows, "failures": len(summary.failures)},
    )
    return summary


def _bind(
    fetch: Callable[[ApiClient, str, int], list[Record]], client: ApiClient, endpoint: str, key: int
) -> Callable[[], list[Record]]:
    return lambda: fetch(client, endpoint, key)


@dataclass
class _Context:
    year: int
    client: ApiClient
    writer: Writer
    extracted_at: datetime
    summary: RunSummary

    def load_sessions(self, *, write: bool) -> list[Record]:
        """Busca as sessões do ano (gravando-as se pedido) e as retorna brutas."""
        spec = get_spec("sessions")
        partition = Partition(self.year)
        if write:
            return self.process(spec, partition, lambda: fetch_sessions(self.client, self.year))
        try:
            return fetch_sessions(self.client, self.year)
        except F1Error as err:
            self._fail(spec, partition, err)
            return []

    def process(
        self, spec: EndpointSpec, partition: Partition, fetch: Callable[[], list[Record]]
    ) -> list[Record]:
        """Executa fetch -> normalize -> write para uma partição; falhas são contadas."""
        try:
            raw = fetch()
            rows = normalize(raw, spec, self.extracted_at)
            self.writer.write_raw(spec.name, partition, raw)
            path = self.writer.write_processed(spec.name, partition, rows)
        except F1Error as err:
            self._fail(spec, partition, err)
            return []
        if path is not None:
            self.summary.partitions += 1
            self.summary.rows += len(rows)
            logger.info("%s %s: %d linhas", spec.name, "/".join(partition.parts()), len(rows))
        return raw

    def _fail(self, spec: EndpointSpec, partition: Partition, err: F1Error) -> None:
        where = f"{spec.name} {'/'.join(partition.parts())}"
        self.summary.failures.append(f"{where}: {err}")
        logger.error("Falha em %s: %s", where, err, extra={"endpoint": spec.name})
