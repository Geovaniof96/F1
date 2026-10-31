from pathlib import Path

import pytest

from f1.config.settings import Settings, get_settings


def test_settings_usa_valores_padrao(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("F1_API_BASE_URL", "F1_DATA_DIR", "F1_MAX_RETRIES", "F1_LOG_LEVEL"):
        monkeypatch.delenv(var, raising=False)
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.api_base_url == "https://api.openf1.org/v1"
    assert settings.data_dir == Path("data")
    assert settings.max_retries == 3
    assert settings.min_interval_seconds == 0.5
    assert settings.log_level == "INFO"


def test_settings_le_variaveis_com_prefixo_f1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("F1_DATA_DIR", "/srv/outro")
    monkeypatch.setenv("F1_MAX_RETRIES", "7")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.data_dir == Path("/srv/outro")
    assert settings.max_retries == 7


def test_get_settings_retorna_instancia_unica() -> None:
    assert get_settings() is get_settings()
