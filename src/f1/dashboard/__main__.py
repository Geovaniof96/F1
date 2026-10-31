"""Entrypoint ``f1-dashboard``: inicia o Streamlit com o app do dashboard."""

import sys
from pathlib import Path

from streamlit.web import cli as stcli

APP_PATH = Path(__file__).with_name("app.py")


def main() -> None:
    """Executa ``streamlit run`` no `app.py`, repassando argumentos extras.

    Example:
        ``poetry run f1-dashboard --server.port 8502``
    """
    sys.argv = ["streamlit", "run", str(APP_PATH), *sys.argv[1:]]
    stcli.main()


if __name__ == "__main__":
    main()
