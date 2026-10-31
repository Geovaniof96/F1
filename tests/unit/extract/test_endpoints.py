import pytest

from f1.extract.endpoints import ENDPOINTS, Scope, get_spec


def test_registro_contem_os_oito_endpoints() -> None:
    assert set(ENDPOINTS) == {
        "meetings",
        "sessions",
        "drivers",
        "laps",
        "session_result",
        "pit",
        "stints",
        "weather",
    }


@pytest.mark.parametrize(
    ("name", "scope", "keys"),
    [
        ("meetings", Scope.YEAR, ("meeting_key",)),
        ("laps", Scope.SESSION, ("session_key", "driver_number", "lap_number")),
        ("weather", Scope.MEETING, ("meeting_key", "date")),
    ],
)
def test_get_spec_retorna_escopo_e_chaves(name: str, scope: Scope, keys: tuple[str, ...]) -> None:
    spec = get_spec(name)
    assert spec.scope is scope
    assert spec.primary_keys == keys


def test_get_spec_rejeita_endpoint_desconhecido() -> None:
    with pytest.raises(ValueError, match="car_data"):
        get_spec("car_data")


def test_registro_e_somente_leitura() -> None:
    with pytest.raises(TypeError):
        ENDPOINTS["x"] = get_spec("laps")  # type: ignore[index]
