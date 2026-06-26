import csv
from collections import Counter
from pathlib import Path


def find_project_root(start: Path) -> Path:
    current = start.resolve()
    for parent in [current, *current.parents]:
        if (parent / "data").exists() and parent.name == "metrics-decision-impact":
            return parent
    raise RuntimeError("Raiz do projeto não encontrada.")

PROJECT_ROOT = find_project_root(Path(__file__))
DATASET_DIR = PROJECT_ROOT / "data" / "dataset_10000_stars"

REPO_SUMMARY_PATH = DATASET_DIR / "repositories_metrics_collected" / "repositories_detailed_summary.csv"
ISSUES_PATH = DATASET_DIR / "repositories_metrics_collected" / "issues_detailed.csv"
PRS_PATH = DATASET_DIR / "repositories_metrics_collected" / "pull_requests_detailed.csv"
RELEASES_PATH = DATASET_DIR / "repositories_metrics_collected" / "releases_detailed.csv"
PROJECTS_PATH = DATASET_DIR / "repositories_metrics_collected" / "projects_detailed.csv"


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        print(f"Arquivo não encontrado: {path.resolve()}")
        return []

    with path.open(mode="r", encoding="utf-8") as csvfile:
        return list(csv.DictReader(csvfile))


def is_filled(value: str | None) -> bool:
    return value is not None and str(value).strip() != "" and str(value).strip().lower() != "none"


def percentage(part: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round((part / total) * 100, 2)


def safe_int(value) -> int:
    try:
        return int(value) if is_filled(value) else 0
    except (ValueError, TypeError):
        return 0


def summarize_repository_summary(repo_rows: list[dict]):
    total_repos = len(repo_rows)

    contributors_counts = []
    issues_collected_counts = []
    prs_collected_counts = []
    releases_collected_counts = []
    projects_counts = []
    project_items_counts = []

    for row in repo_rows:
        contributors_counts.append(safe_int(row.get("contributors_count")))
        issues_collected_counts.append(safe_int(row.get("issues_collected")))
        prs_collected_counts.append(safe_int(row.get("prs_collected")))
        releases_collected_counts.append(safe_int(row.get("releases_collected")))

        # tenta cobrir possíveis nomes de colunas
        projects_counts.append(
            safe_int(
                row.get("projects_v2_count")
                or row.get("projects_count")
                or row.get("projects_collected")
            )
        )
        project_items_counts.append(
            safe_int(
                row.get("projects_v2_items_total")
                or row.get("project_items_total")
                or row.get("items_in_projects")
            )
        )

    print("\n=== RESUMO DOS REPOSITÓRIOS ===")
    print(f"Total de repositórios no summary: {total_repos}")

    if total_repos > 0:
        repos_with_projects = sum(1 for count in projects_counts if count > 0)
        repos_with_project_items = sum(1 for count in project_items_counts if count > 0)

        print(
            f"Repositórios com Projects V2: {repos_with_projects} "
            f"({percentage(repos_with_projects, total_repos)}%)"
        )
        print(
            f"Repositórios com itens em Projects V2: {repos_with_project_items} "
            f"({percentage(repos_with_project_items, total_repos)}%)"
        )

        print(f"Contributors - mín: {min(contributors_counts)} | máx: {max(contributors_counts)}")
        print(f"Issues coletadas - mín: {min(issues_collected_counts)} | máx: {max(issues_collected_counts)}")
        print(f"PRs coletadas - mín: {min(prs_collected_counts)} | máx: {max(prs_collected_counts)}")
        print(f"Releases coletadas - mín: {min(releases_collected_counts)} | máx: {max(releases_collected_counts)}")


def summarize_issues(issues_rows: list[dict]):
    total_issues = len(issues_rows)
    issues_with_closed_at = sum(1 for row in issues_rows if is_filled(row.get("closed_at")))
    issues_open = sum(1 for row in issues_rows if str(row.get("state", "")).upper() == "OPEN")
    issues_closed = sum(1 for row in issues_rows if str(row.get("state", "")).upper() == "CLOSED")

    print("\n=== QUALIDADE DOS DADOS - ISSUES ===")
    print(f"Total de issues: {total_issues}")
    print(
        f"Issues com closed_at preenchido: {issues_with_closed_at} "
        f"({percentage(issues_with_closed_at, total_issues)}%)"
    )
    print(f"Issues com state = OPEN: {issues_open} ({percentage(issues_open, total_issues)}%)")
    print(f"Issues com state = CLOSED: {issues_closed} ({percentage(issues_closed, total_issues)}%)")


def summarize_prs(pr_rows: list[dict]):
    total_prs = len(pr_rows)
    prs_with_merged_at = sum(1 for row in pr_rows if is_filled(row.get("merged_at")))
    prs_with_closed_at = sum(1 for row in pr_rows if is_filled(row.get("closed_at")))
    prs_open = sum(1 for row in pr_rows if str(row.get("state", "")).upper() == "OPEN")
    prs_closed = sum(1 for row in pr_rows if str(row.get("state", "")).upper() == "CLOSED")
    prs_merged = sum(1 for row in pr_rows if str(row.get("state", "")).upper() == "MERGED")

    print("\n=== QUALIDADE DOS DADOS - PULL REQUESTS ===")
    print(f"Total de PRs: {total_prs}")
    print(
        f"PRs com merged_at preenchido: {prs_with_merged_at} "
        f"({percentage(prs_with_merged_at, total_prs)}%)"
    )
    print(
        f"PRs com closed_at preenchido: {prs_with_closed_at} "
        f"({percentage(prs_with_closed_at, total_prs)}%)"
    )
    print(f"PRs com state = OPEN: {prs_open} ({percentage(prs_open, total_prs)}%)")
    print(f"PRs com state = CLOSED: {prs_closed} ({percentage(prs_closed, total_prs)}%)")
    print(f"PRs com state = MERGED: {prs_merged} ({percentage(prs_merged, total_prs)}%)")


def summarize_releases(release_rows: list[dict]):
    total_releases = len(release_rows)
    releases_with_published_at = sum(1 for row in release_rows if is_filled(row.get("published_at")))
    draft_releases = sum(1 for row in release_rows if str(row.get("is_draft", "")).lower() == "true")
    prereleases = sum(1 for row in release_rows if str(row.get("is_prerelease", "")).lower() == "true")

    releases_per_repo = Counter()
    for row in release_rows:
        full_name = row.get("full_name")
        if full_name:
            releases_per_repo[full_name] += 1

    print("\n=== QUALIDADE DOS DADOS - RELEASES ===")
    print(f"Total de releases: {total_releases}")
    print(
        f"Releases com published_at preenchido: {releases_with_published_at} "
        f"({percentage(releases_with_published_at, total_releases)}%)"
    )
    print(f"Releases draft: {draft_releases} ({percentage(draft_releases, total_releases)}%)")
    print(f"Releases prerelease: {prereleases} ({percentage(prereleases, total_releases)}%)")
    print(f"Repositórios com pelo menos 1 release detalhada: {len(releases_per_repo)}")


def summarize_projects(project_rows: list[dict]):
    total_project_rows = len(project_rows)

    print("\n=== QUALIDADE DOS DADOS - PROJECTS V2 ===")
    if total_project_rows == 0:
        print("Nenhum dado de Projects V2 encontrado.")
        return

    repos_with_projects = set()
    projects_per_repo = Counter()
    items_per_repo = Counter()

    for row in project_rows:
        full_name = row.get("full_name")
        if full_name:
            repos_with_projects.add(full_name)
            projects_per_repo[full_name] += 1

        items_total = safe_int(
            row.get("items_total")
            or row.get("project_items_total")
            or row.get("items_in_project")
        )

        if full_name:
            items_per_repo[full_name] += items_total

    total_items = sum(items_per_repo.values())
    repos_with_at_least_one_item = sum(1 for total in items_per_repo.values() if total > 0)

    print(f"Total de registros de projects: {total_project_rows}")
    print(f"Repositórios com pelo menos 1 Project V2: {len(repos_with_projects)}")
    print(f"Total de itens em projects: {total_items}")
    print(f"Repositórios com itens em projects: {repos_with_at_least_one_item}")

    top_projects = projects_per_repo.most_common(5)
    if top_projects:
        print("\nTop 5 repositórios com mais Projects V2:")
        for full_name, count in top_projects:
            print(f"- {full_name}: {count} projects | {items_per_repo[full_name]} itens")

    top_items = items_per_repo.most_common(5)
    if top_items:
        print("\nTop 5 repositórios com mais itens em Projects V2:")
        for full_name, count in top_items:
            print(f"- {full_name}: {count} itens")


def main():
    print("Lendo arquivos...")

    repo_rows = read_csv(REPO_SUMMARY_PATH)
    issues_rows = read_csv(ISSUES_PATH)
    pr_rows = read_csv(PRS_PATH)
    release_rows = read_csv(RELEASES_PATH)
    project_rows = read_csv(PROJECTS_PATH)

    summarize_repository_summary(repo_rows)
    summarize_issues(issues_rows)
    summarize_prs(pr_rows)
    summarize_releases(release_rows)
    summarize_projects(project_rows)


if __name__ == "__main__":
    main()