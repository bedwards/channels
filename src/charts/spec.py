"""
Chart Specification — Declarative chart definitions.

A ChartSpec fully describes a chart: what data to query, how to render it,
and what type of chart to produce. Specs can be defined inline in code,
loaded from YAML config, or defined via CLI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import polars as pl


class ChartType(str, Enum):
    """Chart types following 2025 data visualization best practices."""

    LINE = "line"
    BAR = "bar"
    HORIZONTAL_BAR = "horizontal_bar"
    SCATTER = "scatter"
    AREA = "area"
    STACKED_AREA = "stacked_area"


@dataclass
class ChartSpec:
    """Declarative chart specification.

    Describes everything needed to produce a chart: the data source
    (SQL query against graphyard), chart type, column mappings, and styling.

    Usage:
        spec = ChartSpec(
            chart_id="world-gdp-trend",
            chart_type=ChartType.LINE,
            title="World GDP Over Time",
            query="SELECT year, value FROM public.world_data WHERE ...",
            x="year", y="value",
        )
        df = spec.execute(db)
        chart = builder.from_spec(spec, df)
    """

    chart_id: str
    chart_type: ChartType
    title: str

    # Data source
    query: str = ""
    schema: str = "public"
    params: tuple = ()

    # Column mappings
    x: str = ""
    y: str = ""
    color: Optional[str] = None
    size: Optional[str] = None

    # Labels
    x_label: str = ""
    y_label: str = ""
    subtitle: str = ""
    source_note: str = ""

    # Formatting
    x_format: Optional[str] = None
    y_format: Optional[str] = None

    # Extra options
    options: dict[str, Any] = field(default_factory=dict)

    def execute(self, db) -> pl.DataFrame:
        """Execute the spec's SQL query against a GraphyardDB instance.

        Args:
            db: A GraphyardDB instance.

        Returns:
            polars.DataFrame with query results.
        """
        if not self.query:
            raise ValueError(f"No query defined for chart spec '{self.chart_id}'")
        return db.query(self.query, self.params if self.params else None)

    @classmethod
    def from_dict(cls, d: dict) -> "ChartSpec":
        """Create a ChartSpec from a dictionary (e.g., parsed from YAML).

        Expected keys: chart_id, chart_type, title, query, x, y, etc.
        """
        chart_type = d.get("chart_type", "line")
        if isinstance(chart_type, str):
            chart_type = ChartType(chart_type)

        return cls(
            chart_id=d["chart_id"],
            chart_type=chart_type,
            title=d.get("title", ""),
            query=d.get("query", ""),
            schema=d.get("schema", "public"),
            params=tuple(d.get("params", ())),
            x=d.get("x", ""),
            y=d.get("y", ""),
            color=d.get("color"),
            size=d.get("size"),
            x_label=d.get("x_label", ""),
            y_label=d.get("y_label", ""),
            subtitle=d.get("subtitle", ""),
            source_note=d.get("source_note", ""),
            x_format=d.get("x_format"),
            y_format=d.get("y_format"),
            options=d.get("options", {}),
        )

    def to_dict(self) -> dict:
        """Serialize spec to a dictionary."""
        return {
            "chart_id": self.chart_id,
            "chart_type": self.chart_type.value,
            "title": self.title,
            "query": self.query,
            "schema": self.schema,
            "x": self.x,
            "y": self.y,
            "color": self.color,
            "size": self.size,
            "x_label": self.x_label,
            "y_label": self.y_label,
            "subtitle": self.subtitle,
            "source_note": self.source_note,
            "x_format": self.x_format,
            "y_format": self.y_format,
            "options": self.options,
        }
