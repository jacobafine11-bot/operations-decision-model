"""
charts.py — every chart in the portal, built with Altair.

Color is assigned by role, not by chart, so the same thing is always the
same color everywhere in the program:
  MODEL (blue)       what the equations predict
  SIM   (orange)     what the independent simulation measured
  REAL  (aqua)       what happened in real data
These are slots 1-3 of the validated reference palette (dataviz skill),
which pass colorblind separation checks for up to three series in any
chart form. Reference lines and bands use neutral grays. Every chart
carries tooltips, and identity never relies on color alone: series are
named in a legend and lines use distinct strokes.
"""

from __future__ import annotations

import altair as alt
import numpy as np
import pandas as pd

MODEL, SIM, REAL = "#2a78d6", "#eb6834", "#1baf7a"
INK2, BAND, GRID = "#52514e", "#d9d8d4", "#ecebe8"
ROLE_DOMAIN = ["Model", "Simulation", "Real data"]
ROLE_RANGE = [MODEL, SIM, REAL]
ROLE_DASH = [[1, 0], [6, 3], [2, 2]]


def _base(chart: alt.Chart, height: int = 300) -> alt.Chart:
    return chart.properties(height=height).configure_axis(
        gridColor=GRID, domainColor=BAND, tickColor=BAND,
        labelColor=INK2, titleColor=INK2, labelFontSize=12, titleFontSize=12,
    ).configure_legend(labelColor=INK2, titleColor=INK2, orient="top",
                       labelFontSize=12).configure_view(strokeWidth=0)


def _present(df: pd.DataFrame | None, field: str):
    """Only the roles actually drawn, in fixed order: a legend never names
    a series that isn't on the chart, and colors never shift."""
    if df is None:
        return ROLE_DOMAIN, ROLE_RANGE, ROLE_DASH
    have = set(df[field].unique())
    idx = [i for i, r in enumerate(ROLE_DOMAIN) if r in have]
    return ([ROLE_DOMAIN[i] for i in idx], [ROLE_RANGE[i] for i in idx],
            [ROLE_DASH[i] for i in idx])


def role_color(field: str = "Series", legend: bool = True, df: pd.DataFrame | None = None):
    dom, rng, _ = _present(df, field)
    return alt.Color(f"{field}:N", scale=alt.Scale(domain=dom, range=rng),
                     legend=alt.Legend(title=None) if legend else None)


def convergence(df: pd.DataFrame, theory: float, warmup_n: int, unit: str,
                margin_rel: float | None = None) -> alt.Chart:
    """Running average of a simulated quantity vs. customer index, with the
    theory line, the optional equivalence band, and the warmup shaded."""
    layers = []
    if margin_rel:
        band = pd.DataFrame({"lo": [theory * (1 - margin_rel)],
                             "hi": [theory * (1 + margin_rel)]})
        layers.append(alt.Chart(band).mark_rect(color=BAND, opacity=0.45).encode(
            y="lo:Q", y2="hi:Q",
            tooltip=[alt.Tooltip("lo:Q", format=".4g", title="band low"),
                     alt.Tooltip("hi:Q", format=".4g", title="band high")]))
    warm = pd.DataFrame({"x0": [0], "x1": [warmup_n]})
    layers.append(alt.Chart(warm).mark_rect(color=GRID, opacity=0.7).encode(
        x="x0:Q", x2="x1:Q"))
    layers.append(alt.Chart(df).mark_line(color=SIM, strokeWidth=2).encode(
        x=alt.X("customer:Q", title="Customers simulated"),
        y=alt.Y("running:Q", title=f"Running average ({unit})",
                scale=alt.Scale(zero=False)),
        tooltip=[alt.Tooltip("customer:Q", format=","),
                 alt.Tooltip("running:Q", format=".4g", title="running avg")]))
    th = pd.DataFrame({"theory": [theory], "label": ["Model"]})
    layers.append(alt.Chart(th).mark_rule(color=MODEL, strokeWidth=2).encode(
        y="theory:Q", tooltip=[alt.Tooltip("theory:Q", format=".4g", title="model")]))
    return _base(alt.layer(*layers), 280)


def running_average(x: np.ndarray, points: int = 400) -> pd.DataFrame:
    cs = np.cumsum(x) / np.arange(1, len(x) + 1)
    idx = np.unique(np.linspace(0, len(x) - 1, points).astype(int))
    return pd.DataFrame({"customer": idx + 1, "running": cs[idx]})


def batch_dots(batch_means: np.ndarray, theory: float, ci: tuple[float, float],
               margin_rel: float, unit: str) -> alt.Chart:
    """Each batch mean as a dot, the 95% CI of their average, the model
    line, and the equivalence band. This is what TOST actually judges."""
    df = pd.DataFrame({"batch": np.arange(1, len(batch_means) + 1), "mean": batch_means})
    band = pd.DataFrame({"lo": [theory * (1 - margin_rel)], "hi": [theory * (1 + margin_rel)]})
    cid = pd.DataFrame({"lo": [ci[0]], "hi": [ci[1]]})
    layers = [
        alt.Chart(band).mark_rect(color=BAND, opacity=0.45).encode(y="lo:Q", y2="hi:Q"),
        alt.Chart(cid).mark_rect(color=SIM, opacity=0.18).encode(
            y="lo:Q", y2="hi:Q",
            tooltip=[alt.Tooltip("lo:Q", format=".4g", title="CI low"),
                     alt.Tooltip("hi:Q", format=".4g", title="CI high")]),
        alt.Chart(df).mark_circle(color=SIM, size=70, opacity=0.9).encode(
            x=alt.X("batch:O", title="Batch"),
            y=alt.Y("mean:Q", title=f"Batch average ({unit})", scale=alt.Scale(zero=False)),
            tooltip=["batch:O", alt.Tooltip("mean:Q", format=".4g")]),
        alt.Chart(pd.DataFrame({"t": [theory]})).mark_rule(color=MODEL, strokeWidth=2)
        .encode(y="t:Q", tooltip=[alt.Tooltip("t:Q", format=".4g", title="model")]),
    ]
    return _base(alt.layer(*layers), 260)


def lines(df: pd.DataFrame, x: str, y: str, series: str, x_title: str, y_title: str,
          log_y: bool = False, points: bool = True, height: int = 300) -> alt.Chart:
    """Up to three named series by role (Model / Simulation / Real data)."""
    dom, _, dash = _present(df, series)
    enc = dict(
        x=alt.X(f"{x}:Q", title=x_title),
        y=alt.Y(f"{y}:Q", title=y_title,
                scale=alt.Scale(type="log") if log_y else alt.Scale(zero=False)),
        color=role_color(series, df=df),
        strokeDash=alt.StrokeDash(f"{series}:N", scale=alt.Scale(domain=dom, range=dash),
                                  legend=None),
        tooltip=[alt.Tooltip(f"{series}:N", title="series"),
                 alt.Tooltip(f"{x}:Q", format=".3g", title=x_title),
                 alt.Tooltip(f"{y}:Q", format=".4g", title=y_title)],
    )
    ch = alt.Chart(df).mark_line(strokeWidth=2).encode(**enc)
    if points:
        ch = ch + alt.Chart(df).mark_circle(size=64).encode(
            x=enc["x"], y=enc["y"], color=role_color(series, legend=False, df=df),
            tooltip=enc["tooltip"])
    return _base(ch, height)


def errorbars(df: pd.DataFrame, x: str, lo: str, hi: str, mid: str) -> alt.Chart:
    """Simulation means with 95% CI whiskers (orange), for overlay use."""
    return (alt.Chart(df).mark_rule(color=SIM, strokeWidth=2).encode(
        x=f"{x}:Q", y=f"{lo}:Q", y2=f"{hi}:Q")
        + alt.Chart(df).mark_circle(color=SIM, size=70).encode(
            x=f"{x}:Q", y=f"{mid}:Q",
            tooltip=[alt.Tooltip(f"{x}:Q", format=".3g"),
                     alt.Tooltip(f"{mid}:Q", format=".4g", title="simulated"),
                     alt.Tooltip(f"{lo}:Q", format=".4g", title="CI low"),
                     alt.Tooltip(f"{hi}:Q", format=".4g", title="CI high")]))


def finish(chart, height: int = 300):
    return _base(chart, height)


def pred_vs_obs(df: pd.DataFrame, x: str, y: str, x_title: str, y_title: str,
                tooltip_extra: list | None = None) -> alt.Chart:
    """Real observed (x) vs model predicted (y), log-log, with the y = x
    line and the ±50% band that the S2 criterion uses."""
    d = df[(df[x] > 0) & (df[y] > 0)]
    lo = float(min(d[x].min(), d[y].min()))
    hi = float(max(d[x].max(), d[y].max()))
    ref = pd.DataFrame({"v": np.geomspace(lo, hi, 50)})
    ref["lo"], ref["hi"] = ref["v"] / 1.5, ref["v"] * 1.5
    tt = [alt.Tooltip(f"{x}:Q", format=".3g", title=x_title),
          alt.Tooltip(f"{y}:Q", format=".3g", title=y_title)] + (tooltip_extra or [])
    sc = alt.Scale(type="log", domain=[lo, hi])
    return _base(
        alt.Chart(ref).mark_area(color=BAND, opacity=0.4).encode(
            x=alt.X("v:Q", scale=sc), y=alt.Y("lo:Q", scale=sc), y2="hi:Q")
        + alt.Chart(ref).mark_line(color=INK2, strokeDash=[4, 3], strokeWidth=1.5).encode(
            x=alt.X("v:Q", scale=sc), y=alt.Y("v:Q", scale=sc))
        + alt.Chart(d).mark_circle(color=REAL, size=40, opacity=0.55).encode(
            x=alt.X(f"{x}:Q", title=x_title, scale=sc),
            y=alt.Y(f"{y}:Q", title=y_title, scale=sc), tooltip=tt), 360)
