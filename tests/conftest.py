"""Fixtures compartilhadas pelos testes."""

from collections.abc import Callable, Iterator
from typing import Any

import pytest

from f1.config.settings import get_settings

Handler = Callable[[str, dict[str, Any]], list[dict[str, Any]]]


class FakeClient:
    """Cliente falso da OpenF1 que registra as chamadas e devolve respostas fixas."""

    def __init__(self, responses: dict[str, list[dict[str, Any]] | Handler] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        params = dict(params or {})
        self.calls.append((endpoint, params))
        response = self.responses.get(endpoint, [])
        if callable(response):
            return response(endpoint, params)
        return [dict(r) for r in response]


@pytest.fixture
def fake_client_factory() -> Callable[..., FakeClient]:
    """Fábrica de `FakeClient` com respostas configuráveis."""
    return FakeClient


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
