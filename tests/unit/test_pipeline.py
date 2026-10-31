from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import pytest

from f1.exceptions import OpenF1APIError
from f1.load.local import LocalWriter
from f1.pipeline import SESSION_ENDPOINTS, run

EXTRACTED_AT = datetime(2026, 10, 30, tzinfo=UTC)

SESSIONS = [
    {"session_key": 10, "meeting_key": 1, "session_name": "Race"},
    {"session_key": 20, "meeting_key": 2, "session_name": "Race"},
]


def _laps(_endpoint: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    sk = params["session_key"]
    return [
        {"session_key": sk, "driver_number": 1, "lap_number": n, "lap_duration": 90 + n}
        for n in (1, 2)
    ]


def _weather(_endpoint: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"meeting_key": params["meeting_key"], "date": "2024-03-02T15:00:00+00:00"}]


@pytest.fixture
def responses() -> dict[str, Any]:
    return {
        "meetings": [{"meeting_key": 1}, {"meeting_key": 2}],
        "sessions": SESSIONS,
        "laps": _laps,
        "weather": _weather,
    }


def test_session_endpoints_exclui_os_de_ano() -> None:
    assert "meetings" not in SESSION_ENDPOINTS
    assert {"laps", "weather"} <= set(SESSION_ENDPOINTS)


def test_run_grava_todas_as_particoes(
    tmp_path: Path, fake_client_factory: Callable[..., Any], responses: dict[str, Any]
) -> None:
    client = fake_client_factory(responses)

    summary = run(
        2024,
        client,
        LocalWriter(tmp_path),
        endpoints=["meetings", "sessions", "laps", "weather"],
        extracted_at=EXTRACTED_AT,
    )

    assert summary.ok
    assert summary.partitions == 6  # meetings, sessions, 2x laps, 2x weather
    assert summary.rows == 2 + 2 + 4 + 2
    assert ("laps", {"session_key": 10}) in client.calls
    assert ("weather", {"meeting_key": 2}) in client.calls
    laps = tmp_path / "processed/laps/year=2024/meeting_key=2/session_key=20/data.parquet"
    assert pq.read_table(laps).num_rows == 2


def test_run_e_idempotente(
    tmp_path: Path, fake_client_factory: Callable[..., Any], responses: dict[str, Any]
) -> None:
    writer = LocalWriter(tmp_path)
    for _ in range(2):
        run(2024, fake_client_factory(responses), writer, endpoints=["laps"])

    files = list(tmp_path.rglob("*.*"))
    assert len(files) == 4  # 2 sessões x (json + parquet)
    assert sum(pq.read_table(f).num_rows for f in files if f.suffix == ".parquet") == 4


def test_run_filtra_session_key_sem_gravar_sessions(
    tmp_path: Path, fake_client_factory: Callable[..., Any], responses: dict[str, Any]
) -> None:
    client = fake_client_factory(responses)

    summary = run(2024, client, LocalWriter(tmp_path), endpoints=["laps"], session_key=20)

    assert summary.ok
    assert [c for c in client.calls if c[0] == "laps"] == [("laps", {"session_key": 20})]
    assert not (tmp_path / "raw/sessions").exists()


def test_run_registra_session_key_inexistente(
    tmp_path: Path, fake_client_factory: Callable[..., Any], responses: dict[str, Any]
) -> None:
    client = fake_client_factory(responses)

    summary = run(2024, client, LocalWriter(tmp_path), endpoints=["pit"], session_key=99)

    assert not summary.ok
    assert "session_key=99" in summary.failures[0]


def test_run_continua_apos_falha_de_uma_sessao(
    tmp_path: Path, fake_client_factory: Callable[..., Any], responses: dict[str, Any]
) -> None:
    def flaky(endpoint: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        if params["session_key"] == 10:
            raise OpenF1APIError("HTTP 500")
        return _laps(endpoint, params)

    responses["laps"] = flaky

    summary = run(2024, fake_client_factory(responses), LocalWriter(tmp_path), endpoints=["laps"])

    assert len(summary.failures) == 1
    assert "session_key=10" in summary.failures[0]
    assert summary.partitions == 1


def test_run_registra_registro_invalido_como_falha(
    tmp_path: Path, fake_client_factory: Callable[..., Any]
) -> None:
    client = fake_client_factory({"meetings": [{"sem_chave": 1}]})

    summary = run(2024, client, LocalWriter(tmp_path), endpoints=["meetings"])

    assert summary.failures
    assert "meetings" in summary.failures[0]
    assert not any(tmp_path.iterdir())


def test_run_registra_falha_ao_buscar_sessions(
    tmp_path: Path, fake_client_factory: Callable[..., Any]
) -> None:
    def boom(_e: str, _p: dict[str, Any]) -> list[dict[str, Any]]:
        raise OpenF1APIError("fora do ar")

    client = fake_client_factory({"sessions": boom})

    summary = run(2024, client, LocalWriter(tmp_path), endpoints=["laps"], session_key=10)

    assert len(summary.failures) == 1
    assert "fora do ar" in summary.failures[0]


def test_run_rejeita_endpoint_desconhecido(
    tmp_path: Path, fake_client_factory: Callable[..., Any]
) -> None:
    with pytest.raises(ValueError, match="Endpoint não suportado"):
        run(2024, fake_client_factory(), LocalWriter(tmp_path), endpoints=["car_data"])
