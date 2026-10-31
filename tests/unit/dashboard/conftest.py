"""Cache de exemplo para os testes do dashboard, gerado pelo próprio pipeline."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from f1.load.local import LocalWriter
from f1.pipeline import CALENDAR_ENDPOINTS, SESSION_ENDPOINTS, run

YEAR = 2024
MEETING = 1
QUALI = 10
RACE = 11

DRIVERS = [
    (1, "VER", "Max VERSTAPPEN", "Red Bull Racing", "3671C6"),
    (11, "PER", "Sergio PEREZ", "Red Bull Racing", "3671C6"),
    (16, "LEC", "Charles LECLERC", "Ferrari", "E8002D"),
]


def _drivers(_e: str, p: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "session_key": p["session_key"],
            "meeting_key": MEETING,
            "driver_number": n,
            "name_acronym": acr,
            "full_name": name,
            "team_name": team,
            "team_colour": colour,
        }
        for n, acr, name, team, colour in DRIVERS
    ]


def _results(_e: str, p: dict[str, Any]) -> list[dict[str, Any]]:
    base = {"session_key": p["session_key"], "meeting_key": MEETING, "dsq": False, "dns": False}
    return [
        {**base, "position": 2, "driver_number": 11, "number_of_laps": 5, "dnf": False,
         "duration": 480.5, "gap_to_leader": 2.5, "points": 18.0},
        {**base, "position": 1, "driver_number": 1, "number_of_laps": 5, "dnf": False,
         "duration": 478.0, "gap_to_leader": 0, "points": 25.0},
        {**base, "position": 3, "driver_number": 16, "number_of_laps": 4, "dnf": True,
         "duration": None, "gap_to_leader": "+1 LAP", "points": 0.0},
    ]  # fmt: skip


def _laps(_e: str, p: dict[str, Any]) -> list[dict[str, Any]]:
    laps = []
    for n, *_ in DRIVERS:
        for lap in range(1, 6):
            duration = 120.0 if lap == 1 else 95.0 + lap / 10 + n / 100
            laps.append(
                {
                    "session_key": p["session_key"],
                    "meeting_key": MEETING,
                    "driver_number": n,
                    "lap_number": lap,
                    "lap_duration": duration,
                    "is_pit_out_lap": lap == 4 and n == 1,
                }
            )
    return laps


def _stints(_e: str, p: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        (1, 1, 1, 3, "SOFT"),
        (1, 2, 4, 5, "HARD"),
        (11, 1, 1, 5, "MEDIUM"),
        (16, 1, 1, 4, "HARD"),
    ]
    return [
        {
            "session_key": p["session_key"],
            "meeting_key": MEETING,
            "driver_number": n,
            "stint_number": s,
            "lap_start": a,
            "lap_end": b,
            "compound": c,
        }
        for n, s, a, b, c in rows
    ]


def _pit(_e: str, p: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "session_key": p["session_key"],
            "meeting_key": MEETING,
            "driver_number": 1,
            "lap_number": 3,
            "stop_duration": None,
            "pit_duration": 23.1,
            "date": "2024-03-02T15:20:00+00:00",
        }
    ]


def _weather(_e: str, p: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        (QUALI, "2024-03-01T16:00:00+00:00", 0),
        (RACE, "2024-03-02T15:00:00+00:00", 0),
        (RACE, "2024-03-02T15:01:00+00:00", 1),
        (RACE, "2024-03-02T15:02:00+00:00", 1),
        (RACE, "2024-03-02T15:03:00+00:00", 0),
    ]
    return [
        {
            "meeting_key": p["meeting_key"],
            "session_key": sk,
            "date": date,
            "air_temperature": 20.0 + i,
            "track_temperature": 30.0 + i,
            "humidity": 50.0,
            "rainfall": rain,
        }
        for i, (sk, date, rain) in enumerate(rows)
    ]


RESPONSES: dict[str, Any] = {
    "meetings": [
        {
            "meeting_key": MEETING,
            "meeting_name": "Bahrain Grand Prix",
            "circuit_short_name": "Sakhir",
            "country_name": "Bahrain",
            "date_start": "2024-02-29T11:30:00+00:00",
            "is_cancelled": False,
        },
        {
            "meeting_key": 2,
            "meeting_name": "GP Cancelado",
            "date_start": "2024-01-01T00:00:00+00:00",
            "is_cancelled": True,
        },
    ],
    "sessions": [
        {
            "session_key": RACE,
            "meeting_key": MEETING,
            "session_name": "Race",
            "date_start": "2024-03-02T15:00:00+00:00",
            "date_end": "2024-03-02T17:00:00+00:00",
        },
        {
            "session_key": QUALI,
            "meeting_key": MEETING,
            "session_name": "Qualifying",
            "date_start": "2024-03-01T16:00:00+00:00",
            "date_end": "2024-03-01T17:00:00+00:00",
        },
    ],
    "drivers": _drivers,
    "session_result": _results,
    "laps": _laps,
    "stints": _stints,
    "pit": _pit,
    "weather": _weather,
}


@pytest.fixture
def data_dir(tmp_path: Path, fake_client_factory: Callable[..., Any]) -> Path:
    """Cache com o calendário de 2024 e só a corrida (sessão 11) baixada."""
    writer = LocalWriter(tmp_path)
    client = fake_client_factory(RESPONSES)
    assert run(YEAR, client, writer, endpoints=CALENDAR_ENDPOINTS).ok
    assert run(YEAR, client, writer, endpoints=SESSION_ENDPOINTS, session_key=RACE).ok
    return tmp_path
