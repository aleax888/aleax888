"""
Genera estadísticas de GitHub (commits por año, lenguajes, repos y datos
curiosos) y las renderiza en una plantilla SVG.

Requiere en el .env:
    GITHUB_USERNAME=tu_usuario
    GITHUB_TOKEN=ghp_xxx   (con permisos de lectura; si quieres que se
                             cuenten también tus commits en repos privados,
                             el token debe pertenecer a GITHUB_USERNAME y
                             tener acceso a esos repos)

Este archivo es solo el orquestador: toda la lógica vive en el paquete
`stats/` (config, cliente de GitHub, agregación, layout del gráfico y
renderizado del SVG).
"""
from pathlib import Path

from stats.aggregator import StatsAggregator
from stats.chart_layout import ChartLayoutBuilder
from stats.config import Config
from stats.github_client import GitHubClient
from stats.renderer import SvgRenderer

ROOT = Path(__file__).resolve().parent


def main() -> None:
    config = Config.from_env(ROOT)
    client = GitHubClient(config.token)
    aggregator = StatsAggregator()

    print(f"Obteniendo datos de GitHub para @{config.username}…")

    user = client.get_user_overview(config.username)
    repos = client.get_all_repositories(config.username)

    created_year = int(user["createdAt"][:4])
    contributions_by_year = client.get_contributions_by_year(config.username, created_year)

    stats = aggregator.build(user, repos, contributions_by_year)
    stats["commits_chart"] = ChartLayoutBuilder.build_commits_chart(
        stats["commits_by_year"], stats["best_year"]["year"]
    )
    stats["language_bars"] = ChartLayoutBuilder.build_language_bars(stats["top_languages"])

    renderer = SvgRenderer(config.assets_dir)
    renderer.render(stats)

    print(
        f"✅ github_stats.svg actualizado: {stats['commits_total']} commits, "
        f"{stats['repositories']} repos, {len(stats['top_languages'])} lenguajes."
    )


if __name__ == "__main__":
    main()
