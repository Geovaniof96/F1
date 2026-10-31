"""Registro dos endpoints da OpenF1 suportados pelo projeto."""

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType


class Scope(StrEnum):
    """Granularidade em que um endpoint é consultado e particionado."""

    YEAR = "year"
    MEETING = "meeting"
    SESSION = "session"


@dataclass(frozen=True)
class EndpointSpec:
    """Metadados de um endpoint.

    Attributes:
        name: Nome do endpoint na API (ex.: ``laps``).
        scope: Filtro usado na consulta (`Scope.YEAR`, `Scope.MEETING` ou `Scope.SESSION`).
        primary_keys: Campos que identificam um registro de forma única (usados no dedupe).
    """

    name: str
    scope: Scope
    primary_keys: tuple[str, ...]


ENDPOINTS: MappingProxyType[str, EndpointSpec] = MappingProxyType(
    {
        spec.name: spec
        for spec in (
            EndpointSpec("meetings", Scope.YEAR, ("meeting_key",)),
            EndpointSpec("sessions", Scope.YEAR, ("session_key",)),
            EndpointSpec("drivers", Scope.SESSION, ("session_key", "driver_number")),
            EndpointSpec("laps", Scope.SESSION, ("session_key", "driver_number", "lap_number")),
            EndpointSpec("session_result", Scope.SESSION, ("session_key", "driver_number")),
            EndpointSpec("pit", Scope.SESSION, ("session_key", "driver_number", "lap_number")),
            EndpointSpec("stints", Scope.SESSION, ("session_key", "driver_number", "stint_number")),
            EndpointSpec("weather", Scope.MEETING, ("meeting_key", "date")),
        )
    }
)
"""Endpoints suportados, indexados pelo nome (somente leitura)."""


def get_spec(name: str) -> EndpointSpec:
    """Retorna a especificação de um endpoint.

    Args:
        name: Nome do endpoint.

    Returns:
        A `EndpointSpec` correspondente.

    Raises:
        ValueError: Se o endpoint não for suportado.
    """
    try:
        return ENDPOINTS[name]
    except KeyError as err:
        valid = ", ".join(ENDPOINTS)
        raise ValueError(f"Endpoint não suportado: {name!r}. Válidos: {valid}") from err
