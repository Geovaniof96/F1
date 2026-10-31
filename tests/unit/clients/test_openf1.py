from typing import Any
from unittest.mock import MagicMock

import pytest
import requests
from pytest_mock import MockerFixture

from f1.clients.openf1 import OpenF1Client
from f1.exceptions import OpenF1APIError


def _response(status: int, payload: Any = None) -> MagicMock:
    response = MagicMock(spec=requests.Response)
    response.status_code = status
    response.json.return_value = payload
    response.text = str(payload)
    return response


@pytest.fixture
def sleep(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("f1.clients.openf1.time.sleep")


@pytest.fixture
def session() -> MagicMock:
    return MagicMock(spec=requests.Session)


def _client(session: MagicMock, **kwargs: Any) -> OpenF1Client:
    kwargs.setdefault("min_interval", 0)
    return OpenF1Client("https://api.test/v1/", session=session, **kwargs)


def test_get_retorna_registros_e_monta_url(session: MagicMock, sleep: MagicMock) -> None:
    session.get.return_value = _response(200, [{"session_key": 1}])

    result = _client(session, timeout=5).get("sessions", {"year": 2024})

    assert result == [{"session_key": 1}]
    session.get.assert_called_once_with(
        "https://api.test/v1/sessions", params={"year": 2024}, timeout=5
    )
    sleep.assert_not_called()


@pytest.mark.parametrize("status", [429, 500, 503])
def test_get_refaz_requisicao_em_erro_transitorio(
    session: MagicMock, sleep: MagicMock, status: int
) -> None:
    session.get.side_effect = [_response(status), _response(200, [{"a": 1}])]

    result = _client(session, backoff_factor=2).get("laps")

    assert result == [{"a": 1}]
    assert session.get.call_count == 2
    sleep.assert_called_once_with(2)


def test_get_refaz_requisicao_em_timeout(session: MagicMock, sleep: MagicMock) -> None:
    session.get.side_effect = [requests.Timeout("lento"), _response(200, [])]

    assert _client(session).get("laps") == []
    assert session.get.call_count == 2


def test_get_lanca_erro_apos_max_retries(session: MagicMock, sleep: MagicMock) -> None:
    session.get.return_value = _response(500)

    with pytest.raises(OpenF1APIError, match="3 tentativas") as exc_info:
        _client(session, max_retries=2, backoff_factor=1).get("pit")

    assert session.get.call_count == 3
    assert [c.args[0] for c in sleep.call_args_list] == [1, 2]
    assert isinstance(exc_info.value.__cause__, requests.HTTPError)


def test_get_retorna_lista_vazia_em_404(session: MagicMock, sleep: MagicMock) -> None:
    session.get.return_value = _response(404, {"detail": "No results found."})

    assert _client(session).get("weather", {"meeting_key": 1}) == []
    assert session.get.call_count == 1


def test_get_nao_refaz_em_erro_do_cliente(session: MagicMock, sleep: MagicMock) -> None:
    session.get.return_value = _response(400, {"detail": "bad"})

    with pytest.raises(OpenF1APIError, match="HTTP 400"):
        _client(session).get("laps")
    assert session.get.call_count == 1


@pytest.mark.parametrize("payload", [{"detail": "x"}, "texto"])
def test_get_rejeita_resposta_que_nao_e_lista(
    session: MagicMock, sleep: MagicMock, payload: Any
) -> None:
    session.get.return_value = _response(200, payload)

    with pytest.raises(OpenF1APIError, match="inesperada"):
        _client(session).get("laps")


def test_get_rejeita_json_invalido(session: MagicMock, sleep: MagicMock) -> None:
    response = _response(200)
    response.json.side_effect = ValueError("not json")
    session.get.return_value = response

    with pytest.raises(OpenF1APIError, match="JSON"):
        _client(session).get("laps")


def test_get_respeita_intervalo_minimo(
    session: MagicMock, sleep: MagicMock, mocker: MockerFixture
) -> None:
    mocker.patch("f1.clients.openf1.time.monotonic", side_effect=[100.0, 100.2, 100.5])
    session.get.return_value = _response(200, [])
    client = _client(session, min_interval=0.5)

    client.get("a")
    client.get("b")

    sleep.assert_called_once()
    assert sleep.call_args.args[0] == pytest.approx(0.3)


def test_context_manager_fecha_sessao(session: MagicMock) -> None:
    with _client(session) as client:
        assert isinstance(client, OpenF1Client)
    session.close.assert_called_once()
