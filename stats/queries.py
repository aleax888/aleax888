"""Strings de las queries GraphQL usadas por GitHubClient.

Se mantienen aparte del cliente para que este último no se llene de texto
y sea más fácil de leer.
"""

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

# Nota: se quitó `primaryLanguage` porque ya no se usa — el cálculo de
# lenguajes principales ahora pondera por % de bytes DENTRO de cada repo
# (ver StatsAggregator.aggregate_languages), no por el lenguaje dominante
# ni por bytes crudos globales.
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
