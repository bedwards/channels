"""Tests for graphyard chart integration.

Unit tests run without database access.
Integration tests (marked with @pytest.mark.integration) require
the graphyard database on the studio host (192.168.4.50).
"""

import tempfile
from pathlib import Path

import pytest
import polars as pl

from src.charts import GraphyardDB, ChartBuilder, ChartSpec, ChartType
from src.charts.themes import (
    get_palette, register_themes, enable_theme,
    PUBLICATION, MATERIAL_RECORD,
)


# --- Unit Tests (no database needed) ---


class TestChartSpec:
    """Tests for ChartSpec model."""

    def test_from_dict(self):
        """Test creating a ChartSpec from a dictionary."""
        d = {
            "chart_id": "test-chart",
            "chart_type": "line",
            "title": "Test Chart",
            "query": "SELECT 1",
            "x": "year",
            "y": "value",
            "x_label": "Year",
            "y_label": "Value",
        }
        spec = ChartSpec.from_dict(d)
        assert spec.chart_id == "test-chart"
        assert spec.chart_type == ChartType.LINE
        assert spec.title == "Test Chart"
        assert spec.x == "year"
        assert spec.y == "value"

    def test_to_dict_roundtrip(self):
        """Test that to_dict/from_dict round-trips cleanly."""
        spec = ChartSpec(
            chart_id="rt-test",
            chart_type=ChartType.BAR,
            title="Roundtrip",
            query="SELECT x, y FROM t",
            x="x", y="y",
        )
        d = spec.to_dict()
        spec2 = ChartSpec.from_dict(d)
        assert spec2.chart_id == spec.chart_id
        assert spec2.chart_type == spec.chart_type
        assert spec2.title == spec.title

    def test_chart_type_enum(self):
        """Test all ChartType values are strings."""
        for ct in ChartType:
            assert isinstance(ct.value, str)

    def test_missing_query_raises(self):
        """Test that execute raises when no query is set."""
        spec = ChartSpec(
            chart_id="no-query",
            chart_type=ChartType.LINE,
            title="No Query",
        )
        with pytest.raises(ValueError, match="No query defined"):
            spec.execute(None)


class TestThemes:
    """Tests for chart theme system."""

    def test_get_palette_default(self):
        """Test getting default palette."""
        palette = get_palette()
        assert palette.name == "publication"
        assert palette.primary == "#2563EB"

    def test_get_palette_by_name(self):
        """Test getting palette by name."""
        palette = get_palette("material_record")
        assert palette.name == "material_record"
        assert palette.background == "#171717"

    def test_get_palette_unknown_returns_default(self):
        """Test that unknown palette name returns publication."""
        palette = get_palette("nonexistent")
        assert palette.name == "publication"

    def test_register_themes(self):
        """Test that themes register with altair without error."""
        register_themes()

    def test_enable_theme(self):
        """Test enabling a theme."""
        enable_theme("material_record")

    def test_palette_has_sequence(self):
        """Test that all palettes have a color sequence."""
        for name in ["publication", "economist", "worldbank", "material_record"]:
            palette = get_palette(name)
            assert len(palette.sequence) >= 4


class TestChartBuilder:
    """Tests for ChartBuilder with sample data (no database needed)."""

    @pytest.fixture
    def sample_data(self):
        return pl.DataFrame({
            "year": list(range(2000, 2024)),
            "value": [float(i * 1.5 + 10) for i in range(24)],
        })

    @pytest.fixture
    def category_data(self):
        return pl.DataFrame({
            "country": ["USA", "China", "Japan", "Germany", "India"],
            "gdp": [25.5, 17.9, 4.2, 4.1, 3.4],
        })

    @pytest.fixture
    def multi_series(self):
        years = list(range(2010, 2024)) * 2
        countries = ["USA"] * 14 + ["China"] * 14
        values = [15.0 + i * 0.7 for i in range(14)] + [6.0 + i * 1.2 for i in range(14)]
        return pl.DataFrame({
            "year": years,
            "country": countries,
            "gdp": values,
        })

    @pytest.fixture
    def growth_data(self):
        return pl.DataFrame({
            "year": list(range(2015, 2025)),
            "growth": [2.5, 1.8, 2.3, 3.0, 2.2, -3.1, 5.9, 3.0, 2.6, 2.8],
        })

    def test_line_chart(self, sample_data):
        """Test building a line chart from sample data."""
        import altair as alt
        builder = ChartBuilder(theme="publication")
        chart = builder.line(
            sample_data, x="year", y="value",
            title="Test Line Chart",
        )
        assert isinstance(chart, alt.Chart)

    def test_bar_chart(self, category_data):
        """Test building a bar chart."""
        import altair as alt
        builder = ChartBuilder()
        chart = builder.bar(
            category_data, x="country", y="gdp",
            title="GDP by Country",
        )
        assert isinstance(chart, alt.Chart)

    def test_horizontal_bar(self, category_data):
        """Test building a horizontal bar chart."""
        import altair as alt
        builder = ChartBuilder()
        chart = builder.horizontal_bar(
            category_data, x="gdp", y="country",
            title="GDP Rankings",
        )
        assert isinstance(chart, alt.Chart)

    def test_scatter_chart(self, sample_data):
        """Test building a scatter plot."""
        import altair as alt
        builder = ChartBuilder()
        chart = builder.scatter(
            sample_data, x="year", y="value",
            title="Scatter Test",
        )
        assert isinstance(chart, alt.Chart)

    def test_area_chart(self, sample_data):
        """Test building an area chart."""
        import altair as alt
        builder = ChartBuilder()
        chart = builder.area(
            sample_data, x="year", y="value",
            title="Area Test",
        )
        assert isinstance(chart, alt.Chart)

    def test_multi_line_with_color(self, multi_series):
        """Test multi-series line chart with color encoding."""
        import altair as alt
        builder = ChartBuilder()
        chart = builder.line(
            multi_series, x="year", y="gdp", color="country",
            title="Multi-line Test",
        )
        assert isinstance(chart, alt.Chart)

    def test_bar_highlight_negative(self, growth_data):
        """Test bar chart with negative value highlighting."""
        import altair as alt
        builder = ChartBuilder()
        chart = builder.bar(
            growth_data, x="year", y="growth",
            title="Growth with Negatives",
            highlight_negative=True,
        )
        assert isinstance(chart, (alt.Chart, alt.LayerChart))

    def test_save_png(self, sample_data):
        """Test saving a chart to PNG file."""
        builder = ChartBuilder()
        chart = builder.line(
            sample_data, x="year", y="value",
            title="Save Test",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = builder.save(chart, Path(tmpdir) / "test", formats=["png"])
            assert len(paths) == 1
            assert paths[0].exists()
            assert paths[0].stat().st_size > 0

    def test_save_svg(self, sample_data):
        """Test saving a chart to SVG file."""
        builder = ChartBuilder()
        chart = builder.line(
            sample_data, x="year", y="value",
            title="SVG Test",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = builder.save(chart, Path(tmpdir) / "test", formats=["svg"])
            assert len(paths) == 1
            assert paths[0].exists()
            assert paths[0].stat().st_size > 0

    def test_from_spec(self, sample_data):
        """Test building a chart from a ChartSpec."""
        import altair as alt
        spec = ChartSpec(
            chart_id="spec-test",
            chart_type=ChartType.LINE,
            title="From Spec",
            x="year", y="value",
            x_label="Year", y_label="Value",
        )
        builder = ChartBuilder()
        chart = builder.from_spec(spec, sample_data)
        assert isinstance(chart, alt.Chart)

    def test_material_record_theme(self, sample_data):
        """Test chart with Material Record dark theme."""
        import altair as alt
        builder = ChartBuilder(theme="material_record")
        chart = builder.line(
            sample_data, x="year", y="value",
            title="Dark Theme Test",
        )
        assert isinstance(chart, alt.Chart)


# --- Integration Tests (require studio database) ---


@pytest.mark.integration
class TestGraphyardDB:
    """Integration tests for GraphyardDB (requires studio host)."""

    @pytest.fixture
    def db(self):
        return GraphyardDB.from_env()

    def test_connection(self, db):
        """Test connecting to graphyard on studio."""
        assert db.test_connection() is True

    def test_list_schemas(self, db):
        """Test listing schemas returns expected names."""
        schemas = db.list_schemas()
        assert isinstance(schemas, list)
        assert len(schemas) > 0
        assert "public" in schemas

    def test_list_tables(self, db):
        """Test listing tables in public schema."""
        tables = db.list_tables("public")
        assert isinstance(tables, list)
        assert len(tables) > 0
        table_names = [t["table_name"] for t in tables]
        assert "entities" in table_names or "indicators" in table_names

    def test_query_returns_polars(self, db):
        """Test that query returns polars DataFrame."""
        df = db.query("SELECT 1 as val, 'hello' as text")
        assert isinstance(df, pl.DataFrame)
        assert "val" in df.columns
        assert len(df) == 1

    def test_query_country_data(self, db):
        """Test querying actual country data."""
        df = db.query("""
            SELECT year, value
            FROM public.country_data
            WHERE indicator_code = 'NY.GDP.MKTP.CD'
              AND entity_code = 'USA'
              AND year = 2022
        """)
        assert isinstance(df, pl.DataFrame)
        assert len(df) >= 1

    def test_query_single(self, db):
        """Test query_single returns a scalar."""
        result = db.query_single("SELECT COUNT(*) FROM public.entities")
        assert isinstance(result, int)
        assert result > 0

    def test_describe_table(self, db):
        """Test describing a table's columns."""
        df = db.describe_table("entities", "public")
        assert isinstance(df, pl.DataFrame)
        assert "column_name" in df.columns
        assert len(df) > 0


@pytest.mark.integration
class TestEndToEnd:
    """End-to-end integration tests: query → chart → save."""

    def test_query_and_chart(self):
        """Full pipeline: query graphyard → polars → altair → PNG."""
        db = GraphyardDB.from_env()
        if not db.test_connection():
            pytest.skip("Graphyard database not available")

        df = db.query("""
            SELECT year, value / 1e12 as gdp_trillions
            FROM public.world_data
            WHERE indicator_code = 'NY.GDP.MKTP.CD'
              AND year BETWEEN 2000 AND 2023
              AND value IS NOT NULL
            ORDER BY year
        """)
        assert len(df) > 0

        builder = ChartBuilder(theme="publication")
        chart = builder.line(
            df, x="year", y="gdp_trillions",
            title="World GDP (E2E Test)",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = builder.save(chart, Path(tmpdir) / "e2e_test", formats=["png"])
            assert len(paths) == 1
            assert paths[0].stat().st_size > 1000  # Should be at least 1KB

    def test_spec_driven_chart(self):
        """Test spec-driven pipeline: spec → query → chart → save."""
        db = GraphyardDB.from_env()
        if not db.test_connection():
            pytest.skip("Graphyard database not available")

        spec = ChartSpec(
            chart_id="e2e-spec-test",
            chart_type=ChartType.BAR,
            title="Top 5 Economies (E2E Spec Test)",
            query="""
                SELECT e.entity_name as country,
                       d.value / 1e12 as gdp_trillions
                FROM public.country_data d
                JOIN public.entities e ON d.entity_code = e.entity_code
                WHERE d.indicator_code = 'NY.GDP.MKTP.CD'
                  AND d.year = 2022
                  AND d.value IS NOT NULL
                ORDER BY d.value DESC
                LIMIT 5
            """,
            x="country",
            y="gdp_trillions",
            x_label="Country",
            y_label="GDP (Trillions USD)",
        )

        df = spec.execute(db)
        assert len(df) >= 1

        builder = ChartBuilder()
        chart = builder.from_spec(spec, df)

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = builder.save(chart, Path(tmpdir) / "spec_test", formats=["png"])
            assert paths[0].stat().st_size > 1000
