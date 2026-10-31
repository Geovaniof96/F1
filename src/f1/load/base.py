"""Interface de gravação e definição de partição."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from f1.clients.openf1 import Record


@dataclass(frozen=True)
class Partition:
    """Partição determinística de destino.

    Attributes:
        year: Temporada.
        meeting_key: Meeting, para endpoints por meeting ou sessão.
        session_key: Sessão, para endpoints por sessão.
    """

    year: int
    meeting_key: int | None = None
    session_key: int | None = None

    def parts(self) -> list[str]:
        """Retorna os segmentos de caminho no estilo Hive (``chave=valor``).

        Returns:
            Ex.: ``["year=2024", "meeting_key=1229", "session_key=9158"]``.
        """
        segments = [f"year={self.year}"]
        if self.meeting_key is not None:
            segments.append(f"meeting_key={self.meeting_key}")
        if self.session_key is not None:
            segments.append(f"session_key={self.session_key}")
        return segments


class Writer(Protocol):
    """Destino dos dados. Implementações devem sobrescrever a partição (idempotência)."""

    def write_raw(self, endpoint: str, partition: Partition, records: list[Record]) -> Path | None:
        """Grava os registros como vieram da API. Retorna o caminho ou ``None`` se vazio."""
        ...

    def write_processed(
        self, endpoint: str, partition: Partition, records: list[Record]
    ) -> Path | None:
        """Grava os registros tratados. Retorna o caminho ou ``None`` se vazio."""
        ...
