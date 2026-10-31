"""Writer local: JSON bruto em ``raw/`` e Parquet tratado em ``processed/``."""

import json
import logging
from collections.abc import Callable
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from f1.clients.openf1 import Record
from f1.exceptions import WriteError
from f1.load.base import Partition

logger = logging.getLogger(__name__)

RAW_FILE = "data.json"
PROCESSED_FILE = "data.parquet"


class LocalWriter:
    """Grava partições no sistema de arquivos local de forma atômica e idempotente.

    Layout::

        <base_dir>/raw/<endpoint>/year=YYYY/[meeting_key=M/][session_key=S/]data.json
        <base_dir>/processed/<endpoint>/year=YYYY/.../data.parquet

    Args:
        base_dir: Diretório raiz dos dados.
    """

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir)

    def path_for(self, layer: str, endpoint: str, partition: Partition, filename: str) -> Path:
        """Monta o caminho de um arquivo de partição.

        Args:
            layer: Camada (``raw`` ou ``processed``).
            endpoint: Nome do endpoint.
            partition: Partição de destino.
            filename: Nome do arquivo.

        Returns:
            Caminho completo do arquivo.
        """
        return self.base_dir.joinpath(layer, endpoint, *partition.parts(), filename)

    def write_raw(self, endpoint: str, partition: Partition, records: list[Record]) -> Path | None:
        """Grava os registros brutos em JSON, sobrescrevendo a partição.

        Args:
            endpoint: Nome do endpoint.
            partition: Partição de destino.
            records: Registros como retornados pela API.

        Returns:
            Caminho gravado, ou ``None`` se não houver registros.

        Raises:
            WriteError: Se a gravação falhar.
        """
        if not records:
            return None
        path = self.path_for("raw", endpoint, partition, RAW_FILE)
        payload = json.dumps(records, ensure_ascii=False, default=str)
        try:
            _atomic_write(path, lambda tmp: tmp.write_text(payload, encoding="utf-8"))
        except OSError as err:
            raise WriteError(f"Falha ao gravar {path}") from err
        return path

    def write_processed(
        self, endpoint: str, partition: Partition, records: list[Record]
    ) -> Path | None:
        """Grava os registros tratados em Parquet, sobrescrevendo a partição.

        Args:
            endpoint: Nome do endpoint.
            partition: Partição de destino.
            records: Registros normalizados.

        Returns:
            Caminho gravado, ou ``None`` se não houver registros.

        Raises:
            WriteError: Se a conversão para Arrow ou a gravação falhar.
        """
        if not records:
            return None
        path = self.path_for("processed", endpoint, partition, PROCESSED_FILE)
        try:
            table = to_table(records)
            _atomic_write(path, lambda tmp: pq.write_table(table, tmp))
        except (pa.ArrowException, OSError) as err:
            raise WriteError(f"Falha ao gravar {path}: {err}") from err
        return path


def to_table(records: list[Record]) -> pa.Table:
    """Converte registros em tabela Arrow usando a união de todas as colunas.

    Diferente de ``pa.Table.from_pylist``, não descarta colunas ausentes no
    primeiro registro.

    Args:
        records: Registros normalizados.

    Returns:
        Tabela Arrow; colunas ausentes num registro viram nulo.
    """
    columns = list(dict.fromkeys(field for record in records for field in record))
    return pa.table({c: [r.get(c) for r in records] for c in columns})


def _atomic_write(path: Path, write: Callable[[Path], object]) -> None:
    """Grava em ``<arquivo>.tmp`` no mesmo diretório e renomeia por cima do destino."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    try:
        write(tmp)
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)
    logger.debug("Partição gravada: %s", path)
