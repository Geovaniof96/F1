from pathlib import Path

import pandas as pd

from f1.dashboard.data import (
    SessionData,
    available_years,
    dataset_version,
    filter_weather,
    labels_by_key,
    load_meetings,
    load_session_data,
    load_sessions,
    session_cached,
    session_caption,
)
from f1.load.base import Partition
from tests.unit.dashboard.conftest import MEETING, QUALI, RACE, YEAR


def test_available_years_lista_anos_com_calendario(data_dir: Path, tmp_path: Path) -> None:
    assert available_years(data_dir) == [YEAR]
    assert available_years(tmp_path / "vazio") == []


def test_load_meetings_ordena_e_remove_cancelados(data_dir: Path) -> None:
    meetings = load_meetings(data_dir, YEAR)
    assert meetings["meeting_name"].tolist() == ["Bahrain Grand Prix"]


def test_load_sessions_ordena_por_data(data_dir: Path) -> None:
    assert load_sessions(data_dir, YEAR)["session_key"].tolist() == [QUALI, RACE]


def test_loaders_retornam_vazio_sem_cache(tmp_path: Path) -> None:
    assert load_meetings(tmp_path, YEAR).empty
    assert load_sessions(tmp_path, YEAR).empty


def test_session_cached_indica_sessoes_baixadas(data_dir: Path) -> None:
    assert session_cached(data_dir, Partition(YEAR, MEETING, RACE))
    assert not session_cached(data_dir, Partition(YEAR, MEETING, QUALI))


def test_dataset_version_muda_com_o_cache(data_dir: Path, tmp_path: Path) -> None:
    assert dataset_version(data_dir) > 0
    assert dataset_version(tmp_path / "vazio") == 0.0


def test_load_session_data_le_todos_os_endpoints(data_dir: Path) -> None:
    data = load_session_data(data_dir, YEAR, MEETING, RACE)

    assert not data.empty
    assert len(data.drivers) == 3
    assert len(data.results) == 3
    assert len(data.laps) == 15
    assert len(data.stints) == 4
    assert len(data.pit) == 1
    assert data.weather["session_key"].unique().tolist() == [RACE]
    assert data.weather["date"].is_monotonic_increasing


def test_load_session_data_de_sessao_nao_baixada_e_vazio(data_dir: Path) -> None:
    data = load_session_data(data_dir, YEAR, MEETING, QUALI)
    assert data.drivers.empty
    assert data.laps.empty
    assert len(data.weather) == 1  # o clima é do meeting, filtrado para a sessão


def test_session_data_vazio_por_padrao() -> None:
    assert SessionData().empty


def test_filter_weather_usa_janela_sem_session_key() -> None:
    weather = pd.DataFrame(
        {"date": pd.to_datetime(["2024-03-02 14:00", "2024-03-02 15:30", "2024-03-02 18:00"])}
    )
    session = pd.Series(
        {"session_key": 1, "date_start": pd.Timestamp("2024-03-02 15:00"),
         "date_end": pd.Timestamp("2024-03-02 17:00")}
    )  # fmt: skip

    assert filter_weather(weather, session)["date"].tolist() == [pd.Timestamp("2024-03-02 15:30")]
    assert filter_weather(weather, None) is weather


def test_labels_by_key_preserva_ordem(data_dir: Path) -> None:
    sessions = load_sessions(data_dir, YEAR)
    assert labels_by_key(sessions, "session_key", "session_name") == {
        QUALI: "Qualifying",
        RACE: "Race",
    }


def test_session_caption_monta_local_e_horario(data_dir: Path) -> None:
    caption = session_caption(
        load_meetings(data_dir, YEAR), load_sessions(data_dir, YEAR), MEETING, RACE
    )
    assert caption == "Sakhir, Bahrain · 02/03/2024 15:00 UTC"


def test_session_caption_tolera_dados_ausentes() -> None:
    meetings = pd.DataFrame({"meeting_key": []})
    sessions = pd.DataFrame({"session_key": []})
    assert session_caption(meetings, sessions, 1, 1) == ""
