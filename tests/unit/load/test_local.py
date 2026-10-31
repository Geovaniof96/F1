import json
from datetime import UTC, datetime
from pathlib import Path

import pyarrow.parquet as pq
import pytest
from pytest_mock import MockerFixture

from f1.exceptions import WriteError
from f1.load.base import Partition
from f1.load.local import LocalWriter

SESSION = Partition(year=2024, meeting_key=1229, session_key=9158)


@pytest.mark.parametrize(
    ("partition", "expected"),
    [
        (Partition(2024), ["year=2024"]),
        (Partition(2024, meeting_key=1229), ["year=2024", "meeting_key=1229"]),
        (SESSION, ["year=2024", "meeting_key=1229", "session_key=9158"]),
    ],
)
def test_partition_parts_no_estilo_hive(partition: Partition, expected: list[str]) -> None:
    assert partition.parts() == expected


def test_write_raw_grava_json_na_particao(tmp_path: Path) -> None:
    records = [{"lap_number": 1, "driver_number": 44}]

    path = LocalWriter(tmp_path).write_raw("laps", SESSION, records)

    assert path == tmp_path / "raw/laps/year=2024/meeting_key=1229/session_key=9158/data.json"
    assert json.loads(path.read_text(encoding="utf-8")) == records


def test_write_processed_grava_parquet_com_uniao_das_colunas(tmp_path: Path) -> None:
    when = datetime(2024, 3, 2, tzinfo=UTC)
    records = [{"a": 1, "date": when}, {"a": 2, "b": "só no segundo"}]

    path = LocalWriter(tmp_path).write_processed("laps", SESSION, records)

    assert path is not None
    table = pq.read_table(path)
    assert table.column_names == ["a", "date", "b"]
    assert table.to_pylist() == [
        {"a": 1, "date": when, "b": None},
        {"a": 2, "date": None, "b": "só no segundo"},
    ]


def test_reprocessar_sobrescreve_sem_duplicar(tmp_path: Path) -> None:
    writer = LocalWriter(tmp_path)
    records = [{"a": 1}, {"a": 2}]

    first = writer.write_processed("pit", Partition(2024), records)
    second = writer.write_processed("pit", Partition(2024), records)
    writer.write_raw("pit", Partition(2024), records)
    writer.write_raw("pit", Partition(2024), records)

    assert first == second
    assert second is not None
    assert pq.read_table(second).num_rows == 2
    files = sorted(p.name for p in tmp_path.rglob("*") if p.is_file())
    assert files == ["data.json", "data.parquet"]


def test_lista_vazia_nao_gera_arquivo(tmp_path: Path) -> None:
    writer = LocalWriter(tmp_path)
    assert writer.write_raw("laps", SESSION, []) is None
    assert writer.write_processed("laps", SESSION, []) is None
    assert not any(tmp_path.iterdir())


def test_write_processed_converte_erro_do_arrow(tmp_path: Path) -> None:
    with pytest.raises(WriteError, match="Falha ao gravar"):
        LocalWriter(tmp_path).write_processed("laps", SESSION, [{"a": 1}, {"a": "x"}])
    assert not list(tmp_path.rglob("*.tmp"))


def test_write_raw_converte_erro_de_io(tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch.object(Path, "write_text", side_effect=OSError("disco cheio"))
    with pytest.raises(WriteError):
        LocalWriter(tmp_path).write_raw("laps", SESSION, [{"a": 1}])
