import csv
import json
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests

GITHUB_TOKEN = "COLOQUE_SEU_TOKEN_AQUI"

HEADERS_GRAPHQL = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Content-Type": "application/json",
}

HEADERS_REST = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
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

SEARCH_DIR = DATASET_DIR / "repositories_searched"
SEARCH_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_PATH = SEARCH_DIR / "repos_search_10001_35000.csv"
REJECTED_OUTPUT_PATH = SEARCH_DIR / "repos_search_10001_35000_rejected.csv"
STATE_PATH = SEARCH_DIR / "search_state_10001_35000.json"

BASE_QUERY = "is:public archived:false has:issues pushed:>2020-01-01"

SEARCH_QUERIES = [

    {"label": "stars_10001_20000", "query": f"{BASE_QUERY} stars:10001..20000", "target": 500},
    {"label": "stars_20001_35000", "query": f"{BASE_QUERY} stars:20001..35000", "target": 500},
]

FIRST = 10
MIN_CONTRIBUTORS = 2

GRAPHQL_QUERY = """
query SearchRepositories($searchQuery: String!, $first: Int!, $after: String) {
  search(query: $searchQuery, type: REPOSITORY, first: $first, after: $after) {
    repositoryCount
    pageInfo {
      hasNextPage
      endCursor
    }
    nodes {
      ... on Repository {
        name
        owner {
          login
        }
        url
        description
        createdAt
        pushedAt
        stargazerCount
        forkCount
        primaryLanguage {
          name
        }
        repositoryTopics(first: 20) {
          nodes {
            topic {
              name
            }
          }
        }
        issues {
          totalCount
        }
        pullRequests {
          totalCount
        }
        releases {
          totalCount
        }
      }
    }
  }
}
"""


def run_graphql_query(query: str, variables: dict, retries: int = 8, base_sleep_seconds: int = 5):
    url = "https://api.github.com/graphql"

    for attempt in range(1, retries + 1):
        try:
            response = requests.post(
                url,
                json={"query": query, "variables": variables},
                headers=HEADERS_GRAPHQL,
                timeout=60,
            )

            if response.status_code == 200:
                data = response.json()

                if "errors" in data:
                    print("Erros retornados pela API GraphQL:")
                    for error in data["errors"]:
                        print(error)
                    return None, response.status_code

                return data, response.status_code

            if response.status_code in {502, 503, 504}:
                sleep_time = base_sleep_seconds * attempt
                print(
                    f"Status code GraphQL: {response.status_code} | "
                    f"tentativa {attempt}/{retries} | nova tentativa em {sleep_time}s"
                )
                time.sleep(sleep_time)
                continue

            print(f"Erro GraphQL | Status code: {response.status_code}")
            print(response.text)
            return None, response.status_code

        except requests.exceptions.RequestException as e:
            sleep_time = base_sleep_seconds * attempt
            print(
                f"Erro de conexão GraphQL: {e} | "
                f"tentativa {attempt}/{retries} | nova tentativa em {sleep_time}s"
            )
            time.sleep(sleep_time)

    print("Falha após múltiplas tentativas na API GraphQL.")
    return None, None


def run_rest_get(url: str, retries: int = 5, base_sleep_seconds: int = 2):
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, headers=HEADERS_REST, timeout=60)

            if response.status_code == 200:
                return response

            if response.status_code in {502, 503, 504}:
                sleep_time = base_sleep_seconds * attempt
                print(
                    f"Status code REST: {response.status_code} | "
                    f"tentativa {attempt}/{retries} | nova tentativa em {sleep_time}s"
                )
                time.sleep(sleep_time)
                continue

            print(f"Erro REST | Status code: {response.status_code}")
            print(response.text)
            return None

        except requests.exceptions.RequestException as e:
            sleep_time = base_sleep_seconds * attempt
            print(
                f"Erro de conexão REST: {e} | "
                f"tentativa {attempt}/{retries} | nova tentativa em {sleep_time}s"
            )
            time.sleep(sleep_time)

    print("Falha após múltiplas tentativas na API REST.")
    return None


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


def read_csv(input_path: Path):
    if not input_path.exists():
        return []

    with input_path.open(mode="r", encoding="utf-8") as csvfile:
        return list(csv.DictReader(csvfile))


def save_to_csv(rows: list[dict], output_path: Path):
    if not rows:
        print(f"Nenhum dado para salvar em {output_path}")
        return

    fieldnames = list(rows[0].keys())

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_name(output_path.stem + "_temp.csv")
    fallback_path = output_path.with_name(output_path.stem + "_fallback.csv")

    try:
        with temp_path.open(mode="w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        temp_path.replace(output_path)
        print(f"CSV salvo/atualizado em: {output_path.resolve()}")

    except OSError as e:
        print(f"Erro ao salvar em {output_path}: {e}")
        print(f"Tentando salvar em fallback: {fallback_path}")

        with fallback_path.open(mode="w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        print(f"CSV salvo em fallback: {fallback_path.resolve()}")


def save_partial_results(approved_rows: list[dict], rejected_rows: list[dict]):
    if approved_rows:
        save_to_csv(approved_rows, OUTPUT_PATH)
    if rejected_rows:
        save_to_csv(rejected_rows, REJECTED_OUTPUT_PATH)


def load_state():
    if not STATE_PATH.exists():
        return {}

    with STATE_PATH.open(mode="r", encoding="utf-8") as file:
        return json.load(file)


def save_state(state: dict):
    temp_path = STATE_PATH.with_name(STATE_PATH.stem + "_temp.json")

    with temp_path.open(mode="w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2)

    temp_path.replace(STATE_PATH)


def load_checkpoint():
    approved_rows = read_csv(OUTPUT_PATH)
    rejected_rows = read_csv(REJECTED_OUTPUT_PATH)

    seen_full_names = set()
    approved_counts_by_label = {}

    for row in approved_rows:
        full_name = row.get("full_name")
        label = row.get("query_label")

        if full_name:
            seen_full_names.add(full_name)

        if label:
            approved_counts_by_label[label] = approved_counts_by_label.get(label, 0) + 1

    for row in rejected_rows:
        full_name = row.get("full_name")
        if full_name:
            seen_full_names.add(full_name)

    return approved_rows, rejected_rows, seen_full_names, approved_counts_by_label


def extract_repositories(nodes: list[dict], query_label: str) -> list[dict]:
    extracted = []

    for repo in nodes:
        topics = []
        if repo.get("repositoryTopics") and repo["repositoryTopics"].get("nodes"):
            topics = [
                node["topic"]["name"]
                for node in repo["repositoryTopics"]["nodes"]
                if node.get("topic") and node["topic"].get("name")
            ]

        extracted.append(
            {
                "query_label": query_label,
                "repository_name": repo["name"],
                "owner_login": repo["owner"]["login"],
                "full_name": f"{repo['owner']['login']}/{repo['name']}",
                "url": repo["url"],
                "description": repo.get("description"),
                "topics": " | ".join(topics),
                "created_at": repo["createdAt"],
                "pushed_at": repo["pushedAt"],
                "stars": repo["stargazerCount"],
                "forks": repo["forkCount"],
                "primary_language": repo["primaryLanguage"]["name"] if repo["primaryLanguage"] else None,
                "issues_total": repo["issues"]["totalCount"],
                "pull_requests_total": repo["pullRequests"]["totalCount"],
                "releases_total": repo["releases"]["totalCount"],
            }
        )

    return extracted


def collect_repositories_for_query(
        query_label: str,
        search_query: str,
        target_repositories: int,
        seen_full_names: set,
        global_approved_rows: list[dict],
        global_rejected_rows: list[dict],
        query_state: dict,
        full_state: dict,
):
    after_cursor = query_state.get("after_cursor")
    total_found = None
    approved_rows = []
    rejected_rows = []
    page = query_state.get("page", 1)
    candidates_evaluated = 0
    current_approved_total = query_state.get("approved_count", 0)

    if query_state.get("done"):
        print(f"\nQuery {query_label} já concluída no estado. Pulando.")
        return {
            "label": query_label,
            "total_found": None,
            "approved_rows": [],
            "rejected_rows": [],
            "candidates_evaluated": 0,
            "truncated": False,
        }

    if current_approved_total >= target_repositories:
        print(f"\nQuery {query_label} já atingiu a meta ({current_approved_total}/{target_repositories}). Marcando como concluída.")
        query_state["done"] = True
        query_state["after_cursor"] = None
        full_state[query_label] = query_state
        save_state(full_state)
        return {
            "label": query_label,
            "total_found": None,
            "approved_rows": [],
            "rejected_rows": [],
            "candidates_evaluated": 0,
            "truncated": False,
        }

    while current_approved_total < target_repositories:
        print("\n==================================================")
        print(f"Query: {query_label}")
        print(f"Página atual: {page}")
        print(f"Aprovados nesta query: {current_approved_total} / {target_repositories}")
        print(f"Candidatos avaliados nesta execução da query: {candidates_evaluated}")
        print("==================================================")

        variables = {
            "searchQuery": search_query,
            "first": FIRST,
            "after": after_cursor,
        }

        result, status_code = run_graphql_query(GRAPHQL_QUERY, variables)

        if not result:
            print(f"\nFalha na coleta da query {query_label}.")
            break

        print(f"Status code GraphQL: {status_code}")

        search_data = result["data"]["search"]

        if total_found is None:
            total_found = search_data["repositoryCount"]
            print(f"Total estimado encontrado pela busca ({query_label}): {total_found}")

        nodes = search_data["nodes"]
        page_rows = extract_repositories(nodes, query_label)

        approved_this_page = 0
        rejected_this_page = 0
        skipped_this_page = 0

        for row in page_rows:
            if row["full_name"] in seen_full_names:
                skipped_this_page += 1
                continue

            seen_full_names.add(row["full_name"])
            candidates_evaluated += 1

            owner = row["owner_login"]
            repo_name = row["repository_name"]

            contributors_count = get_contributors_count(owner, repo_name)
            row["contributors_count"] = contributors_count

            print(
                f"[{query_label} | candidato {candidates_evaluated}] "
                f"{row['full_name']} | contributors: {contributors_count}",
                end=" "
            )

            if contributors_count >= MIN_CONTRIBUTORS:
                approved_rows.append(row)
                global_approved_rows.append(row)
                approved_this_page += 1
                current_approved_total += 1
                print("-> APROVADO")
            else:
                rejected = row.copy()
                rejected["rejection_reasons"] = f"contributors_count < {MIN_CONTRIBUTORS}"
                rejected_rows.append(rejected)
                global_rejected_rows.append(rejected)
                rejected_this_page += 1
                print("-> REJEITADO")

            if current_approved_total >= target_repositories:
                break

            time.sleep(0.2)

        print(f"\nAprovados nesta página ({query_label}): {approved_this_page}")
        print(f"Rejeitados nesta página ({query_label}): {rejected_this_page}")
        print(f"Pulados por já existirem ({query_label}): {skipped_this_page}")
        print(f"Total aprovado acumulado na query ({query_label}): {current_approved_total}/{target_repositories}")

        save_partial_results(global_approved_rows, global_rejected_rows)

        page_info = search_data["pageInfo"]

        query_state["approved_count"] = current_approved_total
        query_state["page"] = page + 1
        query_state["after_cursor"] = page_info["endCursor"] if page_info["hasNextPage"] else None
        full_state[query_label] = query_state
        save_state(full_state)

        if current_approved_total >= target_repositories:
            print(f"\nMeta da query {query_label} atingida.")
            query_state["done"] = True
            query_state["after_cursor"] = None
            full_state[query_label] = query_state
            save_state(full_state)
            break

        if not page_info["hasNextPage"]:
            print(f"\nNão há mais páginas disponíveis para a query {query_label}.")
            query_state["done"] = True
            query_state["after_cursor"] = None
            full_state[query_label] = query_state
            save_state(full_state)
            break

        after_cursor = page_info["endCursor"]
        page += 1

        time.sleep(2)

    truncated = (
            total_found is not None
            and total_found > candidates_evaluated
            and candidates_evaluated >= 900
    )

    return {
        "label": query_label,
        "total_found": total_found,
        "approved_rows": approved_rows,
        "rejected_rows": rejected_rows,
        "candidates_evaluated": candidates_evaluated,
        "truncated": truncated,
    }


def main():
    start_time = time.time()
    start_datetime = datetime.now()

    print(f"Início da execução: {start_datetime.strftime('%d/%m/%Y %H:%M:%S')}")

    all_approved_rows, all_rejected_rows, seen_full_names, approved_counts_by_label = load_checkpoint()
    state = load_state()

    # Inicializa ou atualiza o estado com base no que já existe no CSV
    for query_config in SEARCH_QUERIES:
        label = query_config["label"]
        target = query_config["target"]
        approved_count = approved_counts_by_label.get(label, 0)

        if label not in state:
            state[label] = {
                "after_cursor": None,
                "page": 1,
                "approved_count": approved_count,
                "done": approved_count >= target,
            }
        else:
            state[label]["approved_count"] = approved_count

            if approved_count >= target:
                state[label]["done"] = True
                state[label]["after_cursor"] = None

    save_state(state)

    print("\n=== CHECKPOINT CARREGADO ===")
    print(f"Aprovados já salvos: {len(all_approved_rows)}")
    print(f"Rejeitados já salvos: {len(all_rejected_rows)}")
    print(f"Repositórios já avaliados: {len(seen_full_names)}")
    print("Aprovados por query:")
    for query_config in SEARCH_QUERIES:
        label = query_config["label"]
        print(
            f"  {label}: {state[label].get('approved_count', 0)} / "
            f"{query_config['target']} | done={state[label].get('done', False)}"
        )
    print("============================\n")

    total_candidates_evaluated = 0

    for query_config in SEARCH_QUERIES:
        label = query_config["label"]
        query_state = state[label]

        if query_state.get("done"):
            print(f"\nQuery {label} já concluída no arquivo de estado. Pulando.")
            continue

        result = collect_repositories_for_query(
            query_label=label,
            search_query=query_config["query"],
            target_repositories=query_config["target"],
            seen_full_names=seen_full_names,
            global_approved_rows=all_approved_rows,
            global_rejected_rows=all_rejected_rows,
            query_state=query_state,
            full_state=state,
        )

        total_candidates_evaluated += result["candidates_evaluated"]

        print("\n--------------------------------------------------")
        print(f"Resumo da query {result['label']}:")
        print(f"  Total estimado encontrado: {result['total_found']}")
        print(f"  Candidatos avaliados nesta execução: {result['candidates_evaluated']}")
        print(f"  Aprovados novos nesta execução: {len(result['approved_rows'])}")
        print(f"  Rejeitados novos nesta execução: {len(result['rejected_rows'])}")
        if result.get("truncated"):
            print("  AVISO: busca truncada pelo limite do GitHub Search; a faixa deve ser subdividida.")
        print("--------------------------------------------------\n")

        if result["total_found"] is None and result["candidates_evaluated"] == 0:
            print(f"\nFalha sem progresso na query {label}. O estado foi preservado. Tentando a próxima query.")
            time.sleep(20)
            continue

        print("\n⏳ Pausando 10 segundos antes da próxima query...\n")
        time.sleep(10)

    print("\n================ RESUMO GERAL ================")
    print(f"Total de candidatos avaliados nesta execução: {total_candidates_evaluated}")
    print(f"Total de repositórios aprovados no checkpoint final: {len(all_approved_rows)}")
    print(f"Total de repositórios rejeitados no checkpoint final: {len(all_rejected_rows)}")
    print("=============================================\n")

    print("Exemplos dos 10 primeiros repositórios aprovados:\n")
    for repo in all_approved_rows[:10]:
        print(repo["full_name"])
        print(f"  Query: {repo['query_label']}")
        print(f"  Stars: {repo['stars']}")
        print(f"  Forks: {repo['forks']}")
        print(f"  Issues: {repo['issues_total']}")
        print(f"  PRs: {repo['pull_requests_total']}")
        print(f"  Releases: {repo['releases_total']}")
        print(f"  Linguagem: {repo['primary_language']}")
        print(f"  Description: {repo['description']}")
        print(f"  Topics: {repo['topics']}")
        print(f"  Contributors: {repo['contributors_count']}")
        print("-" * 50)

    save_partial_results(all_approved_rows, all_rejected_rows)

    end_time = time.time()
    end_datetime = datetime.now()

    print(f"\nFim da execução: {end_datetime.strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"Tempo total de execução: {round(end_time - start_time, 2)} segundos")


if __name__ == "__main__":
    main()