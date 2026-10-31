import logging

import pytest

from f1.utils.logging import setup_logging


@pytest.mark.parametrize(
    ("level", "expected"), [("DEBUG", logging.DEBUG), ("warning", logging.WARNING)]
)
def test_setup_logging_define_nivel_do_root(level: str, expected: int) -> None:
    setup_logging(level)
    assert logging.getLogger().level == expected


def test_setup_logging_rejeita_nivel_invalido() -> None:
    with pytest.raises(ValueError, match="inválido"):
        setup_logging("VERBOSO")
