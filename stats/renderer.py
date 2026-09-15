"""SVG template rendering with Jinja2."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader


class SvgRenderer:
    """Loads the template once and renders it against the stats dictionary."""

    def __init__(self, assets_dir: Path, template_dir: Path, template_name: str = "github_stats.svg.template"):
        self._assets_dir = assets_dir
        env = Environment(loader=FileSystemLoader(template_dir))
        self._template = env.get_template(template_name)

    def render(self, stats: dict, output_name: str = "github_stats.svg") -> Path:
        svg = self._template.render(**stats)
        output_path = self._assets_dir / output_name
        output_path.write_text(svg, encoding="utf-8")
        return output_path
