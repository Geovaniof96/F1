"""Visões do dashboard: funções puras que recebem DataFrames e devolvem tabelas ou figuras."""

import json
import math
from collections.abc import Iterable, Sequence
from typing import Any, cast

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

DEFAULT_COLOUR = "#888888"
OUTLIER_FACTOR = 1.07
"""Voltas acima de 107% da mediana são consideradas lentas (safety car, box, erros)."""

COMPOUND_COLOURS: dict[str, str] = {
    "SOFT": "#DA291C",
    "MEDIUM": "#FFD12E",
    "HARD": "#B0B0B0",
    "INTERMEDIATE": "#43B02A",
    "WET": "#0067AD",
}
PIT_DURATION_COLUMNS: tuple[str, ...] = ("stop_duration", "pit_duration", "lane_duration")
"""Colunas de duração do pit, em ordem de preferência (variam por temporada)."""


# ---------- utilitários ----------


def empty_figure(message: str = "Sem dados") -> go.Figure:
    """Figura vazia com uma mensagem centralizada.

    Args:
        message: Texto exibido.

    Returns:
        Figura sem traces, com a anotação.
    """
    fig = go.Figure()
    fig.add_annotation(text=message, showarrow=False, font={"size": 16})
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def _is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def _as_list(value: Any) -> list[Any] | None:
    """Converte listas, arrays e textos JSON de lista em ``list``; outros valores em ``None``."""
    if isinstance(value, str) and value.startswith("["):
        try:
            parsed = json.loads(value)
        except ValueError:
            return None
        return parsed if isinstance(parsed, list) else None
    if isinstance(value, Iterable) and not isinstance(value, str | bytes | dict):
        return list(value)
    return None


def format_lap_time(seconds: Any) -> str:
    """Formata segundos como ``M:SS.mmm`` (ou ``H:MM:SS.mmm``).

    Args:
        seconds: Duração em segundos.

    Returns:
        Texto formatado, ou ``"—"`` se ausente.
    """
    if _is_missing(seconds):
        return "—"
    total = float(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{int(hours)}:{int(minutes):02d}:{secs:06.3f}"
    return f"{int(minutes)}:{secs:06.3f}"


def _format_each(value: Any, single: Any) -> str:
    items = _as_list(value)
    if items is not None:
        return " / ".join(single(v) for v in items) if items else "—"
    return str(single(value))


def format_gap(value: Any) -> str:
    """Formata o ``gap_to_leader`` (número, texto como ``"+1 LAP"`` ou lista Q1/Q2/Q3).

    Args:
        value: Valor bruto do gap.

    Returns:
        Texto como ``"+1.234s"``, ``"+1 LAP"`` ou ``"+0.122s / +0.209s / +0.000s"``.
    """

    def single(v: Any) -> str:
        if _is_missing(v):
            return "—"
        try:
            return f"+{float(v):.3f}s"
        except (TypeError, ValueError):
            return str(v)

    return _format_each(value, single)


def format_duration(value: Any) -> str:
    """Formata a ``duration`` do resultado (segundos ou lista Q1/Q2/Q3).

    Args:
        value: Valor bruto da duração.

    Returns:
        Texto formatado com `format_lap_time`.
    """

    def single(v: Any) -> str:
        try:
            return format_lap_time(None if _is_missing(v) else float(v))
        except (TypeError, ValueError):
            return str(v)

    return _format_each(value, single)


def driver_info(drivers: pd.DataFrame) -> pd.DataFrame:
    """Tabela de apoio por ``driver_number``: sigla, nome, equipe e cor (``#RRGGBB``).

    Args:
        drivers: DataFrame de ``/drivers``.

    Returns:
        DataFrame indexado por ``driver_number`` com ``acronym``, ``name``, ``team`` e ``colour``.
    """
    columns = ["acronym", "name", "team", "colour"]
    if drivers.empty:
        return pd.DataFrame(columns=columns, index=pd.Index([], name="driver_number"))
    df = drivers.drop_duplicates("driver_number").set_index("driver_number")
    colour = df.get("team_colour", pd.Series(index=df.index, dtype=object))
    return pd.DataFrame(
        {
            "acronym": df.get("name_acronym", df.index.astype(str)),
            "name": df.get("full_name", df.index.astype(str)),
            "team": df.get("team_name", ""),
            "colour": [f"#{c}" if isinstance(c, str) and c else DEFAULT_COLOUR for c in colour],
        },
        index=df.index,
    )


def driver_labels(info: pd.DataFrame) -> dict[int, str]:
    """Rótulos ``"VER (Red Bull Racing)"`` por ``driver_number``, para o filtro de pilotos.

    Args:
        info: Resultado de `driver_info`.

    Returns:
        Dicionário ``{driver_number: rótulo}``.
    """
    return {
        int(n): f"{row['acronym']} ({row['team']})"
        for n, row in zip(info.index.tolist(), info.to_dict("records"), strict=True)
    }


def _field(info: pd.DataFrame, number: int, column: str, default: str = "") -> str:
    return str(info.at[number, column]) if number in info.index else default


def _label(info: pd.DataFrame, number: int) -> str:
    return _field(info, number, "acronym", str(number))


def _colour(info: pd.DataFrame, number: int) -> str:
    return _field(info, number, "colour", DEFAULT_COLOUR)


def _select(df: pd.DataFrame, selected: Sequence[int] | None) -> pd.DataFrame:
    if selected is None or df.empty or "driver_number" not in df:
        return df
    return df[df["driver_number"].isin(list(selected))]


# ---------- resultado ----------


def _status(row: pd.Series) -> str:
    for flag in ("dsq", "dns", "dnf"):
        if bool(row.get(flag)) and not _is_missing(row.get(flag)):
            return flag.upper()
    return "Classificado"


def results_table(results: pd.DataFrame, drivers: pd.DataFrame) -> pd.DataFrame:
    """Classificação da sessão pronta para exibição.

    Args:
        results: DataFrame de ``/session_result``.
        drivers: DataFrame de ``/drivers``.

    Returns:
        Colunas ``Pos``, ``Piloto``, ``Equipe``, ``Voltas``, ``Tempo``, ``Gap``,
        ``Pontos`` e ``Status``, ordenadas pela posição (sem posição ao final).
    """
    columns = ["Pos", "Piloto", "Equipe", "Voltas", "Tempo", "Gap", "Pontos", "Status"]
    if results.empty:
        return pd.DataFrame(columns=columns)
    info = driver_info(drivers)
    df = results.sort_values("position", na_position="last")
    table = pd.DataFrame(
        {
            "Pos": df["position"].astype("Int64"),
            "Piloto": [
                f"{_label(info, n)} - {_field(info, n, 'name')}" if n in info.index else str(n)
                for n in df["driver_number"]
            ],
            "Equipe": [_field(info, n, "team") for n in df["driver_number"]],
            "Voltas": df.get("number_of_laps", pd.Series(dtype="Int64")).astype("Int64"),
            "Tempo": [format_duration(v) for v in df.get("duration", [None] * len(df))],
            "Gap": [format_gap(v) for v in df.get("gap_to_leader", [None] * len(df))],
            "Pontos": df.get("points", pd.Series([None] * len(df), index=df.index)),
            "Status": [_status(row) for _, row in df.iterrows()],
        }
    )
    return table.reset_index(drop=True)


# ---------- ritmo ----------


def filter_outlier_laps(laps: pd.DataFrame, factor: float = OUTLIER_FACTOR) -> pd.DataFrame:
    """Remove voltas de saída do box e voltas acima de ``factor`` x a mediana.

    Args:
        laps: DataFrame de ``/laps``.
        factor: Limite relativo à mediana de ``lap_duration``.

    Returns:
        Voltas representativas do ritmo.
    """
    df = laps.dropna(subset=["lap_duration"])
    if df.empty:
        return df
    if "is_pit_out_lap" in df:
        df = df[~df["is_pit_out_lap"].fillna(False).astype(bool)]
    limit = df["lap_duration"].median() * factor
    return df[df["lap_duration"] <= limit]


def lap_pace(
    laps: pd.DataFrame,
    drivers: pd.DataFrame,
    selected: Sequence[int] | None = None,
    *,
    exclude_outliers: bool = True,
) -> go.Figure:
    """Tempo de volta por piloto ao longo da sessão, na cor da equipe.

    Companheiros de equipe têm a mesma cor; o segundo usa linha tracejada.

    Args:
        laps: DataFrame de ``/laps``.
        drivers: DataFrame de ``/drivers``.
        selected: Pilotos (``driver_number``) a exibir; ``None`` exibe todos.
        exclude_outliers: Aplica `filter_outlier_laps`.

    Returns:
        Figura com um trace por piloto.
    """
    if laps.empty or "lap_duration" not in laps:
        return empty_figure("Sem dados de voltas")
    df = _select(laps.dropna(subset=["lap_duration"]), selected)
    if exclude_outliers:
        df = filter_outlier_laps(df)
    if df.empty:
        return empty_figure("Sem dados de voltas")

    info = driver_info(drivers)
    fig = go.Figure()
    team_count: dict[str, int] = {}
    for key, group in df.sort_values("lap_number").groupby("driver_number", sort=True):
        number = int(cast(int, key))
        team = _field(info, number, "team") or str(number)
        team_count[team] = team_count.get(team, 0) + 1
        label = _label(info, number)
        fig.add_trace(
            go.Scatter(
                x=group["lap_number"],
                y=group["lap_duration"],
                mode="lines+markers",
                name=label,
                line={
                    "color": _colour(info, number),
                    "dash": "solid" if team_count[team] == 1 else "dash",
                },
                marker={"size": 4},
                customdata=[format_lap_time(v) for v in group["lap_duration"]],
                hovertemplate=f"{label} | volta %{{x}}: %{{customdata}}<extra></extra>",
            )
        )
    fig.update_layout(
        xaxis_title="Volta", yaxis_title="Tempo de volta (s)", hovermode="closest", height=550
    )
    return fig


# ---------- pneus ----------


def pit_duration(pit: pd.DataFrame) -> pd.Series:
    """Duração de cada pit stop, usando a primeira coluna disponível e não nula.

    Args:
        pit: DataFrame de ``/pit``.

    Returns:
        Série de durações em segundos (``NaN`` se nenhuma coluna tiver valor).
    """
    duration = pd.Series(float("nan"), index=pit.index)
    for column in PIT_DURATION_COLUMNS:
        if column in pit:
            duration = duration.fillna(pd.to_numeric(pit[column], errors="coerce"))
    return duration


def tyre_strategy(
    stints: pd.DataFrame,
    pit: pd.DataFrame,
    drivers: pd.DataFrame,
    order: Sequence[int] | None = None,
) -> go.Figure:
    """Gantt de stints por piloto, colorido pelo composto, com marcadores de pit stop.

    Args:
        stints: DataFrame de ``/stints``.
        pit: DataFrame de ``/pit``.
        drivers: DataFrame de ``/drivers``.
        order: Pilotos (``driver_number``) na ordem de exibição, de cima para baixo.
            Também filtra os pilotos exibidos. ``None`` exibe todos por número.

    Returns:
        Figura com um trace por composto e um de pit stops.
    """
    if stints.empty:
        return empty_figure("Sem dados de pneus")
    df = _select(stints.dropna(subset=["lap_start"]), order)
    if df.empty:
        return empty_figure("Sem dados de pneus")
    df = df.assign(lap_end=df["lap_end"].fillna(df["lap_start"]))
    info = driver_info(drivers)
    numbers = list(order) if order is not None else sorted(df["driver_number"].unique())
    labels = [_label(info, int(n)) for n in numbers if n in set(df["driver_number"])]

    fig = go.Figure()
    for compound, group in df.groupby(df["compound"].fillna("UNKNOWN"), sort=False):
        name = str(compound)
        fig.add_trace(
            go.Bar(
                y=[_label(info, int(n)) for n in group["driver_number"]],
                base=group["lap_start"] - 1,
                x=group["lap_end"] - group["lap_start"] + 1,
                orientation="h",
                name=name,
                marker={
                    "color": COMPOUND_COLOURS.get(name, DEFAULT_COLOUR),
                    "line": {"color": "#222222", "width": 1},
                },
                customdata=group[["lap_start", "lap_end", "stint_number"]].to_numpy(),
                hovertemplate=(
                    f"{name} | stint %{{customdata[2]}}: "
                    "voltas %{customdata[0]}-%{customdata[1]}<extra></extra>"
                ),
            )
        )

    stops = _select(pit, order)
    if not stops.empty and "lap_number" in stops:
        durations = pit_duration(stops)
        fig.add_trace(
            go.Scatter(
                x=stops["lap_number"],
                y=[_label(info, int(n)) for n in stops["driver_number"]],
                mode="markers",
                name="Pit stop",
                marker={"symbol": "line-ns-open", "size": 18, "color": "#000000"},
                customdata=[f"{d:.1f}s" if not math.isnan(d) else "—" for d in durations],
                hovertemplate="Pit na volta %{x}: %{customdata}<extra></extra>",
            )
        )

    fig.update_layout(
        barmode="overlay",
        xaxis_title="Volta",
        yaxis={"categoryorder": "array", "categoryarray": labels[::-1]},
        height=max(350, 28 * len(labels) + 120),
        legend_title_text="Composto",
    )
    return fig


# ---------- clima ----------


def rain_intervals(weather: pd.DataFrame) -> list[tuple[Any, Any]]:
    """Intervalos contínuos com chuva (``rainfall > 0``).

    Args:
        weather: DataFrame de ``/weather`` ordenado por data.

    Returns:
        Lista de pares ``(início, fim)``.
    """
    if weather.empty or "rainfall" not in weather:
        return []
    raining = weather["rainfall"].fillna(0) > 0
    intervals: list[tuple[Any, Any]] = []
    start: Any = None
    previous: Any = None
    for date, wet in zip(weather["date"], raining, strict=True):
        if wet and start is None:
            start = date
        if not wet and start is not None:
            intervals.append((start, previous))
            start = None
        previous = date
    if start is not None:
        intervals.append((start, previous))
    return intervals


def weather_chart(weather: pd.DataFrame) -> go.Figure:
    """Temperaturas do ar e da pista, umidade (eixo secundário) e faixas de chuva.

    Args:
        weather: DataFrame de ``/weather`` da sessão.

    Returns:
        Figura com eixo secundário para a umidade.
    """
    if weather.empty or "date" not in weather:
        return empty_figure("Sem dados de clima")
    df = weather.sort_values("date")
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    series = (
        ("air_temperature", "Ar (°C)", "#1f77b4", False, "solid"),
        ("track_temperature", "Pista (°C)", "#d62728", False, "solid"),
        ("humidity", "Umidade (%)", "#7f7f7f", True, "dot"),
    )
    for column, name, colour, secondary, dash in series:
        if column in df:
            fig.add_trace(
                go.Scatter(
                    x=df["date"],
                    y=df[column],
                    name=name,
                    mode="lines",
                    line={"color": colour, "dash": dash},
                ),
                secondary_y=secondary,
            )
    for start, end in rain_intervals(df):
        fig.add_vrect(x0=start, x1=end, fillcolor="#0067AD", opacity=0.15, line_width=0)
    fig.update_layout(height=450, hovermode="x unified", xaxis_title="Horário (UTC)")
    fig.update_yaxes(title_text="Temperatura (°C)", secondary_y=False)
    fig.update_yaxes(title_text="Umidade (%)", secondary_y=True)
    return fig
