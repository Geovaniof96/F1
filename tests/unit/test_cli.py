from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from f1.cli import extract, main, parse_args
from f1.config.settings import Settings
from f1.pipeline import DEFAULT_ENDPOINTS, RunSummary


def test_parse_args_usa_padroes() -> None:
    args = parse_args(["--year", "2024"])
    assert args.year == 2024
    assert args.endpoints == list(DEFAULT_ENDPOINTS)
    assert args.session_key is None
    assert args.log_level is None


def test_parse_args_le_endpoints_e_session_key() -> None:
    args = parse_args(["--year", "2023", "--endpoints", "laps, pit", "--session-key", "9158"])
    assert args.endpoints == ["laps", "pit"]
    assert args.session_key == 9158


@pytest.mark.parametrize(
    "argv", [[], ["--year", "x"], ["--year", "2024", "--endpoints", "car_data"]]
)
def test_parse_args_rejeita_argumentos_invalidos(argv: list[str]) -> None:
    with pytest.raises(SystemExit):
        parse_args(argv)


def test_extract_monta_cliente_e_writer_a_partir_da_configuracao(
    mocker: MockerFixture, tmp_path: Path
) -> None:
    client_cls = mocker.patch("f1.cli.OpenF1Client")
    run = mocker.patch("f1.cli.run", return_value=RunSummary())
    settings = Settings(_env_file=None, data_dir=tmp_path, min_interval_seconds=0)  # type: ignore[call-arg]

    extract(settings, 2024, ["laps"], 9158)

    assert client_cls.call_args.kwargs["min_interval"] == 0
    args, kwargs = run.call_args
    assert args[0] == 2024
    assert args[1] is client_cls.return_value.__enter__.return_value
    assert args[2].base_dir == tmp_path
    assert kwargs == {"endpoints": ["laps"], "session_key": 9158}


@pytest.mark.parametrize(("failures", "code"), [([], 0), (["laps: erro"], 1)])
def test_main_retorna_codigo_de_saida(
    mocker: MockerFixture, failures: list[str], code: int
) -> None:
    extract_mock = mocker.patch("f1.cli.extract", return_value=RunSummary(failures=failures))

    assert main(["--year", "2024", "--endpoints", "laps", "--log-level", "debug"]) == code
    assert extract_mock.call_args.args[1:] == (2024, ["laps"], None)
