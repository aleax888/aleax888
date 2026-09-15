"""Pure geometry for the SVG: converts stats into x/y/width/height coordinates.

It does not touch the network or the template, only math. The constants must
match the coordinates used in assets/github_stats.svg.template.
"""
from __future__ import annotations

# Bar chart for "commits per year"
CHART_X = 60
CHART_WIDTH = 370
CHART_BASELINE_Y = 406
CHART_MAX_HEIGHT = 130
BAR_WIDTH = 28
MAX_YEARS_SHOWN = 6

# Horizontal bars for "top languages".
# Uses the same available height as the commits chart (CHART_MAX_HEIGHT)
# so both blocks remain symmetrical, distributing the rows like
# "space-between" according to how many languages there are.
LANG_AREA_TOP = 276
LANG_AREA_HEIGHT = CHART_MAX_HEIGHT
LANG_TRACK_WIDTH = 380
LANG_BAR_HEIGHT = 6        # grosor normal de la barra
LANG_BAR_HEIGHT_TOP = 10   # grosor del lenguaje #1 (destacado)


class ChartLayoutBuilder:
    """Precomputes each bar position so the template only has to draw."""

    @staticmethod
    def build_commits_chart(commits_by_year: dict[int, int], best_year: int) -> list[dict]:
        years = sorted(commits_by_year.items())[-MAX_YEARS_SHOWN:]
        if not years:
            return []

        max_count = max(count for _, count in years) or 1
        n = len(years)
        gap = (CHART_WIDTH - n * BAR_WIDTH) / (n - 1) if n > 1 else 0
        step = BAR_WIDTH + gap

        bars = []
        for i, (year, count) in enumerate(years):
            height = max(4, round(count / max_count * CHART_MAX_HEIGHT))
            x = round(CHART_X + i * step)
            bars.append(
                {
                    "year": year,
                    "year_short": str(year)[2:],
                    "count": count,
                    "x": x,
                    "center_x": x + BAR_WIDTH // 2,
                    "width": BAR_WIDTH,
                    "height": height,
                    "y": CHART_BASELINE_Y - height,
                    "is_best": year == best_year,
                }
            )
        return bars

    @staticmethod
    def build_language_bars(top_languages: list[dict]) -> list[dict]:
        n = len(top_languages)
        step = LANG_AREA_HEIGHT / (n - 1) if n > 1 else 0

        bars = []
        for i, lang in enumerate(top_languages):
            is_top = i == 0
            bars.append(
                {
                    **lang,
                    "y": round(LANG_AREA_TOP + i * step),
                    "bar_width": round(lang["percent"] / 100 * LANG_TRACK_WIDTH),
                    "bar_height": LANG_BAR_HEIGHT_TOP if is_top else LANG_BAR_HEIGHT,
                    "is_top": is_top,
                }
            )
        return bars
