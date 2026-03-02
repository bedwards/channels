"""
Charts Module — Graphyard Integration

Data-driven chart generation for Substack posts using the graphyard
PostgreSQL database on the studio host.

Stack: polars + altair + plotly
Database: graphyard on studio (192.168.4.50)

Usage:
    from src.charts import GraphyardDB, ChartBuilder, ChartSpec

    db = GraphyardDB.from_env()
    df = db.query("SELECT year, value FROM public.country_data WHERE ...")
    builder = ChartBuilder(theme="material_record")
    chart = builder.line(df, x="year", y="value", title="GDP Over Time")
    builder.save(chart, Path("output/gdp_trend"))
"""

from .database import GraphyardDB
from .builder import ChartBuilder
from .spec import ChartSpec, ChartType

__all__ = [
    "GraphyardDB",
    "ChartBuilder",
    "ChartSpec",
    "ChartType",
]
