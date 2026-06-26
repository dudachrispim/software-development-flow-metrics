from pathlib import Path
import time
import pandas as pd
import requests


GITHUB_TOKEN = "COLOQUE_SEU_TOKEN_AQUI"

def find_project_root(start: Path) -> Path:
    current = start.resolve()
    for parent in [current, *current.parents]:
        if (parent / "data").exists() and parent.name == "metrics-decision-impact":
            return parent
    raise RuntimeError("Raiz do projeto não encontrada.")

PROJECT_ROOT = find_project_root(Path(__file__))
DATASET_DIR = PROJECT_ROOT / "data" / "dataset_10000_stars"

PRS_PATH = DATASET_DIR / "repositories_metrics_clean" / "pull_requests_detailed_clean.csv"

OUTPUT_DIR = DATASET_DIR / "repositories_metrics_final"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_PATH = OUTPUT_DIR / "issue_pr_links_batched.csv"
PROGRESS_PATH = OUTPUT_DIR / "issue_pr_links_progress.csv"
ERRORS_PATH = OUTPUT_DIR / "issue_pr_links_errors.csv"

GRAPHQL_URL = "https://api.github.com/graphql"

SAVE_EVERY_REPOS = 1
WAIT_SECONDS = 2
MAX_RETRIES = 3


QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(first: 100, after: $cursor, states: MERGED, orderBy: {field: CREATED_AT, direction: ASC}) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        number
        createdAt
        mergedAt
        url
        closingIssuesReferences(first: 20) {
          nodes {
            number
            title
            createdAt
            closedAt
            url
          }
        }
      }
    }
  }
}
"""


def split_repo(full_name: str):
    owner, repo = full_name.split("/", 1)
    return owner, repo


def graphql_request(owner, repo, cursor):
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "query": QUERY,
        "variables": {
            "owner": owner,
            "name": repo,
            "cursor": cursor,
        },
    }

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(
                GRAPHQL_URL,
                json=payload,
                headers=headers,
                timeout=40,
            )

            if response.status_code == 403:
                print("Rate limit/acesso negado. Aguardando 60s...")
                time.sleep(60)
                last_error = response.text[:300]
                continue

            if response.status_code in [500, 502, 503, 504]:
                print(f"Erro temporário {response.status_code}. Tentativa {attempt}/{MAX_RETRIES}")
                time.sleep(20 * attempt)
                last_error = response.text[:300]
                continue

            response.raise_for_status()
            data = response.json()

            if "errors" in data:
                last_error = str(data["errors"])[:500]
                print(f"Erro GraphQL. Tentativa {attempt}/{MAX_RETRIES}: {last_error}")
                time.sleep(20 * attempt)
                continue

            return data

        except Exception as e:
            last_error = str(e)
            print(f"Falha. Tentativa {attempt}/{MAX_RETRIES}: {last_error}")
            time.sleep(20 * attempt)

    raise RuntimeError(last_error)


def load_existing():
    rows = []
    errors = []
    completed_repos = set()

    if OUTPUT_PATH.exists():
        df = pd.read_csv(OUTPUT_PATH)
        rows = df.to_dict("records")
        print(f"Links já salvos: {len(rows)}")

    if ERRORS_PATH.exists():
        err_df = pd.read_csv(ERRORS_PATH)
        errors = err_df.to_dict("records")
        print(f"Erros já salvos: {len(errors)}")

    if PROGRESS_PATH.exists():
        progress_df = pd.read_csv(PROGRESS_PATH)
        completed_repos = set(progress_df.loc[progress_df["status"] == "completed", "full_name"])
        print(f"Repositórios completos já processados: {len(completed_repos)}")

    return rows, errors, completed_repos


def save_all(rows, errors, progress_rows):
    pd.DataFrame(rows).to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    pd.DataFrame(errors).to_csv(ERRORS_PATH, index=False, encoding="utf-8-sig")
    pd.DataFrame(progress_rows).to_csv(PROGRESS_PATH, index=False, encoding="utf-8-sig")


def main():
    if not GITHUB_TOKEN or GITHUB_TOKEN == "COLOQUE_SEU_TOKEN_AQUI":
        raise ValueError("Coloque seu token no GITHUB_TOKEN.")

    prs_df = pd.read_csv(PRS_PATH)
    repos = sorted(prs_df["full_name"].dropna().unique())

    rows, errors, completed_repos = load_existing()
    progress_rows = [
        {"full_name": repo, "status": "completed"}
        for repo in completed_repos
    ]

    print(f"Total de repositórios: {len(repos)}")
    start_time = time.time()

    for repo_index, full_name in enumerate(repos, start=1):
        if full_name in completed_repos:
            continue

        print(f"\n[{repo_index}/{len(repos)}] Processando {full_name}")

        try:
            owner, repo = split_repo(full_name)
            cursor = None
            page = 0
            repo_links = 0
            repo_prs = 0

            while True:
                data = graphql_request(owner, repo, cursor)

                pr_connection = (
                    data.get("data", {})
                    .get("repository", {})
                    .get("pullRequests", {})
                )

                nodes = pr_connection.get("nodes", [])
                page_info = pr_connection.get("pageInfo", {})

                page += 1
                repo_prs += len(nodes)

                for pr in nodes:
                    issues = (
                        pr.get("closingIssuesReferences", {})
                        .get("nodes", [])
                    )

                    for issue in issues:
                        rows.append({
                            "full_name": full_name,
                            "pr_number": pr.get("number"),
                            "pr_created_at": pr.get("createdAt"),
                            "pr_merged_at": pr.get("mergedAt"),
                            "pr_url": pr.get("url"),
                            "issue_number": issue.get("number"),
                            "issue_title": issue.get("title"),
                            "issue_created_at": issue.get("createdAt"),
                            "issue_closed_at": issue.get("closedAt"),
                            "issue_url": issue.get("url"),
                        })
                        repo_links += 1

                print(
                    f"  Página {page} | PRs lidos: {repo_prs} | "
                    f"links issue↔PR: {repo_links}"
                )

                if not page_info.get("hasNextPage"):
                    break

                cursor = page_info.get("endCursor")
                time.sleep(WAIT_SECONDS)

            completed_repos.add(full_name)
            progress_rows.append({"full_name": full_name, "status": "completed"})

            save_all(rows, errors, progress_rows)

            elapsed = time.time() - start_time
            repos_done = len(completed_repos)
            avg_per_repo = elapsed / repos_done if repos_done else 0
            remaining = len(repos) - repos_done
            estimated_hours = (avg_per_repo * remaining) / 3600

            print(
                f"Concluído {full_name} | PRs: {repo_prs} | links: {repo_links} | "
                f"estimativa restante: {estimated_hours:.2f} horas"
            )

        except Exception as e:
            print(f"Erro em {full_name}: {e}")

            errors.append({
                "full_name": full_name,
                "error": str(e),
            })

            save_all(rows, errors, progress_rows)
            continue

    print("\nFINALIZADO")
    print(f"Arquivo salvo em: {OUTPUT_PATH.resolve()}")
    print(f"Links encontrados: {len(rows)}")


if __name__ == "__main__":
    main()