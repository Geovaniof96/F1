from datetime import UTC, datetime
from typing import Any

import pytest

from f1.exceptions import InvalidRecordError
from f1.extract.endpoints import get_spec
from f1.transform.normalize import (
    add_metadata,
    coerce_mixed_types,
    deduplicate,
    normalize,
    parse_dates,
)

EXTRACTED_AT = datetime(2026, 10, 30, 12, tzinfo=UTC)


@pytest.mark.parametrize(
    ("record", "expected"),
    [
        (
            {"date_start": "2024-03-02T15:00:00+00:00"},
            {"date_start": datetime(2024, 3, 2, 15, tzinfo=UTC)},
        ),
        (
            {"date": "2024-03-02T15:00:00.123000+00:00", "x": "2024-01-01"},
            {"date": datetime(2024, 3, 2, 15, 0, 0, 123000, tzinfo=UTC), "x": "2024-01-01"},
        ),
        ({"date_end": None}, {"date_end": None}),
        ({"date_start": "não é data"}, {"date_start": "não é data"}),
    ],
)
def test_parse_dates_converte_apenas_campos_date_iso(
    record: dict[str, Any], expected: dict[str, Any]
) -> None:
    assert parse_dates(record) == expected


def test_parse_dates_nao_altera_o_original() -> None:
    record = {"date": "2024-03-02T15:00:00+00:00"}
    parse_dates(record)
    assert record == {"date": "2024-03-02T15:00:00+00:00"}


def test_add_metadata_inclui_endpoint_e_data_de_extracao() -> None:
    result = add_metadata([{"a": 1}], "laps", EXTRACTED_AT)
    assert result == [{"a": 1, "_endpoint": "laps", "_extracted_at": EXTRACTED_AT}]


def test_deduplicate_mantem_ultimo_por_chave_preservando_ordem() -> None:
    records = [{"k": 1, "v": "velho"}, {"k": 2, "v": "b"}, {"k": 1, "v": "novo"}]
    assert deduplicate(records, ("k",)) == [{"k": 1, "v": "novo"}, {"k": 2, "v": "b"}]


@pytest.mark.parametrize("record", [{"v": 1}, {"k": None, "v": 1}])
def test_deduplicate_rejeita_registro_sem_chave(record: dict[str, Any]) -> None:
    with pytest.raises(InvalidRecordError, match="chave primária"):
        deduplicate([record], ("k",))


def test_coerce_mixed_types_unifica_int_e_float() -> None:
    result = coerce_mixed_types([{"t": 90}, {"t": 90.5}, {"t": None}])
    assert result == [{"t": 90.0}, {"t": 90.5}, {"t": None}]
    assert isinstance(result[0]["t"], float)


def test_coerce_mixed_types_converte_mistura_em_texto() -> None:
    result = coerce_mixed_types([{"gap": 1.5}, {"gap": "+1 LAP"}, {"gap": [1, None]}])
    assert result == [{"gap": "1.5"}, {"gap": "+1 LAP"}, {"gap": "[1, null]"}]


def test_coerce_mixed_types_mantem_registros_homogeneos() -> None:
    records = [{"a": 1, "b": "x"}, {"a": 2, "b": None}]
    assert coerce_mixed_types(records) is records


def test_normalize_compoe_todas_as_etapas() -> None:
    raw = [
        {"session_key": 1, "driver_number": 44, "lap_number": 1, "date_start": None},
        {
            "session_key": 1,
            "driver_number": 44,
            "lap_number": 1,
            "date_start": "2024-03-02T15:00:00+00:00",
        },
    ]
    result = normalize(raw, get_spec("laps"), EXTRACTED_AT)
    assert result == [
        {
            "session_key": 1,
            "driver_number": 44,
            "lap_number": 1,
            "date_start": datetime(2024, 3, 2, 15, tzinfo=UTC),
            "_endpoint": "laps",
            "_extracted_at": EXTRACTED_AT,
        }
    ]
