"""App Streamlit do dashboard (só layout e orquestração).

Execute com ``poetry run task dashboard`` (ou ``f1-dashboard``).
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from f1.cli import extract
from f1.config.settings import Settings, get_settings
from f1.dashboard import charts
from f1.dashboard.data import (
    SessionData,
    available_years,
    dataset_version,
    labels_by_key,
    load_meetings,
    load_session_data,
    load_sessions,
    session_cached,
    session_caption,
)
from f1.load.base import Partition
from f1.pipeline import CALENDAR_ENDPOINTS, SESSION_ENDPOINTS

FIRST_YEAR = 2023
"""Primeira temporada com dados históricos abertos na OpenF1."""


@st.cache_data(show_spinner=False)
def _meetings(data_dir: str, year: int, version: float) -> pd.DataFrame:
    return load_meetings(Path(data_dir), year)


@st.cache_data(show_spinner=False)
def _sessions(data_dir: str, year: int, version: float) -> pd.DataFrame:
    return load_sessions(Path(data_dir), year)


@st.cache_data(show_spinner=False)
def _session_data(
    data_dir: str, year: int, meeting_key: int, session_key: int, version: float
) -> SessionData:
    return load_session_data(Path(data_dir), year, meeting_key, session_key)


def _download(
    settings: Settings,
    label: str,
    year: int,
    endpoints: Sequence[str],
    session_key: int | None = None,
) -> None:
    """Executa o pipeline a partir de um botão e recarrega a página se der certo."""
    with st.spinner(f"Baixando {label} da OpenF1..."):
        summary = extract(settings, year, endpoints, session_key)
    if summary.ok:
        st.rerun()
    st.error("Falhas no download:\n\n" + "\n".join(f"- {f}" for f in summary.failures))


def _sidebar_year(data_dir: Path) -> int:
    """Seletor de temporada; abre no ano mais recente já presente no cache."""
    years = list(range(datetime.now(UTC).year, FIRST_YEAR - 1, -1))
    cached = [y for y in available_years(data_dir) if y in years]
    index = years.index(cached[0]) if cached else 0
    return int(st.sidebar.selectbox("Temporada", years, index=index))


def main() -> None:
    """Monta a página: filtros na barra lateral e quatro abas de visões."""
    st.set_page_config(page_title="F1 Dashboard", layout="wide")
    settings = get_settings()
    data_dir = str(settings.data_dir)
    version = dataset_version(settings.data_dir)

    st.sidebar.title("F1 Dashboard")
    year = _sidebar_year(settings.data_dir)
    meetings = _meetings(data_dir, year, version)
    sessions = _sessions(data_dir, year, version)
    if meetings.empty or sessions.empty:
        st.info(f"O calendário de {year} ainda não está no cache local.")
        if st.button(f"Baixar calendário de {year}", type="primary"):
            _download(settings, "o calendário", year, CALENDAR_ENDPOINTS)
        return

    meeting_names = labels_by_key(meetings, "meeting_key", "meeting_name")
    meeting_key = st.sidebar.selectbox(
        "Grande Prêmio", list(meeting_names), format_func=lambda k: meeting_names[k]
    )
    meeting_sessions = sessions[sessions["meeting_key"] == meeting_key]
    if meeting_key is None or meeting_sessions.empty:
        st.warning("Nenhuma sessão encontrada para este Grande Prêmio.")
        return
    session_names = labels_by_key(meeting_sessions, "session_key", "session_name")
    session_key = st.sidebar.selectbox(
        "Sessão",
        list(session_names),
        index=len(session_names) - 1,
        format_func=lambda k: session_names[k],
    )
    if session_key is None:
        return

    st.title(f"{meeting_names[meeting_key]} — {session_names[session_key]}")
    st.caption(session_caption(meetings, sessions, meeting_key, session_key))

    partition = Partition(year, meeting_key, session_key)
    if not session_cached(settings.data_dir, partition):
        st.info("Os dados desta sessão ainda não estão no cache local.")
        if st.button("Baixar dados da sessão", type="primary"):
            _download(settings, "os dados da sessão", year, SESSION_ENDPOINTS, session_key)
        return

    data = _session_data(data_dir, year, meeting_key, session_key, version)
    info = charts.driver_info(data.drivers)
    labels = charts.driver_labels(info)
    selected = st.sidebar.multiselect(
        "Pilotos", list(labels), default=list(labels), format_func=lambda n: labels[n]
    )
    ranking = (
        info.index.tolist()
        if data.results.empty
        else data.results.sort_values("position")["driver_number"].tolist()
    )
    order = [n for n in ranking if n in selected]

    tab_result, tab_pace, tab_tyres, tab_weather = st.tabs(["Resultado", "Ritmo", "Pneus", "Clima"])
    with tab_result:
        table = charts.results_table(data.results, data.drivers)
        if table.empty:
            st.info("Sem resultado para esta sessão.")
        else:
            st.dataframe(table, hide_index=True)
    with tab_pace:
        exclude = st.toggle("Excluir voltas de box e lentas (> 107% da mediana)", value=True)
        st.plotly_chart(
            charts.lap_pace(data.laps, data.drivers, selected, exclude_outliers=exclude)
        )
    with tab_tyres:
        st.plotly_chart(charts.tyre_strategy(data.stints, data.pit, data.drivers, order))
    with tab_weather:
        st.plotly_chart(charts.weather_chart(data.weather))


if __name__ == "__main__":
    main()
