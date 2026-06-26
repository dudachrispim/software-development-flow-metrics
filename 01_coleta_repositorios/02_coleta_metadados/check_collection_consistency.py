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

REPO_SUMMARY_PATH = DATASET_DIR / "repositories_metrics_collected" / "repositories_detailed_summary.csv"


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        print(f"Arquivo não encontrado: {path.resolve()}")
        return []

    with path.open(mode="r", encoding="utf-8") as csvfile:
        return list(csv.DictReader(csvfile))


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


def main():
    rows = read_csv(REPO_SUMMARY_PATH)

    if not rows:
        print("Nenhum dado encontrado no summary.")
        return

    inconsistent_prs = []
    inconsistent_releases = []
    inconsistent_issues = []

    for row in rows:
        full_name = row.get("full_name", "UNKNOWN")

        issues_initial = safe_int(row.get("issues_total_initial"))
        prs_initial = safe_int(row.get("pull_requests_total_initial"))
        releases_initial = safe_int(row.get("releases_total_initial"))

        issues_collected = safe_int(row.get("issues_collected"))
        prs_collected = safe_int(row.get("prs_collected"))
        releases_collected = safe_int(row.get("releases_collected"))

        if issues_initial > 0 and issues_collected == 0:
            inconsistent_issues.append(
                {
                    "full_name": full_name,
                    "issues_total_initial": issues_initial,
                    "issues_collected": issues_collected,
                }
            )

        if prs_initial > 0 and prs_collected == 0:
            inconsistent_prs.append(
                {
                    "full_name": full_name,
                    "pull_requests_total_initial": prs_initial,
                    "prs_collected": prs_collected,
                }
            )

        if releases_initial > 0 and releases_collected == 0:
            inconsistent_releases.append(
                {
                    "full_name": full_name,
                    "releases_total_initial": releases_initial,
                    "releases_collected": releases_collected,
                }
            )

    print("\n=== VERIFICAÇÃO DE INCONSISTÊNCIAS ===")
    print(f"Total de repositórios analisados: {len(rows)}")

    print("\nRepositórios com issues_total_initial > 0 e issues_collected = 0:")
    print(f"Quantidade: {len(inconsistent_issues)}")
    for item in inconsistent_issues[:10]:
        print(
            f"- {item['full_name']} | "
            f"issues_total_initial: {item['issues_total_initial']} | "
            f"issues_collected: {item['issues_collected']}"
        )

    print("\nRepositórios com pull_requests_total_initial > 0 e prs_collected = 0:")
    print(f"Quantidade: {len(inconsistent_prs)}")
    for item in inconsistent_prs[:10]:
        print(
            f"- {item['full_name']} | "
            f"pull_requests_total_initial: {item['pull_requests_total_initial']} | "
            f"prs_collected: {item['prs_collected']}"
        )

    print("\nRepositórios com releases_total_initial > 0 e releases_collected = 0:")
    print(f"Quantidade: {len(inconsistent_releases)}")
    for item in inconsistent_releases[:10]:
        print(
            f"- {item['full_name']} | "
            f"releases_total_initial: {item['releases_total_initial']} | "
            f"releases_collected: {item['releases_collected']}"
        )


if __name__ == "__main__":
    main()