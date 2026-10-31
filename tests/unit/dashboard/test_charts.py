from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from f1.dashboard import charts
from f1.dashboard.data import SessionData, load_session_data
from tests.unit.dashboard.conftest import MEETING, RACE, YEAR


@pytest.fixture
def race(data_dir: Path) -> SessionData:
    return load_session_data(data_dir, YEAR, MEETING, RACE)


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(89.179, "1:29.179"), (5504.742, "1:31:44.742"), (None, "—"), (float("nan"), "—")],
)
def test_format_lap_time(seconds: Any, expected: str) -> None:
    assert charts.format_lap_time(seconds) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (2.5, "+2.500s"),
        ("22.457", "+22.457s"),
        ("+1 LAP", "+1 LAP"),
        (None, "—"),
        ([0.122, None, 0.0], "+0.122s / — / +0.000s"),
        (np.array([0.1, 0.2]), "+0.100s / +0.200s"),
        ("[0.5, null]", "+0.500s / —"),
        ([], "—"),
    ],
)
def test_format_gap(value: Any, expected: str) -> None:
    assert charts.format_gap(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(90.031, "1:30.031"), ([90.031, 89.374], "1:30.031 / 1:29.374"), ("DNF", "DNF")],
)
def test_format_duration(value: Any, expected: str) -> None:
    assert charts.format_duration(value) == expected


def test_driver_info_monta_cor_hex_com_fallback() -> None:
    drivers = pd.DataFrame(
        {"driver_number": [1, 2], "name_acronym": ["VER", "XXX"], "team_colour": ["3671C6", None]}
    )
    info = charts.driver_info(drivers)
    assert info.loc[1, "colour"] == "#3671C6"
    assert info.loc[2, "colour"] == charts.DEFAULT_COLOUR
    assert charts.driver_info(pd.DataFrame()).empty


def test_driver_labels(race: SessionData) -> None:
    labels = charts.driver_labels(charts.driver_info(race.drivers))
    assert labels[16] == "LEC (Ferrari)"


def test_results_table_ordena_e_formata(race: SessionData) -> None:
    table = charts.results_table(race.results, race.drivers)

    assert table["Pos"].tolist() == [1, 2, 3]
    assert table["Piloto"].tolist()[0] == "VER - Max VERSTAPPEN"
    assert table["Gap"].tolist() == ["+0.000s", "+2.500s", "+1 LAP"]
    assert table["Tempo"].tolist()[2] == "—"
    assert table["Status"].tolist() == ["Classificado", "Classificado", "DNF"]


def test_results_table_vazia() -> None:
    assert charts.results_table(pd.DataFrame(), pd.DataFrame()).empty


def test_filter_outlier_laps_remove_box_e_voltas_lentas(race: SessionData) -> None:
    laps = charts.filter_outlier_laps(race.laps)
    assert 1 not in laps["lap_number"].tolist()  # 120s > 107% da mediana
    assert not ((laps["driver_number"] == 1) & (laps["lap_number"] == 4)).any()  # saída do box
    assert len(laps) == 15 - 3 - 1


def test_lap_pace_um_trace_por_piloto_com_cor_da_equipe(race: SessionData) -> None:
    fig = charts.lap_pace(race.laps, race.drivers)

    by_name = {t.name: t for t in fig.data}
    assert set(by_name) == {"VER", "PER", "LEC"}
    assert by_name["VER"].line.color == "#3671C6"
    assert by_name["VER"].line.dash == "solid"
    assert by_name["PER"].line.dash == "dash"  # companheiro de equipe


def test_lap_pace_filtra_pilotos_e_mantem_outliers_se_pedido(race: SessionData) -> None:
    fig = charts.lap_pace(race.laps, race.drivers, [16], exclude_outliers=False)
    assert [t.name for t in fig.data] == ["LEC"]
    assert len(fig.data[0].x) == 5


@pytest.mark.parametrize(
    "build",
    [
        lambda: charts.lap_pace(pd.DataFrame(), pd.DataFrame()),
        lambda: charts.tyre_strategy(pd.DataFrame(), pd.DataFrame(), pd.DataFrame()),
        lambda: charts.weather_chart(pd.DataFrame()),
    ],
)
def test_entradas_vazias_geram_figura_com_mensagem(build: Any) -> None:
    fig = build()
    assert len(fig.data) == 0
    assert fig.layout.annotations[0].text.startswith("Sem dados")


def test_pit_duration_usa_primeira_coluna_disponivel() -> None:
    pit = pd.DataFrame({"stop_duration": [2.4, None, None], "pit_duration": [None, 23.1, None]})
    result = charts.pit_duration(pit).tolist()
    assert result[:2] == [2.4, 23.1]
    assert np.isnan(result[2])


def test_tyre_strategy_agrupa_por_composto_e_marca_pits(race: SessionData) -> None:
    fig = charts.tyre_strategy(race.stints, race.pit, race.drivers, order=[1, 11, 16])

    bars = {t.name: t for t in fig.data if t.type == "bar"}
    assert set(bars) == {"SOFT", "HARD", "MEDIUM"}
    assert bars["SOFT"].marker.color == charts.COMPOUND_COLOURS["SOFT"]
    pit = next(t for t in fig.data if t.name == "Pit stop")
    assert list(pit.customdata) == ["23.1s"]
    assert list(fig.layout.yaxis.categoryarray) == ["LEC", "PER", "VER"]


def test_tyre_strategy_respeita_selecao(race: SessionData) -> None:
    fig = charts.tyre_strategy(race.stints, race.pit, race.drivers, order=[16])
    assert [t.name for t in fig.data] == ["HARD"]


def test_rain_intervals_agrupa_periodos_continuos(race: SessionData) -> None:
    intervals = charts.rain_intervals(race.weather)
    assert intervals == [(race.weather["date"][1], race.weather["date"][2])]
    assert charts.rain_intervals(pd.DataFrame()) == []


def test_rain_intervals_fecha_chuva_ate_o_fim() -> None:
    weather = pd.DataFrame({"date": [1, 2, 3], "rainfall": [0, 1, 1]})
    assert charts.rain_intervals(weather) == [(2, 3)]


def test_weather_chart_tem_temperaturas_umidade_e_chuva(race: SessionData) -> None:
    fig = charts.weather_chart(race.weather)
    assert [t.name for t in fig.data] == ["Ar (°C)", "Pista (°C)", "Umidade (%)"]
    assert len(fig.layout.shapes) == 1
