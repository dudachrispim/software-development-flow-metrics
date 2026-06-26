from pathlib import Path
import time

import numpy as np
import pandas as pd
import requests


GITHUB_TOKEN = "COLOQUE_SEU_TOKEN_AQUI"

MAX_RETRIES = 3
RETRY_WAIT_SECONDS = 20
SAVE_EVERY = 100



def find_project_root(start: Path) -> Path:
    current = start.resolve()
    for parent in [current, *current.parents]:
        if (parent / "data").exists() and parent.name == "metrics-decision-impact":
            return parent
    raise RuntimeError("Raiz do projeto não encontrada.")

PROJECT_ROOT = find_project_root(Path(__file__))
DATASET_DIR = PROJECT_ROOT / "data" / "dataset_10000_stars"

PRS_PATH = DATASET_DIR / "repositories_metrics_clean" / "pull_requests_detailed_clean.csv"
RELEASES_PATH = DATASET_DIR / "repositories_metrics_clean" / "releases_detailed_clean.csv"

OUTPUT_DIR = DATASET_DIR / "repositories_metrics_final"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_PATH = OUTPUT_DIR / "flow_stage_metrics.csv"
ERRORS_PATH = OUTPUT_DIR / "flow_stage_metrics_errors.csv"


GRAPHQL_URL = "https://api.github.com/graphql"

QUERY = """
query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      number
      createdAt
      mergedAt
      closingIssuesReferences(first: 20) {
        nodes {
          number
          createdAt
          closedAt
          title
          url
        }
      }
    }
  }
}
"""


def parse_datetime(value):
    if pd.isna(value):
        return None
    return pd.to_datetime(value, utc=True, errors="coerce")


def split_repo(full_name: str):
    owner, repo = full_name.split("/", 1)
    return owner, repo


def find_pr_number_column(df):
    candidates = [
        "number",
        "pr_number",
        "pull_request_number",
    ]

    for col in candidates:
        if col in df.columns:
            return col

    raise KeyError(
        "Coluna de número do PR não encontrada. "
        "Esperado: number, pr_number ou pull_request_number."
    )


def save_progress(rows, errors):
    if rows:
        pd.DataFrame(rows).to_csv(
            OUTPUT_PATH,
            index=False,
            encoding="utf-8-sig"
        )

    if errors:
        pd.DataFrame(errors).to_csv(
            ERRORS_PATH,
            index=False,
            encoding="utf-8-sig"
        )


def load_existing_progress():
    processed = set()
    rows = []
    errors = []

    if OUTPUT_PATH.exists():
        existing_df = pd.read_csv(OUTPUT_PATH)

        if not existing_df.empty:
            rows = existing_df.to_dict("records")

            processed = set(
                zip(
                    existing_df["full_name"],
                    existing_df["pr_number"]
                )
            )

        print(f"Progresso carregado: {len(processed)} PRs já processados.")

    if ERRORS_PATH.exists():
        errors_df = pd.read_csv(ERRORS_PATH)

        if not errors_df.empty:
            errors = errors_df.to_dict("records")

        print(f"Erros carregados: {len(errors)} registros.")

    return processed, rows, errors


def github_graphql_request(owner, repo, pr_number):
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "query": QUERY,
        "variables": {
            "owner": owner,
            "name": repo,
            "number": int(pr_number),
        },
    }

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(
                GRAPHQL_URL,
                json=payload,
                headers=headers,
                timeout=30,
            )

            if response.status_code == 403:
                print(
                    f"Rate limit ou acesso negado em {owner}/{repo} PR #{pr_number}. "
                    f"Aguardando 60 segundos..."
                )
                time.sleep(60)
                last_error = f"HTTP 403: {response.text[:300]}"
                continue

            if response.status_code in [500, 502, 503, 504]:
                print(
                    f"Erro temporário HTTP {response.status_code} "
                    f"em {owner}/{repo} PR #{pr_number}. "
                    f"Tentativa {attempt}/{MAX_RETRIES}."
                )
                time.sleep(RETRY_WAIT_SECONDS * attempt)
                last_error = f"HTTP {response.status_code}: {response.text[:300]}"
                continue

            response.raise_for_status()
            data = response.json()

            if "errors" in data:
                last_error = str(data["errors"])[:500]

                print(
                    f"Erro GraphQL em {owner}/{repo} PR #{pr_number}. "
                    f"Tentativa {attempt}/{MAX_RETRIES}: {last_error}"
                )

                time.sleep(RETRY_WAIT_SECONDS * attempt)
                continue

            return data

        except Exception as e:
            last_error = str(e)

            print(
                f"Falha em {owner}/{repo} PR #{pr_number}. "
                f"Tentativa {attempt}/{MAX_RETRIES}: {last_error}"
            )

            time.sleep(RETRY_WAIT_SECONDS * attempt)

    raise RuntimeError(last_error)


def get_next_release_days(full_name, pr_merged, release_map):
    repo_releases = release_map.get(full_name)

    if repo_releases is None or len(repo_releases) == 0:
        return np.nan

    pr_merged = pd.Timestamp(pr_merged)

    if pr_merged.tzinfo is None:
        pr_merged = pr_merged.tz_localize("UTC")
    else:
        pr_merged = pr_merged.tz_convert("UTC")

    for release_date in repo_releases:
        release_date = pd.Timestamp(release_date)

        if release_date.tzinfo is None:
            release_date = release_date.tz_localize("UTC")
        else:
            release_date = release_date.tz_convert("UTC")

        if release_date >= pr_merged:
            delta = (release_date - pr_merged).total_seconds() / 86400
            return delta

    return np.nan


def process_pr(row, pr_number_col, release_map):
    full_name = row["full_name"]
    pr_number = int(row[pr_number_col])

    owner, repo = split_repo(full_name)

    data = github_graphql_request(
        owner,
        repo,
        pr_number
    )

    pr_data = (
        data.get("data", {})
        .get("repository", {})
        .get("pullRequest")
    )

    if pr_data is None:
        raise ValueError("PR não encontrado na resposta da API.")

    pr_created = parse_datetime(pr_data.get("createdAt"))
    pr_merged = parse_datetime(pr_data.get("mergedAt"))

    if pr_created is None or pr_merged is None:
        raise ValueError("PR sem createdAt ou mergedAt válido.")

    pr_to_merge_days = (
            (pr_merged - pr_created).total_seconds() / 86400
    )

    merge_to_release_days = get_next_release_days(
        full_name,
        pr_merged,
        release_map
    )

    issues = (
        pr_data.get("closingIssuesReferences", {})
        .get("nodes", [])
    )

    result_rows = []

    if not issues:
        result_rows.append({
            "full_name": full_name,
            "pr_number": pr_number,
            "issue_number": np.nan,
            "issue_to_pr_days": np.nan,
            "pr_to_merge_days": pr_to_merge_days,
            "merge_to_release_days": merge_to_release_days,
        })

    else:
        for issue in issues:
            issue_created = parse_datetime(issue.get("createdAt"))
            issue_to_pr_days = np.nan

            if issue_created is not None:
                delta = (
                                pr_created - issue_created
                        ).total_seconds() / 86400

                if delta >= 0:
                    issue_to_pr_days = delta

            result_rows.append({
                "full_name": full_name,
                "pr_number": pr_number,
                "issue_number": issue.get("number"),
                "issue_to_pr_days": issue_to_pr_days,
                "pr_to_merge_days": pr_to_merge_days,
                "merge_to_release_days": merge_to_release_days,
            })

    return result_rows


def main():
    if not GITHUB_TOKEN or GITHUB_TOKEN == "COLOQUE_SEU_TOKEN_AQUI":
        raise ValueError("Coloque seu token do GitHub na variável GITHUB_TOKEN dentro do script.")

    print("Lendo datasets...")

    prs_df = pd.read_csv(PRS_PATH)
    releases_df = pd.read_csv(RELEASES_PATH)

    pr_number_col = find_pr_number_column(prs_df)

    print("Preparando releases...")

    releases_df["published_at"] = pd.to_datetime(
        releases_df["published_at"],
        utc=True,
        errors="coerce"
    )

    releases_df = releases_df.dropna(
        subset=["full_name", "published_at"]
    )

    release_map = {
    repo: list(group["published_at"].sort_values())
    for repo, group in releases_df.groupby("full_name")
    }

    processed, rows, errors = load_existing_progress()

    total = len(prs_df)

    print(f"Total de PRs no arquivo: {total}")
    print(f"Restantes aproximados: {total - len(processed)}")

    for idx, row in prs_df.iterrows():
        full_name = row["full_name"]
        pr_number = int(row[pr_number_col])
        key = (full_name, pr_number)

        if key in processed:
            continue

        try:
            new_rows = process_pr(
                row,
                pr_number_col,
                release_map
            )

            rows.extend(new_rows)
            processed.add(key)

        except Exception as e:
            error_row = {
                "full_name": full_name,
                "pr_number": pr_number,
                "error": str(e)
            }

            errors.append(error_row)
            processed.add(key)

            print(
                f"Pulando {full_name} PR #{pr_number} após falhas: {e}"
            )

        if idx % SAVE_EVERY == 0:
            print(
                f"[{idx}/{total}] "
                f"Processados nesta base: {len(processed)} | "
                f"Linhas geradas: {len(rows)} | "
                f"Erros: {len(errors)}"
            )

            save_progress(rows, errors)

    save_progress(rows, errors)

    print("\n===================================")
    print("FINALIZADO")
    print("===================================")

    print(f"Arquivo salvo em:\n{OUTPUT_PATH.resolve()}")

    if ERRORS_PATH.exists():
        print(f"Arquivo de erros salvo em:\n{ERRORS_PATH.resolve()}")

    output_df = pd.DataFrame(rows)

    print(f"\nTotal de linhas: {len(output_df)}")

    if not output_df.empty:
        print("\nResumo:")
        print(
            output_df[
                [
                    "issue_to_pr_days",
                    "pr_to_merge_days",
                    "merge_to_release_days"
                ]
            ].describe()
        )


if __name__ == "__main__":
    main()