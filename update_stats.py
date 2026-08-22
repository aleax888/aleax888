"""
Genera estadísticas de GitHub (commits por año, lenguajes, repos y datos
curiosos) y las renderiza en una plantilla SVG.

Requiere en el .env:
    GITHUB_USERNAME=tu_usuario
    GITHUB_TOKEN=ghp_xxx   (con permisos de lectura; si quieres que se
                             cuenten también tus commits en repos privados,
                             el token debe pertenecer a GITHUB_USERNAME y
                             tener acceso a esos repos)
"""

import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader
import os

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"

load_dotenv(ROOT / ".env")

GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

if not GITHUB_USERNAME or not GITHUB_TOKEN:
    sys.exit("Error: define GITHUB_USERNAME y GITHUB_TOKEN en tu archivo .env")

REST_URL = "https://api.github.com"
GRAPHQL_URL = f"{REST_URL}/graphql"
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
}

WEEKDAYS_EN = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Geometría del gráfico de barras "commits por año" (debe coincidir con las
# coordenadas usadas en assets/github_stats.svg.template).
CHART_X = 60
CHART_WIDTH = 370
CHART_BASELINE_Y = 406
CHART_MAX_HEIGHT = 130
BAR_WIDTH = 28
MAX_YEARS_SHOWN = 6

# Geometría de las barras horizontales de "lenguajes principales".
# Usa el mismo alto disponible que el chart de commits (CHART_MAX_HEIGHT)
# para que ambos bloques queden simétricos, y reparte las filas tipo
# "space-between" según cuántos lenguajes haya.
LANG_AREA_TOP = 276
LANG_AREA_HEIGHT = CHART_MAX_HEIGHT
LANG_TRACK_WIDTH = 380
LANG_BAR_HEIGHT = 6        # grosor normal de la barra
LANG_BAR_HEIGHT_TOP = 10   # grosor del lenguaje #1 (destacado)


# ---------------------------------------------------------------------------
# Peticiones a la API
# ---------------------------------------------------------------------------

def github_graphql(query: str, variables: dict | None = None) -> dict:
    response = requests.post(
        GRAPHQL_URL,
        headers=HEADERS,
        json={"query": query, "variables": variables or {}},
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    if "errors" in payload:
        raise RuntimeError(f"Error de GraphQL: {payload['errors']}")
    return payload["data"]


USER_QUERY = """
query($login: String!) {
  user(login: $login) {
    name
    login
    createdAt
    followers { totalCount }
    following { totalCount }
  }
}
"""

REPOS_QUERY = """
query($login: String!, $after: String) {
  user(login: $login) {
    repositories(
      first: 100
      after: $after
      ownerAffiliations: OWNER
      isFork: false
      privacy: PUBLIC
      orderBy: {field: UPDATED_AT, direction: DESC}
    ) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        name
        stargazerCount
        forkCount
        isArchived
        primaryLanguage { name color }
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges {
            size
            node { name color }
          }
        }
      }
    }
  }
}
"""

CONTRIBUTIONS_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      restrictedContributionsCount
      totalPullRequestContributions
      totalIssueContributions
      totalPullRequestReviewContributions
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
            weekday
          }
        }
      }
    }
  }
}
"""


# ---------------------------------------------------------------------------
# Obtención de datos
# ---------------------------------------------------------------------------

def get_user_overview() -> dict:
    data = github_graphql(USER_QUERY, {"login": GITHUB_USERNAME})
    return data["user"]


def get_all_repositories() -> list[dict]:
    """Trae TODOS los repos públicos propios, paginando de 100 en 100."""
    repos = []
    after = None
    while True:
        data = github_graphql(REPOS_QUERY, {"login": GITHUB_USERNAME, "after": after})
        block = data["user"]["repositories"]
        repos.extend(block["nodes"])
        if not block["pageInfo"]["hasNextPage"]:
            break
        after = block["pageInfo"]["endCursor"]
    return repos


def get_contributions_by_year(start_year: int) -> dict[int, dict]:
    """Una query por año (el límite de GraphQL es de 1 año por consulta)."""
    current_year = datetime.now(timezone.utc).year
    results = {}

    for year in range(start_year, current_year + 1):
        date_from = f"{year}-01-01T00:00:00Z"
        date_to = (
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            if year == current_year
            else f"{year}-12-31T23:59:59Z"
        )
        data = github_graphql(
            CONTRIBUTIONS_QUERY,
            {"login": GITHUB_USERNAME, "from": date_from, "to": date_to},
        )
        results[year] = data["user"]["contributionsCollection"]

    return results


# ---------------------------------------------------------------------------
# Agregaciones y datos curiosos
# ---------------------------------------------------------------------------

def aggregate_languages(repos: list[dict], top_n: int = 3) -> list[dict]:
    """Suma bytes de código por lenguaje en todos los repos y calcula %.

    Devuelve los `top_n` lenguajes más usados y agrupa el resto en una
    entrada sintética "Others" (si es que sobra algo por agrupar).
    """
    totals: Counter[str] = Counter()
    colors: dict[str, str] = {}

    for repo in repos:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            totals[name] += edge["size"]
            colors[name] = edge["node"]["color"] or "#858585"

    total_bytes = sum(totals.values()) or 1
    ranked = totals.most_common()  # todos, ordenados de mayor a menor

    top = ranked[:top_n]
    rest = ranked[top_n:]

    languages = [
        {
            "name": name,
            "bytes": size,
            "percent": round(size / total_bytes * 100, 1),
            "color": colors[name],
        }
        for name, size in top
    ]

    if rest:
        others_bytes = sum(size for _, size in rest)
        languages.append(
            {
                "name": "Others",
                "bytes": others_bytes,
                "percent": round(others_bytes / total_bytes * 100, 1),
                "color": "#858585",
            }
        )

    return languages


def flatten_calendar_days(contributions_by_year: dict[int, dict]) -> list[dict]:
    """Aplana los días de contribución de todos los años, ordenados por fecha."""
    days = []
    for year_data in contributions_by_year.values():
        for week in year_data["contributionCalendar"]["weeks"]:
            days.extend(week["contributionDays"])
    days.sort(key=lambda d: d["date"])
    return days


def longest_streak(days: list[dict]) -> int:
    longest = current = 0
    for day in days:
        if day["contributionCount"] > 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def most_active_weekday(days: list[dict]) -> str:
    totals: Counter[int] = Counter()
    for day in days:
        totals[day["weekday"]] += day["contributionCount"]
    if not totals:
        return "N/A"
    weekday_index, _ = totals.most_common(1)[0]
    return WEEKDAYS_EN[weekday_index]


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


def build_commits_chart(commits_by_year: dict[int, int], best_year: int) -> list[dict]:
    """Precalcula x/y/ancho/alto de cada barra para que el template solo dibuje."""
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


def build_language_bars(top_languages: list[dict]) -> list[dict]:
    """Precalcula la posición y el ancho de barra de cada lenguaje.

    Las filas se reparten tipo "space-between" a lo largo de
    LANG_AREA_HEIGHT (mismo alto que el chart de commits), en vez de usar
    una altura de fila fija: con pocos lenguajes quedan más separados, con
    más lenguajes se acomodan igual sin desbordar.

    El lenguaje #1 (índice 0) se marca como `is_top` y recibe una barra
    más gruesa para que el template lo resalte con el gradiente/glow.
    """
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


# ---------------------------------------------------------------------------
# Ensamblado final
# ---------------------------------------------------------------------------

def get_stats() -> dict:
    print(f"Obteniendo datos de GitHub para @{GITHUB_USERNAME}…")

    user = get_user_overview()
    repos = get_all_repositories()

    created_year = int(user["createdAt"][:4])
    contributions_by_year = get_contributions_by_year(created_year)

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

    days = flatten_calendar_days(contributions_by_year)
    created_at = datetime.fromisoformat(user["createdAt"].replace("Z", "+00:00"))
    account_age_days = (datetime.now(timezone.utc) - created_at).days

    top_languages = aggregate_languages(repos)

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
        "commits_by_year": commits_by_year,          # {2022: 340, 2023: 890, ...}
        "commits_this_year": commits_by_year.get(datetime.now().year, 0),
        "best_year": {"year": best_year, "commits": best_year_commits},
        "commits_chart": build_commits_chart(commits_by_year, best_year),

        # Actividad
        "pull_requests": pull_requests,
        "issues": issues,
        "code_reviews": reviews,

        # Lenguajes
        "top_languages": top_languages,               # [{"name","percent","color"}, ...]
        "language_bars": build_language_bars(top_languages),

        # Datos curiosos
        "longest_streak": longest_streak(days),
        "most_active_weekday": most_active_weekday(days),
        "busiest_day": busiest_day(days),
    }


def main() -> None:
    stats = get_stats()

    env = Environment(loader=FileSystemLoader(ASSETS))
    template = env.get_template("github_stats.svg.template")
    svg = template.render(**stats)

    output_path = ASSETS / "github_stats.svg"
    output_path.write_text(svg, encoding="utf-8")

    print(
        f"✅ github_stats.svg actualizado: {stats['commits_total']} commits, "
        f"{stats['repositories']} repos, {len(stats['top_languages'])} lenguajes."
    )


if __name__ == "__main__":
    main()