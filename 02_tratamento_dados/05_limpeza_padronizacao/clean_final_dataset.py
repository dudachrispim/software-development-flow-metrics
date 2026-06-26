import csv
from pathlib import Path


def find_project_root(start: Path) -> Path:
    current = start.resolve()
    for parent in [current, *current.parents]:
        if (parent / "data").exists() and parent.name == "metrics-decision-impact":
            return parent
    raise RuntimeError("Raiz do projeto não encontrada.")

PROJECT_ROOT = find_project_root(Path(__file__))
DATASET_DIR = PROJECT_ROOT / "data" / "dataset_10000_stars"

COLLECTED_DIR = DATASET_DIR / "repositories_metrics_collected"
CLEAN_DIR = DATASET_DIR / "repositories_metrics_clean"

CLEAN_DIR.mkdir(parents=True, exist_ok=True)

REPO_SUMMARY_PATH = COLLECTED_DIR / "repositories_detailed_summary.csv"
ISSUES_PATH = COLLECTED_DIR / "issues_detailed.csv"
PRS_PATH = COLLECTED_DIR / "pull_requests_detailed.csv"
RELEASES_PATH = COLLECTED_DIR / "releases_detailed.csv"
PROJECTS_PATH = COLLECTED_DIR / "projects_detailed.csv"

OUTPUT_REPO_SUMMARY = CLEAN_DIR / "repositories_detailed_summary_clean.csv"
OUTPUT_ISSUES = CLEAN_DIR / "issues_detailed_clean.csv"
OUTPUT_PRS = CLEAN_DIR / "pull_requests_detailed_clean.csv"
OUTPUT_RELEASES = CLEAN_DIR / "releases_detailed_clean.csv"
OUTPUT_PROJECTS = CLEAN_DIR / "projects_detailed_clean.csv"


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        print(f"Arquivo não encontrado: {path.resolve()}")
        return []

    with path.open(mode="r", encoding="utf-8") as csvfile:
        return list(csv.DictReader(csvfile))


def write_csv(rows: list[dict], path: Path):
    if not rows:
        print(f"Nenhum dado para salvar em {path.resolve()}")
        return

    fieldnames = list(rows[0].keys())

    with path.open(mode="w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Arquivo salvo em: {path.resolve()}")


def safe_int(value) -> int:
    try:
        if value is None:
            return 0
        value_str = str(value).strip()
        if value_str == "" or value_str.lower() == "none":
            return 0
        return int(value_str)
    except (ValueError, TypeError):
        return 0


def identify_inconsistent_repositories(repo_rows: list[dict]) -> set[str]:
    inconsistent_repos = set()

    for row in repo_rows:
        full_name = row.get("full_name")
        if not full_name:
            continue

        issues_initial = safe_int(row.get("issues_total_initial"))
        prs_initial = safe_int(row.get("pull_requests_total_initial"))
        releases_initial = safe_int(row.get("releases_total_initial"))

        issues_collected = safe_int(row.get("issues_collected"))
        prs_collected = safe_int(row.get("prs_collected"))
        releases_collected = safe_int(row.get("releases_collected"))

        inconsistent = False

        if issues_initial > 0 and issues_collected == 0:
            inconsistent = True

        if prs_initial > 0 and prs_collected == 0:
            inconsistent = True

        if releases_initial > 0 and releases_collected == 0:
            inconsistent = True

        if inconsistent:
            inconsistent_repos.add(full_name)

    return inconsistent_repos


def filter_rows_by_repository(rows: list[dict], inconsistent_repos: set[str]) -> list[dict]:
    filtered = []
    for row in rows:
        full_name = row.get("full_name")
        if full_name not in inconsistent_repos:
            filtered.append(row)
    return filtered


def main():
    print("Lendo arquivos...")
    repo_rows = read_csv(REPO_SUMMARY_PATH)
    issues_rows = read_csv(ISSUES_PATH)
    pr_rows = read_csv(PRS_PATH)
    release_rows = read_csv(RELEASES_PATH)
    project_rows = read_csv(PROJECTS_PATH)

    if not repo_rows:
        print("Arquivo de resumo não encontrado ou vazio.")
        return

    inconsistent_repos = identify_inconsistent_repositories(repo_rows)

    print("\n=== LIMPEZA FINAL DO DATASET ===")
    print(f"Total de repositórios no summary original: {len(repo_rows)}")
    print(f"Total de repositórios inconsistentes identificados: {len(inconsistent_repos)}")

    if inconsistent_repos:
        print("\nExemplos de repositórios inconsistentes:")
        for repo in list(sorted(inconsistent_repos))[:10]:
            print(f"- {repo}")

    clean_repo_rows = filter_rows_by_repository(repo_rows, inconsistent_repos)
    clean_issues_rows = filter_rows_by_repository(issues_rows, inconsistent_repos)
    clean_pr_rows = filter_rows_by_repository(pr_rows, inconsistent_repos)
    clean_release_rows = filter_rows_by_repository(release_rows, inconsistent_repos)
    clean_project_rows = filter_rows_by_repository(project_rows, inconsistent_repos)

    print("\n=== TAMANHO DOS ARQUIVOS LIMPOS ===")
    print(f"Repositórios: {len(clean_repo_rows)}")
    print(f"Issues: {len(clean_issues_rows)}")
    print(f"PRs: {len(clean_pr_rows)}")
    print(f"Releases: {len(clean_release_rows)}")
    print(f"Projects: {len(clean_project_rows)}")

    write_csv(clean_repo_rows, OUTPUT_REPO_SUMMARY)
    write_csv(clean_issues_rows, OUTPUT_ISSUES)
    write_csv(clean_pr_rows, OUTPUT_PRS)
    write_csv(clean_release_rows, OUTPUT_RELEASES)

    if project_rows:
        write_csv(clean_project_rows, OUTPUT_PROJECTS)


if __name__ == "__main__":
    main()