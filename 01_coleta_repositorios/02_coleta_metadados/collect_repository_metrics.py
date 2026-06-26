import csv
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests


GITHUB_TOKEN = "COLOQUE_SEU_TOKEN_AQUI"

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/vnd.github+json",
}

def find_project_root(start: Path) -> Path:
    current = start.resolve()
    for parent in [current, *current.parents]:
        if (parent / "data").exists() and parent.name == "metrics-decision-impact":
            return parent
    raise RuntimeError("Raiz do projeto não encontrada.")

PROJECT_ROOT = find_project_root(Path(__file__))
DATASET_DIR = PROJECT_ROOT / "data" / "dataset_10000_stars"

INPUT_PATH = DATASET_DIR / "repositories_filtered" / "repositories_filtered.csv"

OUTPUT_REPO_SUMMARY = DATASET_DIR / "repositories_metrics_collected" / "repositories_detailed_summary.csv"
OUTPUT_ISSUES = DATASET_DIR / "repositories_metrics_collected" / "issues_detailed.csv"
OUTPUT_PRS = DATASET_DIR / "repositories_metrics_collected" / "pull_requests_detailed.csv"
OUTPUT_RELEASES = DATASET_DIR / "repositories_metrics_collected" / "releases_detailed.csv"
OUTPUT_PROJECTS = DATASET_DIR / "repositories_metrics_collected" / "projects_detailed.csv"

OUTPUT_REJECTED = DATASET_DIR / "repositories_filtered" / "repositories_rejected_contributors_collect.csv"

OUTPUT_REPO_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
MIN_CONTRIBUTORS = 2

# QUERIES GRAPHQL

ISSUES_QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    issues(first: 100, after: $cursor, orderBy: {field: CREATED_AT, direction: ASC}) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        number
        createdAt
        closedAt
        state
        labels(first: 20) {
          nodes {
            name
          }
        }
      }
    }
  }
}
"""

PRS_QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(first: 100, after: $cursor, orderBy: {field: CREATED_AT, direction: ASC}) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        number
        createdAt
        mergedAt
        closedAt
        state
        additions
        deletions
        changedFiles
      }
    }
  }
}
"""

RELEASES_QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    releases(first: 100, after: $cursor, orderBy: {field: CREATED_AT, direction: ASC}) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        name
        tagName
        createdAt
        publishedAt
        isDraft
        isPrerelease
      }
    }
  }
}
"""

PROJECTS_QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    projectsV2(first: 100, after: $cursor, orderBy: {field: TITLE, direction: ASC}) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        id
        number
        title
        closed
        public
        items(first: 1) {
          totalCount
        }
      }
    }
  }
}
"""

# FUNÇÕES AUXILIARES DE REQUISIÇÃO

def run_graphql_query(query: str, variables: dict, retries: int = 3, sleep_seconds: int = 2):
    url = "https://api.github.com/graphql"

    for attempt in range(1, retries + 1):
        try:
            response = requests.post(
                url,
                json={"query": query, "variables": variables},
                headers=HEADERS,
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()
                if "errors" in data:
                    print("Erros GraphQL:", data["errors"])
                    return None
                return data

            if response.status_code in {502, 503, 504}:
                print(f"Erro temporário GraphQL (tentativa {attempt}). Tentando novamente...")
                time.sleep(sleep_seconds)
                continue

            print("Erro GraphQL:", response.status_code, response.text)
            return None

        except requests.exceptions.RequestException as e:
            print(f"Erro de conexão GraphQL (tentativa {attempt}): {e}")
            time.sleep(sleep_seconds)

    return None


def run_rest_get(url: str, retries: int = 3, sleep_seconds: int = 2):
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)

            if response.status_code == 200:
                return response

            if response.status_code in {502, 503, 504}:
                print(f"Erro temporário REST (tentativa {attempt}). Tentando novamente...")
                time.sleep(sleep_seconds)
                continue

            print("Erro REST:", response.status_code, response.text)
            return None

        except requests.exceptions.RequestException as e:
            print(f"Erro de conexão REST (tentativa {attempt}): {e}")
            time.sleep(sleep_seconds)

    return None


def read_csv(input_path: Path):
    with input_path.open(mode="r", encoding="utf-8") as csvfile:
        return list(csv.DictReader(csvfile))


def write_csv(rows: list[dict], output_path: Path):
    if not rows:
        print(f"Nenhum dado para salvar em {output_path}")
        return

    fieldnames = list(rows[0].keys())
    with output_path.open(mode="w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Arquivo salvo em: {output_path.resolve()}")

# CONTRIBUTOR COUNT (REST)

def extract_last_page_from_link(link_header: str):
    if not link_header:
        return None

    parts = link_header.split(",")
    for part in parts:
        if 'rel="last"' in part:
            url_part = part.split(";")[0].strip().strip("<>").strip()
            parsed = urlparse(url_part)
            page = parse_qs(parsed.query).get("page")
            if page:
                return int(page[0])
    return None


def get_contributors_count(owner: str, repo: str) -> int:
    url = f"https://api.github.com/repos/{owner}/{repo}/contributors?per_page=1&anon=true"
    response = run_rest_get(url)

    if response is None:
        return 0

    link_header = response.headers.get("Link")
    last_page = extract_last_page_from_link(link_header)

    if last_page is not None:
        return last_page

    data = response.json()
    return len(data)

# COLETA PAGINADA

def collect_paginated_nodes(owner: str, repo: str, query: str, root_field: str):
    all_nodes = []
    cursor = None

    while True:
        variables = {
            "owner": owner,
            "name": repo,
            "cursor": cursor,
        }

        data = run_graphql_query(query, variables)
        if not data:
            break

        container = data["data"]["repository"][root_field]
        nodes = container["nodes"]
        page_info = container["pageInfo"]

        all_nodes.extend(nodes)

        if not page_info["hasNextPage"]:
            break

        cursor = page_info["endCursor"]
        time.sleep(0.3)

    return all_nodes

# TRANSFORMAÇÃO DOS DADOS

def transform_issue_rows(full_name: str, issues: list[dict]) -> list[dict]:
    rows = []
    for issue in issues:
        labels = [label["name"] for label in issue["labels"]["nodes"]]
        rows.append({
            "full_name": full_name,
            "issue_number": issue["number"],
            "created_at": issue["createdAt"],
            "closed_at": issue["closedAt"],
            "state": issue["state"],
            "labels": " | ".join(labels),
        })
    return rows


def transform_pr_rows(full_name: str, prs: list[dict]) -> list[dict]:
    rows = []
    for pr in prs:
        rows.append({
            "full_name": full_name,
            "pr_number": pr["number"],
            "created_at": pr["createdAt"],
            "merged_at": pr["mergedAt"],
            "closed_at": pr["closedAt"],
            "state": pr["state"],
            "additions": pr["additions"],
            "deletions": pr["deletions"],
            "changed_files": pr["changedFiles"],
        })
    return rows


def transform_release_rows(full_name: str, releases: list[dict]) -> list[dict]:
    rows = []
    for release in releases:
        rows.append({
            "full_name": full_name,
            "release_name": release["name"],
            "tag_name": release["tagName"],
            "created_at": release["createdAt"],
            "published_at": release["publishedAt"],
            "is_draft": release["isDraft"],
            "is_prerelease": release["isPrerelease"],
        })
    return rows


def transform_project_rows(full_name: str, projects: list[dict]) -> list[dict]:
    rows = []
    for project in projects:
        rows.append({
            "full_name": full_name,
            "project_id": project["id"],
            "project_number": project["number"],
            "project_title": project["title"],
            "closed": project["closed"],
            "public": project["public"],
            "items_total": project["items"]["totalCount"],
        })
    return rows

# EXECUÇÃO PRINCIPAL

def main():
    start_time = time.time()
    start_datetime = datetime.now()

    print(f"Início da execução: {start_datetime.strftime('%d/%m/%Y %H:%M:%S')}")

    if not INPUT_PATH.exists():
        print(f"Arquivo de entrada não encontrado: {INPUT_PATH.resolve()}")
        return

    repositories = read_csv(INPUT_PATH)

    repo_summary_rows = []
    issue_rows = []
    pr_rows = []
    release_rows = []
    project_rows = []
    rejected_rows = []

    total = len(repositories)
    print(f"Total de repositórios para coleta detalhada: {total}\n")

    for index, repo in enumerate(repositories, start=1):
        full_name = repo["full_name"]
        owner, repo_name = full_name.split("/")

        print(f"[{index}/{total}] Processando {full_name}...")

        contributors_count = get_contributors_count(owner, repo_name)
        print(f"  Contributors: {contributors_count}")

        if contributors_count < MIN_CONTRIBUTORS:
            rejected = repo.copy()
            rejected["rejection_reasons"] = f"contributors_count < {MIN_CONTRIBUTORS}"
            rejected["contributors_count"] = contributors_count
            rejected_rows.append(rejected)
            print("  Repositório rejeitado por número insuficiente de contributors.\n")
            continue

        issues = collect_paginated_nodes(owner, repo_name, ISSUES_QUERY, "issues")
        prs = collect_paginated_nodes(owner, repo_name, PRS_QUERY, "pullRequests")
        releases = collect_paginated_nodes(owner, repo_name, RELEASES_QUERY, "releases")
        projects = collect_paginated_nodes(owner, repo_name, PROJECTS_QUERY, "projectsV2")

        projects_v2_count = len(projects)
        projects_v2_items_total = sum(
            project["items"]["totalCount"] for project in projects
        )

        repo_summary_rows.append({
            "full_name": full_name,
            "owner_login": owner,
            "repository_name": repo_name,
            "stars": repo["stars"],
            "forks": repo["forks"],
            "primary_language": repo["primary_language"],
            "issues_total_initial": repo["issues_total"],
            "pull_requests_total_initial": repo["pull_requests_total"],
            "releases_total_initial": repo["releases_total"],
            "contributors_count": contributors_count,
            "issues_collected": len(issues),
            "prs_collected": len(prs),
            "releases_collected": len(releases),
            "projects_v2_count": projects_v2_count,
            "projects_v2_items_total": projects_v2_items_total,
        })

        issue_rows.extend(transform_issue_rows(full_name, issues))
        pr_rows.extend(transform_pr_rows(full_name, prs))
        release_rows.extend(transform_release_rows(full_name, releases))
        project_rows.extend(transform_project_rows(full_name, projects))

        print(
            f"  Issues coletadas: {len(issues)} | "
            f"PRs coletadas: {len(prs)} | "
            f"Releases coletadas: {len(releases)} | "
            f"Projects V2: {projects_v2_count} | "
            f"Itens em projects: {projects_v2_items_total}\n"
        )

        time.sleep(0.5)

    print("\n=== RESUMO FINAL ===")
    print(f"Repositórios aprovados para coleta detalhada: {len(repo_summary_rows)}")
    print(f"Repositórios rejeitados por contributors: {len(rejected_rows)}")
    print(f"Issues detalhadas coletadas: {len(issue_rows)}")
    print(f"Pull requests detalhadas coletadas: {len(pr_rows)}")
    print(f"Releases detalhadas coletadas: {len(release_rows)}")
    print(f"Projects V2 detalhados coletados: {len(project_rows)}\n")

    if repo_summary_rows:
        write_csv(repo_summary_rows, OUTPUT_REPO_SUMMARY)

    if issue_rows:
        write_csv(issue_rows, OUTPUT_ISSUES)

    if pr_rows:
        write_csv(pr_rows, OUTPUT_PRS)

    if release_rows:
        write_csv(release_rows, OUTPUT_RELEASES)

    if project_rows:
        write_csv(project_rows, OUTPUT_PROJECTS)

    if rejected_rows:
        write_csv(rejected_rows, OUTPUT_REJECTED)

    end_time = time.time()
    end_datetime = datetime.now()

    print(f"\nFim da execução: {end_datetime.strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"Tempo total de execução: {round(end_time - start_time, 2)} segundos")


if __name__ == "__main__":
    main()
