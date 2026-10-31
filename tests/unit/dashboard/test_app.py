from pathlib import Path

import pytest
from pytest_mock import MockerFixture
from streamlit.testing.v1 import AppTest

from f1.dashboard.__main__ import APP_PATH
from f1.pipeline import RunSummary
from tests.unit.dashboard.conftest import QUALI, RACE

TIMEOUT = 30


def _app(monkeypatch: pytest.MonkeyPatch, data_dir: Path) -> AppTest:
    monkeypatch.setenv("F1_DATA_DIR", str(data_dir))
    return AppTest.from_file(str(APP_PATH), default_timeout=TIMEOUT)


def test_app_renderiza_as_quatro_abas_da_corrida(
    monkeypatch: pytest.MonkeyPatch, data_dir: Path
) -> None:
    at = _app(monkeypatch, data_dir).run()

    assert not at.exception
    assert at.sidebar.selectbox[0].value == 2024  # abre no ano em cache
    assert at.sidebar.selectbox[2].value == RACE  # última sessão do GP
    assert at.title[0].value == "Bahrain Grand Prix — Race"
    assert [t.label for t in at.tabs] == ["Resultado", "Ritmo", "Pneus", "Clima"]
    assert len(at.dataframe) == 1
    assert at.sidebar.multiselect[0].value == [1, 11, 16]


def test_app_desmarcar_toggle_e_pilotos_nao_quebra(
    monkeypatch: pytest.MonkeyPatch, data_dir: Path
) -> None:
    at = _app(monkeypatch, data_dir).run()
    at.sidebar.multiselect[0].set_value([16])
    at.toggle[0].set_value(False)
    at.run()
    assert not at.exception


def test_app_oferece_download_de_sessao_fora_do_cache(
    monkeypatch: pytest.MonkeyPatch, data_dir: Path, mocker: MockerFixture
) -> None:
    extract = mocker.patch("f1.cli.extract", return_value=RunSummary(failures=["laps: HTTP 500"]))
    at = _app(monkeypatch, data_dir).run()
    at.sidebar.selectbox[2].set_value(QUALI).run()

    assert "não estão no cache" in at.info[0].value
    at.button[0].click().run()

    assert extract.call_args.args[1] == 2024
    assert extract.call_args.args[3] == QUALI
    assert "laps: HTTP 500" in at.error[0].value


def test_app_sem_calendario_oferece_download(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mocker: MockerFixture
) -> None:
    extract = mocker.patch("f1.cli.extract", return_value=RunSummary(failures=["x"]))
    at = _app(monkeypatch, tmp_path).run()

    assert "calendário" in at.info[0].value
    at.button[0].click().run()
    assert list(extract.call_args.args[2]) == ["meetings", "sessions"]


def test_entrypoint_executa_streamlit_run(mocker: MockerFixture) -> None:
    from f1.dashboard import __main__ as entry  # noqa: PLC0415 - import local para o mock

    st_main = mocker.patch.object(entry.stcli, "main")
    mocker.patch.object(entry.sys, "argv", ["f1-dashboard", "--server.port", "8502"])

    entry.main()

    st_main.assert_called_once()
    assert entry.sys.argv == ["streamlit", "run", str(APP_PATH), "--server.port", "8502"]
