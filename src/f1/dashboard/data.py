"""Leitura do cache local (Parquet) para o dashboard.

Não depende do Streamlit: as funções recebem o diretório de dados e devolvem
DataFrames do pandas, o que permite testá-las com ``tmp_path``.
"""

import logging
from dataclasses import dataclass, field, fields
from pathlib import Path

import pandas as pd

from f1.load.base import Partition
from f1.load.local import PROCESSED_FILE, LocalWriter

logger = logging.getLogger(__name__)

SESSION_MARKERS: tuple[str, ...] = ("drivers", "laps", "session_result", "stints")
"""Endpoints cuja presença indica que a sessão já foi baixada."""


@dataclass(frozen=True)
class SessionData:
    """DataFrames de uma sessão. Endpoint ausente no cache vira DataFrame vazio.

    Attributes:
        drivers: Pilotos da sessão (``/drivers``).
        results: Classificação final (``/session_result``).
        laps: Voltas (``/laps``).
        stints: Stints de pneus (``/stints``).
        pit: Pit stops (``/pit``).
        weather: Clima durante a sessão (``/weather``).
    """

    drivers: pd.DataFrame = field(default_factory=pd.DataFrame)
    results: pd.DataFrame = field(default_factory=pd.DataFrame)
    laps: pd.DataFrame = field(default_factory=pd.DataFrame)
    stints: pd.DataFrame = field(default_factory=pd.DataFrame)
    pit: pd.DataFrame = field(default_factory=pd.DataFrame)
    weather: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def empty(self) -> bool:
        """``True`` se nenhum endpoint da sessão tiver dados."""
        return all(getattr(self, f.name).empty for f in fields(self))


def _path(data_dir: Path, endpoint: str, partition: Partition) -> Path:
    return LocalWriter(data_dir).path_for("processed", endpoint, partition, PROCESSED_FILE)


def _read(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def available_years(data_dir: Path) -> list[int]:
    """Lista as temporadas cujo calendário (``sessions``) está no cache.

    Args:
        data_dir: Diretório raiz dos dados.

    Returns:
        Anos em ordem decrescente.
    """
    base = Path(data_dir) / "processed" / "sessions"
    years = {
        int(p.parent.name.removeprefix("year="))
        for p in base.glob(f"year=*/{PROCESSED_FILE}")
        if p.parent.name.removeprefix("year=").isdigit()
    }
    return sorted(years, reverse=True)


def load_meetings(data_dir: Path, year: int) -> pd.DataFrame:
    """Lê os meetings de uma temporada, ordenados por data, sem os cancelados.

    Args:
        data_dir: Diretório raiz dos dados.
        year: Temporada.

    Returns:
        DataFrame de ``/meetings`` (vazio se não estiver no cache).
    """
    df = _read(_path(data_dir, "meetings", Partition(year)))
    if df.empty:
        return df
    if "is_cancelled" in df:
        df = df[~df["is_cancelled"].fillna(False).astype(bool)]
    return df.sort_values("date_start").reset_index(drop=True)


def load_sessions(data_dir: Path, year: int) -> pd.DataFrame:
    """Lê as sessões de uma temporada, ordenadas por data.

    Args:
        data_dir: Diretório raiz dos dados.
        year: Temporada.

    Returns:
        DataFrame de ``/sessions`` (vazio se não estiver no cache).
    """
    df = _read(_path(data_dir, "sessions", Partition(year)))
    if df.empty:
        return df
    return df.sort_values("date_start").reset_index(drop=True)


def session_cached(data_dir: Path, partition: Partition) -> bool:
    """Indica se os dados de uma sessão já foram baixados.

    Args:
        data_dir: Diretório raiz dos dados.
        partition: Partição da sessão (ano, meeting e sessão).

    Returns:
        ``True`` se algum endpoint de `SESSION_MARKERS` estiver no cache.
    """
    return any(_path(data_dir, e, partition).exists() for e in SESSION_MARKERS)


def dataset_version(data_dir: Path) -> float:
    """Retorna o maior mtime dos Parquet do cache, usado como chave de cache da UI.

    Args:
        data_dir: Diretório raiz dos dados.

    Returns:
        Timestamp do arquivo mais recente, ou ``0.0`` se não houver dados.
    """
    files = (Path(data_dir) / "processed").rglob(PROCESSED_FILE)
    return max((p.stat().st_mtime for p in files), default=0.0)


def filter_weather(weather: pd.DataFrame, session: pd.Series | None) -> pd.DataFrame:
    """Restringe o clima do meeting à sessão escolhida.

    Usa ``session_key`` quando a coluna existe; senão, a janela
    ``date_start``/``date_end`` da sessão.

    Args:
        weather: Clima do meeting inteiro.
        session: Linha da sessão (de `load_sessions`), ou ``None``.

    Returns:
        Clima da sessão, ordenado por data.
    """
    if weather.empty or session is None:
        return weather
    if "session_key" in weather and weather["session_key"].notna().any():
        mask = weather["session_key"] == session["session_key"]
    else:
        mask = (weather["date"] >= session["date_start"]) & (weather["date"] <= session["date_end"])
    filtered: pd.DataFrame = weather.loc[mask].sort_values("date").reset_index(drop=True)
    return filtered


def labels_by_key(df: pd.DataFrame, key: str, label: str) -> dict[int, str]:
    """Mapeia a chave de cada linha para um rótulo, preservando a ordem (para os filtros).

    Args:
        df: DataFrame de origem (ex.: meetings ou sessões).
        key: Coluna com a chave inteira (ex.: ``meeting_key``).
        label: Coluna com o texto exibido (ex.: ``meeting_name``).

    Returns:
        Dicionário ``{chave: rótulo}``.
    """
    return {int(k): str(v) for k, v in zip(df[key].tolist(), df[label].tolist(), strict=True)}


def session_caption(
    meetings: pd.DataFrame, sessions: pd.DataFrame, meeting_key: int, session_key: int
) -> str:
    """Monta a legenda da sessão: circuito, país e horário de início (UTC).

    Args:
        meetings: DataFrame de `load_meetings`.
        sessions: DataFrame de `load_sessions`.
        meeting_key: Meeting escolhido.
        session_key: Sessão escolhida.

    Returns:
        Texto como ``"Sakhir, Bahrain · 02/03/2024 15:00 UTC"``.
    """
    meeting = meetings[meetings["meeting_key"] == meeting_key].to_dict("records")
    session = sessions[sessions["session_key"] == session_key].to_dict("records")
    place = ", ".join(
        str(meeting[0][c])
        for c in ("circuit_short_name", "country_name")
        if meeting and meeting[0].get(c)
    )
    start = session[0].get("date_start") if session else None
    when = f"{pd.Timestamp(start):%d/%m/%Y %H:%M} UTC" if start is not None else ""
    return " · ".join(part for part in (place, when) if part)


def load_session_data(data_dir: Path, year: int, meeting_key: int, session_key: int) -> SessionData:
    """Lê todos os endpoints de uma sessão a partir do cache.

    Args:
        data_dir: Diretório raiz dos dados.
        year: Temporada.
        meeting_key: Meeting da sessão.
        session_key: Sessão.

    Returns:
        `SessionData` com um DataFrame por endpoint.
    """
    session_part = Partition(year, meeting_key, session_key)
    sessions = load_sessions(data_dir, year)
    match = sessions[sessions["session_key"] == session_key] if not sessions.empty else sessions
    session = match.iloc[0] if not match.empty else None
    weather = _read(_path(data_dir, "weather", Partition(year, meeting_key=meeting_key)))
    data = SessionData(
        drivers=_read(_path(data_dir, "drivers", session_part)),
        results=_read(_path(data_dir, "session_result", session_part)),
        laps=_read(_path(data_dir, "laps", session_part)),
        stints=_read(_path(data_dir, "stints", session_part)),
        pit=_read(_path(data_dir, "pit", session_part)),
        weather=filter_weather(weather, session),
    )
    logger.debug("Sessão %s carregada do cache (vazia=%s)", session_key, data.empty)
    return data
