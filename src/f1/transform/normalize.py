"""Normalização dos registros da OpenF1 (funções puras)."""

import json
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from f1.clients.openf1 import Record
from f1.exceptions import InvalidRecordError
from f1.extract.endpoints import EndpointSpec

DATE_PREFIX = "date"


def parse_dates(record: Record) -> Record:
    """Converte campos ``date*`` em ISO 8601 para `datetime`.

    Valores que não são texto ISO válido são mantidos como estão.

    Args:
        record: Registro bruto.

    Returns:
        Novo registro com as datas convertidas.
    """
    parsed = dict(record)
    for field, value in record.items():
        if field.startswith(DATE_PREFIX) and isinstance(value, str):
            try:
                parsed[field] = datetime.fromisoformat(value)
            except ValueError:
                parsed[field] = value
    return parsed


def add_metadata(records: Iterable[Record], endpoint: str, extracted_at: datetime) -> list[Record]:
    """Adiciona as colunas de linhagem ``_endpoint`` e ``_extracted_at``.

    Args:
        records: Registros a enriquecer.
        endpoint: Nome do endpoint de origem.
        extracted_at: Momento da extração.

    Returns:
        Novos registros com os metadados.
    """
    return [{**r, "_endpoint": endpoint, "_extracted_at": extracted_at} for r in records]


def deduplicate(records: Iterable[Record], keys: tuple[str, ...]) -> list[Record]:
    """Remove duplicatas mantendo o último registro de cada chave primária.

    A ordem da primeira ocorrência de cada chave é preservada.

    Args:
        records: Registros a deduplicar.
        keys: Campos da chave primária.

    Returns:
        Registros únicos por chave.

    Raises:
        InvalidRecordError: Se algum registro não tiver um dos campos da chave.
    """
    unique: dict[tuple[Any, ...], Record] = {}
    for record in records:
        missing = [k for k in keys if record.get(k) is None]
        if missing:
            raise InvalidRecordError(f"Registro sem chave primária {missing}: {record}")
        unique[tuple(record[k] for k in keys)] = record
    return list(unique.values())


def coerce_mixed_types(records: list[Record]) -> list[Record]:
    """Uniformiza colunas com tipos mistos para permitir a gravação em Parquet.

    Colunas só com ``int`` e ``float`` viram ``float``. Qualquer outra mistura
    (ex.: ``gap_to_leader`` com número e ``"+1 LAP"``) vira texto, com listas e
    dicionários serializados em JSON.

    Args:
        records: Registros normalizados.

    Returns:
        Novos registros com tipos consistentes por coluna.
    """
    types: dict[str, set[str]] = {}
    for record in records:
        for field, value in record.items():
            if value is not None:
                types.setdefault(field, set()).add(type(value).__name__)

    numeric = {"int", "float"}
    to_float = {f for f, t in types.items() if len(t) > 1 and t <= numeric}
    to_text = {f for f, t in types.items() if len(t) > 1 and not t <= numeric}
    if not to_float and not to_text:
        return records

    def convert(field: str, value: Any) -> Any:
        if value is None:
            return None
        if field in to_float:
            return float(value)
        if field in to_text and not isinstance(value, str):
            return json.dumps(value, default=str)
        return value

    return [{f: convert(f, v) for f, v in record.items()} for record in records]


def normalize(
    records: Iterable[Record], spec: EndpointSpec, extracted_at: datetime
) -> list[Record]:
    """Aplica todo o tratamento a registros de um endpoint.

    Ordem: `parse_dates` -> `add_metadata` -> `deduplicate` -> `coerce_mixed_types`.

    Args:
        records: Registros brutos da API.
        spec: Especificação do endpoint.
        extracted_at: Momento da extração.

    Returns:
        Registros prontos para gravação.

    Raises:
        InvalidRecordError: Se algum registro não tiver a chave primária.
    """
    parsed = (parse_dates(r) for r in records)
    enriched = add_metadata(parsed, spec.name, extracted_at)
    return coerce_mixed_types(deduplicate(enriched, spec.primary_keys))
