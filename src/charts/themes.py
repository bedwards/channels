"""
Chart Themes — Publication-quality palettes and Altair theming.

Ported from graphyard charts/themes with additions for the
Lluminate Network publications.
"""

from dataclasses import dataclass, field

import altair as alt


@dataclass
class ColorPalette:
    """Color palette for charts."""

    name: str
    primary: str
    secondary: str
    accent: str
    positive: str
    negative: str
    neutral: str
    background: str = "#FFFFFF"
    text: str = "#1A1A2E"
    grid: str = "#E5E5E5"
    sequence: list[str] = field(default_factory=list)


# --- Palettes ---

PUBLICATION = ColorPalette(
    name="publication",
    primary="#2563EB",
    secondary="#7C3AED",
    accent="#F59E0B",
    positive="#10B981",
    negative="#EF4444",
    neutral="#6B7280",
    sequence=[
        "#2563EB", "#7C3AED", "#EC4899", "#F59E0B",
        "#10B981", "#06B6D4", "#8B5CF6", "#F97316",
    ],
)

ECONOMIST = ColorPalette(
    name="economist",
    primary="#0D6EAD",
    secondary="#8B0000",
    accent="#DAA520",
    positive="#228B22",
    negative="#8B0000",
    neutral="#4A4A4A",
    sequence=[
        "#0D6EAD", "#8B0000", "#DAA520", "#228B22",
        "#4B0082", "#FF6347",
    ],
)

WORLDBANK = ColorPalette(
    name="worldbank",
    primary="#002244",
    secondary="#0071BC",
    accent="#F5A623",
    positive="#00A651",
    negative="#ED1C24",
    neutral="#58595B",
    sequence=[
        "#002244", "#0071BC", "#00A651", "#F5A623",
        "#ED1C24", "#8E44AD",
    ],
)

MATERIAL_RECORD = ColorPalette(
    name="material_record",
    primary="#C4A265",       # Warm gold
    secondary="#8B7355",     # Muted brown
    accent="#D4764E",        # Burnt orange
    positive="#7A9E7E",      # Sage green
    negative="#B85450",      # Muted red
    neutral="#9E9E9E",       # Mid gray
    background="#171717",    # Near-black (matches Material Record style)
    text="#E8E0D4",          # Warm off-white
    grid="#333333",          # Dark grid lines
    sequence=[
        "#C4A265", "#D4764E", "#7A9E7E", "#8B7355",
        "#B85450", "#6B8E9E", "#9B8EC4", "#C47A65",
    ],
)


_PALETTES = {
    "publication": PUBLICATION,
    "economist": ECONOMIST,
    "worldbank": WORLDBANK,
    "material_record": MATERIAL_RECORD,
}


def get_palette(name: str = "publication") -> ColorPalette:
    """Get a color palette by name."""
    return _PALETTES.get(name.lower(), PUBLICATION)


def _make_altair_theme(palette: ColorPalette) -> dict:
    """Convert a ColorPalette into an Altair theme config dict."""
    return {
        "config": {
            "background": palette.background,
            "title": {
                "color": palette.text,
                "fontSize": 16,
                "fontWeight": "bold",
                "anchor": "start",
                "offset": 10,
            },
            "axis": {
                "labelColor": palette.text,
                "titleColor": palette.text,
                "gridColor": palette.grid,
                "domainColor": palette.grid,
                "tickColor": palette.grid,
                "labelFontSize": 11,
                "titleFontSize": 13,
            },
            "legend": {
                "labelColor": palette.text,
                "titleColor": palette.text,
                "labelFontSize": 11,
                "titleFontSize": 12,
            },
            "view": {
                "stroke": "transparent",
            },
            "range": {
                "category": palette.sequence,
            },
            "mark": {
                "color": palette.primary,
            },
            "line": {
                "strokeWidth": 2.5,
            },
            "bar": {
                "cornerRadiusTopLeft": 3,
                "cornerRadiusTopRight": 3,
            },
            "point": {
                "size": 60,
                "filled": True,
            },
        }
    }


def register_themes() -> None:
    """Register all palettes as Altair themes.

    After calling this, use: alt.theme.enable("material_record")
    """
    for name, palette in _PALETTES.items():
        theme_config = _make_altair_theme(palette)

        @alt.theme.register(name, enable=False)
        def _theme_fn(cfg=theme_config):
            return alt.theme.ThemeConfig(cfg)


def enable_theme(name: str = "publication") -> None:
    """Register and enable an Altair theme by palette name."""
    register_themes()
    if name in _PALETTES:
        alt.theme.enable(name)
    else:
        alt.theme.enable("publication")
