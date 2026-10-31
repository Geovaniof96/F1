from collections.abc import Callable
from typing import Any

from f1.extract.openf1 import fetch_by_meeting, fetch_by_session, fetch_meetings, fetch_sessions


def test_fetch_meetings_filtra_por_ano(fake_client_factory: Callable[..., Any]) -> None:
    client = fake_client_factory({"meetings": [{"meeting_key": 1}]})
    assert fetch_meetings(client, 2024) == [{"meeting_key": 1}]
    assert client.calls == [("meetings", {"year": 2024})]


def test_fetch_sessions_filtra_por_ano(fake_client_factory: Callable[..., Any]) -> None:
    client = fake_client_factory()
    assert fetch_sessions(client, 2023) == []
    assert client.calls == [("sessions", {"year": 2023})]


def test_fetch_by_session_envia_session_key(fake_client_factory: Callable[..., Any]) -> None:
    client = fake_client_factory({"laps": [{"lap_number": 1}]})
    assert fetch_by_session(client, "laps", 9158) == [{"lap_number": 1}]
    assert client.calls == [("laps", {"session_key": 9158})]


def test_fetch_by_meeting_envia_meeting_key(fake_client_factory: Callable[..., Any]) -> None:
    client = fake_client_factory()
    fetch_by_meeting(client, "weather", 1229)
    assert client.calls == [("weather", {"meeting_key": 1229})]
