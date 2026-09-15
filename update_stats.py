"""
Generates GitHub statistics (commits per year, languages, repos, and fun
facts) and renders them in an SVG template.

Requires in the .env:
    GITHUB_USERNAME=your_username
    GITHUB_TOKEN=ghp_xxx   (with read permissions; if you want your private
                            repo commits counted as well, the token must belong
                            to GITHUB_USERNAME and have access to those repos)

This file is only the orchestrator: all the logic lives in the `stats/`
package (config, GitHub client, aggregation, chart layout, and SVG
rendering).
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

    print(f"Fetching GitHub data for @{config.username}…")

    user = client.get_user_overview(config.username)
    repos = client.get_all_repositories(config.username)

    created_year = int(user["createdAt"][:4])
    contributions_by_year = client.get_contributions_by_year(config.username, created_year)

    stats = aggregator.build(user, repos, contributions_by_year)
    stats["commits_chart"] = ChartLayoutBuilder.build_commits_chart(
        stats["commits_by_year"], stats["best_year"]["year"]
    )
    stats["language_bars"] = ChartLayoutBuilder.build_language_bars(stats["top_languages"])

    renderer = SvgRenderer(config.assets_dir, config.templates_dir)
    renderer.render(stats)

    print(
        f"✅ github_stats.svg updated: {stats['commits_total']} commits, "
        f"{stats['repositories']} repos, {len(stats['top_languages'])} languages."
    )


if __name__ == "__main__":
    main()
