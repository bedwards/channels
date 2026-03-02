"""
Chart Builder — Renders charts from polars DataFrames using Altair and Plotly.

The builder applies themes, creates publication-quality charts, and exports
to PNG/SVG for embedding in Substack essays.

Usage:
    builder = ChartBuilder(theme="material_record")
    chart = builder.line(df, x="year", y="value", title="GDP Over Time")
    builder.save(chart, Path("output/gdp_trend"))
"""

from pathlib import Path
from typing import Optional

import altair as alt
import polars as pl

from .themes import enable_theme, get_palette, ColorPalette
from .spec import ChartSpec, ChartType


# Default chart dimensions for Substack
DEFAULT_WIDTH = 680
DEFAULT_HEIGHT = 420


class ChartBuilder:
    """Builds publication-quality charts from polars DataFrames.

    Supports Altair for static charts (PNG/SVG export) and Plotly
    for interactive HTML charts (future use).
    """

    def __init__(
        self,
        theme: str = "publication",
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
    ):
        self.theme_name = theme
        self.width = width
        self.height = height
        self.palette = get_palette(theme)
        enable_theme(theme)

    def line(
        self,
        data: pl.DataFrame,
        x: str,
        y: str,
        title: str = "",
        color: Optional[str] = None,
        x_label: str = "",
        y_label: str = "",
        subtitle: str = "",
        **kwargs,
    ) -> alt.Chart:
        """Create a line chart.

        Best for: trends over time, continuous data.
        """
        pdf = data.to_pandas()
        base = alt.Chart(pdf).properties(
            width=self.width,
            height=self.height,
            title=self._make_title(title, subtitle),
        )

        encoding = {
            "x": alt.X(x, title=x_label or x),
            "y": alt.Y(y, title=y_label or y),
        }
        if color:
            encoding["color"] = alt.Color(color)

        chart = base.mark_line(
            strokeWidth=2.5,
            interpolate="monotone",
        ).encode(**encoding)

        return self._add_source_note(chart, kwargs.get("source_note", ""))

    def bar(
        self,
        data: pl.DataFrame,
        x: str,
        y: str,
        title: str = "",
        color: Optional[str] = None,
        x_label: str = "",
        y_label: str = "",
        subtitle: str = "",
        highlight_negative: bool = False,
        **kwargs,
    ) -> alt.Chart:
        """Create a vertical bar chart.

        Best for: comparisons across categories.
        """
        pdf = data.to_pandas()
        base = alt.Chart(pdf).properties(
            width=self.width,
            height=self.height,
            title=self._make_title(title, subtitle),
        )

        encoding = {
            "x": alt.X(x, title=x_label or x),
            "y": alt.Y(y, title=y_label or y),
        }

        if highlight_negative:
            encoding["color"] = alt.condition(
                alt.datum[y] > 0,
                alt.value(self.palette.positive),
                alt.value(self.palette.negative),
            )
        elif color:
            encoding["color"] = alt.Color(color)

        chart = base.mark_bar().encode(**encoding)
        return self._add_source_note(chart, kwargs.get("source_note", ""))

    def horizontal_bar(
        self,
        data: pl.DataFrame,
        x: str,
        y: str,
        title: str = "",
        color: Optional[str] = None,
        x_label: str = "",
        y_label: str = "",
        subtitle: str = "",
        **kwargs,
    ) -> alt.Chart:
        """Create a horizontal bar chart.

        Best for: rankings, comparisons with long labels.
        """
        pdf = data.to_pandas()
        base = alt.Chart(pdf).properties(
            width=self.width,
            height=self.height,
            title=self._make_title(title, subtitle),
        )

        encoding = {
            "x": alt.X(x, title=x_label or x),
            "y": alt.Y(y, title=y_label or y, sort="-x"),
        }
        if color:
            encoding["color"] = alt.Color(color)

        chart = base.mark_bar().encode(**encoding)
        return self._add_source_note(chart, kwargs.get("source_note", ""))

    def scatter(
        self,
        data: pl.DataFrame,
        x: str,
        y: str,
        title: str = "",
        color: Optional[str] = None,
        size: Optional[str] = None,
        x_label: str = "",
        y_label: str = "",
        subtitle: str = "",
        **kwargs,
    ) -> alt.Chart:
        """Create a scatter plot.

        Best for: correlations between two numeric variables.
        """
        pdf = data.to_pandas()
        base = alt.Chart(pdf).properties(
            width=self.width,
            height=self.height,
            title=self._make_title(title, subtitle),
        )

        encoding = {
            "x": alt.X(x, title=x_label or x),
            "y": alt.Y(y, title=y_label or y),
        }
        if color:
            encoding["color"] = alt.Color(color)
        if size:
            encoding["size"] = alt.Size(size)

        # Add tooltip for all encoded channels
        tooltip_fields = [x, y]
        if color:
            tooltip_fields.append(color)
        if size:
            tooltip_fields.append(size)
        encoding["tooltip"] = tooltip_fields

        chart = base.mark_circle(opacity=0.7).encode(**encoding)
        return self._add_source_note(chart, kwargs.get("source_note", ""))

    def area(
        self,
        data: pl.DataFrame,
        x: str,
        y: str,
        title: str = "",
        color: Optional[str] = None,
        x_label: str = "",
        y_label: str = "",
        subtitle: str = "",
        **kwargs,
    ) -> alt.Chart:
        """Create an area chart.

        Best for: cumulative trends, volume emphasis.
        """
        pdf = data.to_pandas()
        base = alt.Chart(pdf).properties(
            width=self.width,
            height=self.height,
            title=self._make_title(title, subtitle),
        )

        encoding = {
            "x": alt.X(x, title=x_label or x),
            "y": alt.Y(y, title=y_label or y),
        }
        if color:
            encoding["color"] = alt.Color(color)

        chart = base.mark_area(
            opacity=0.6,
            line=True,
            interpolate="monotone",
        ).encode(**encoding)

        return self._add_source_note(chart, kwargs.get("source_note", ""))

    def from_spec(self, spec: ChartSpec, data: pl.DataFrame) -> alt.Chart:
        """Build a chart from a ChartSpec and pre-loaded data.

        This is the primary entry point when using ChartSpec objects.
        """
        method_map = {
            ChartType.LINE: self.line,
            ChartType.BAR: self.bar,
            ChartType.HORIZONTAL_BAR: self.horizontal_bar,
            ChartType.SCATTER: self.scatter,
            ChartType.AREA: self.area,
            ChartType.STACKED_AREA: self.area,
        }

        method = method_map.get(spec.chart_type)
        if method is None:
            raise ValueError(f"Unsupported chart type: {spec.chart_type}")

        kwargs = {
            "data": data,
            "x": spec.x,
            "y": spec.y,
            "title": spec.title,
            "x_label": spec.x_label,
            "y_label": spec.y_label,
            "subtitle": spec.subtitle,
            "source_note": spec.source_note,
        }
        if spec.color:
            kwargs["color"] = spec.color
        if spec.size:
            kwargs["size"] = spec.size

        # Pass extra options
        kwargs.update(spec.options)

        return method(**kwargs)

    # --- Export ---

    def save(
        self,
        chart: alt.Chart,
        output_path: Path,
        formats: Optional[list[str]] = None,
    ) -> list[Path]:
        """Save a chart to disk in the specified formats.

        Args:
            chart: An Altair chart object.
            output_path: Base path without extension (e.g., Path("output/gdp_trend")).
            formats: List of formats to export (default: ["png", "svg"]).

        Returns:
            List of paths to saved files.
        """
        formats = formats or ["png", "svg"]
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        saved = []
        for fmt in formats:
            path = output_path.parent / f"{output_path.name}.{fmt}"
            chart.save(str(path), format=fmt)
            saved.append(path)

        return saved

    def to_png_bytes(self, chart: alt.Chart) -> bytes:
        """Render a chart to PNG bytes (for inline embedding).

        Returns:
            PNG image as bytes.
        """
        import vl_convert as vlc
        vl_spec = chart.to_dict()
        return vlc.vegalite_to_png(vl_spec, scale=2)

    # --- Private helpers ---

    def _make_title(self, title: str, subtitle: str = "") -> alt.TitleParams | str:
        """Create Altair title with optional subtitle."""
        if subtitle:
            return alt.TitleParams(
                text=title,
                subtitle=subtitle,
            )
        return title

    def _add_source_note(self, chart: alt.Chart, source_note: str) -> alt.Chart:
        """Add a small source annotation below the chart."""
        if not source_note:
            return chart

        # Use a text layer at the bottom
        note = alt.Chart({"values": [{}]}).mark_text(
            align="right",
            baseline="top",
            color=self.palette.neutral,
            fontSize=9,
            text=f"Source: {source_note}",
        ).encode(
            x=alt.value(self.width),
            y=alt.value(self.height + 5),
        )

        return alt.layer(chart, note)
