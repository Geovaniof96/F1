"""Funções de extração dos endpoints da OpenF1."""

from f1.clients.openf1 import ApiClient, Record


def fetch_meetings(client: ApiClient, year: int) -> list[Record]:
    """Busca os meetings (fins de semana de GP/teste) de um ano.

    Args:
        client: Cliente da OpenF1.
        year: Temporada.

    Returns:
        Registros de ``/meetings``.
    """
    return client.get("meetings", {"year": year})


def fetch_sessions(client: ApiClient, year: int) -> list[Record]:
    """Busca as sessões (treinos, classificação, sprint, corrida) de um ano.

    Args:
        client: Cliente da OpenF1.
        year: Temporada.

    Returns:
        Registros de ``/sessions``.
    """
    return client.get("sessions", {"year": year})


def fetch_by_session(client: ApiClient, endpoint: str, session_key: int) -> list[Record]:
    """Busca os registros de um endpoint filtrando por sessão.

    Args:
        client: Cliente da OpenF1.
        endpoint: Nome do endpoint (ex.: ``laps``).
        session_key: Identificador da sessão.

    Returns:
        Registros do endpoint para a sessão.
    """
    return client.get(endpoint, {"session_key": session_key})


def fetch_by_meeting(client: ApiClient, endpoint: str, meeting_key: int) -> list[Record]:
    """Busca os registros de um endpoint filtrando por meeting.

    Args:
        client: Cliente da OpenF1.
        endpoint: Nome do endpoint (ex.: ``weather``).
        meeting_key: Identificador do meeting.

    Returns:
        Registros do endpoint para o meeting.
    """
    return client.get(endpoint, {"meeting_key": meeting_key})
