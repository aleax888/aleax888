"""Agregaciones de estadísticas: commits, lenguajes y datos curiosos."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

WEEKDAYS_EN = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


class StatsAggregator:
    """Convierte las respuestas crudas de la API en el diccionario de stats final."""

    def __init__(self, top_languages_n: int = 3):
        self._top_languages_n = top_languages_n

    # -- Lenguajes ---------------------------------------------------------

    def aggregate_languages(self, repos: list[dict]) -> list[dict]:
        """Pondera lenguajes por % dentro de cada repo, no por bytes globales.

        Cada repo aporta un total fijo de 100 puntos, repartidos entre sus
        lenguajes según el % que ocupan en ESE repo (si un repo es 64%
        Python, Python suma 64 puntos). Así todos los repos pesan igual en
        el cálculo final, y uno con archivos pesados (p. ej. notebooks con
        imágenes embebidas) no domina el resultado solo por tener más bytes
        que el resto.
        """
        points: Counter[str] = Counter()
        colors: dict[str, str] = {}
        counted_repos = 0

        for repo in repos:
            edges = repo["languages"]["edges"]
            repo_total = sum(edge["size"] for edge in edges)
            if repo_total == 0:
                continue  # repo sin código detectable (solo README, vacío, etc.)

            counted_repos += 1
            for edge in edges:
                name = edge["node"]["name"]
                share = edge["size"] / repo_total * 100  # % dentro del repo
                points[name] += share
                colors[name] = edge["node"]["color"] or "#858585"

        if counted_repos == 0:
            return []

        ranked = points.most_common()
        top = ranked[: self._top_languages_n]
        rest = ranked[self._top_languages_n :]

        languages = [
            {
                "name": name,
                "percent": round(pts / counted_repos, 1),
                "color": colors[name],
            }
            for name, pts in top
        ]

        if rest:
            others_pts = sum(pts for _, pts in rest)
            languages.append(
                {
                    "name": "Others",
                    "percent": round(others_pts / counted_repos, 1),
                    "color": "#858585",
                }
            )

        return languages

    # -- Calendario de contribuciones --------------------------------------

    @staticmethod
    def flatten_calendar_days(contributions_by_year: dict[int, dict]) -> list[dict]:
        """Aplana los días de contribución de todos los años, ordenados por fecha."""
        days = []
        for year_data in contributions_by_year.values():
            for week in year_data["contributionCalendar"]["weeks"]:
                days.extend(week["contributionDays"])
        days.sort(key=lambda d: d["date"])
        return days

    @staticmethod
    def longest_streak(days: list[dict]) -> int:
        longest = current = 0
        for day in days:
            if day["contributionCount"] > 0:
                current += 1
                longest = max(longest, current)
            else:
                current = 0
        return longest

    @staticmethod
    def most_active_weekday(days: list[dict]) -> str:
        totals: Counter[int] = Counter()
        for day in days:
            totals[day["weekday"]] += day["contributionCount"]
        if not totals:
            return "N/A"
        weekday_index, _ = totals.most_common(1)[0]
        return WEEKDAYS_EN[weekday_index]

    @staticmethod
    def busiest_day(days: list[dict]) -> dict | None:
        if not days:
            return None
        top = max(days, key=lambda d: d["contributionCount"])
        date = datetime.strptime(top["date"], "%Y-%m-%d")
        return {
            "date": top["date"],
            "commits": top["contributionCount"],
            "date_label": f"{date.day} {MONTHS_EN[date.month - 1]} {date.year}",
        }

    # -- Ensamblado final ----------------------------------------------------

    def build(self, user: dict, repos: list[dict], contributions_by_year: dict[int, dict]) -> dict:
        """Devuelve el diccionario de stats (sin el layout de gráficos en
        píxeles; eso lo agrega ChartLayoutBuilder por separado)."""
        commits_by_year = {
            year: data["totalCommitContributions"] + data["restrictedContributionsCount"]
            for year, data in contributions_by_year.items()
        }
        commits_total = sum(commits_by_year.values())
        pull_requests = sum(d["totalPullRequestContributions"] for d in contributions_by_year.values())
        issues = sum(d["totalIssueContributions"] for d in contributions_by_year.values())
        reviews = sum(d["totalPullRequestReviewContributions"] for d in contributions_by_year.values())

        best_year, best_year_commits = max(commits_by_year.items(), key=lambda kv: kv[1])

        active_repos = [r for r in repos if not r["isArchived"]]
        total_stars = sum(r["stargazerCount"] for r in repos)
        total_forks = sum(r["forkCount"] for r in repos)
        top_repo = max(repos, key=lambda r: r["stargazerCount"], default=None)

        days = self.flatten_calendar_days(contributions_by_year)
        created_at = datetime.fromisoformat(user["createdAt"].replace("Z", "+00:00"))
        account_age_days = (datetime.now(timezone.utc) - created_at).days

        top_languages = self.aggregate_languages(repos)

        return {
            # Perfil
            "username": user["login"],
            "name": user["name"] or user["login"],
            "updated": datetime.now().strftime("%Y-%m-%d"),
            "account_created": user["createdAt"][:10],
            "account_age_years": round(account_age_days / 365, 1),
            "followers": user["followers"]["totalCount"],
            "following": user["following"]["totalCount"],

            # Repos
            "repositories": len(repos),
            "active_repositories": len(active_repos),
            "total_stars": total_stars,
            "total_forks": total_forks,
            "top_repo": (
                {"name": top_repo["name"], "stars": top_repo["stargazerCount"]}
                if top_repo else None
            ),

            # Commits por año
            "commits_total": commits_total,
            "commits_by_year": commits_by_year,           # {2022: 340, 2023: 890, ...}
            "commits_this_year": commits_by_year.get(datetime.now().year, 0),
            "best_year": {"year": best_year, "commits": best_year_commits},

            # Actividad
            "pull_requests": pull_requests,
            "issues": issues,
            "code_reviews": reviews,

            # Lenguajes (el layout de barras lo agrega ChartLayoutBuilder)
            "top_languages": top_languages,                # [{"name","percent","color"}, ...]

            # Datos curiosos
            "longest_streak": self.longest_streak(days),
            "most_active_weekday": self.most_active_weekday(days),
            "busiest_day": self.busiest_day(days),
        }
