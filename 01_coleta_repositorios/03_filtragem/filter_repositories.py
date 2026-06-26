import csv
from datetime import datetime, timedelta, UTC
from pathlib import Path


def find_project_root(start: Path) -> Path:
    current = start.resolve()
    for parent in [current, *current.parents]:
        if (parent / "data").exists() and parent.name == "metrics-decision-impact":
            return parent
    raise RuntimeError("Raiz do projeto não encontrada.")

PROJECT_ROOT = find_project_root(Path(__file__))
DATASET_DIR = PROJECT_ROOT / "data" / "dataset_10000_stars"
SEARCH_DIR = DATASET_DIR / "repositories_searched"
FILTERED_DIR = DATASET_DIR / "repositories_filtered"

FILTERED_DIR.mkdir(parents=True, exist_ok=True)

INPUT_PATHS = [
    SEARCH_DIR / "repos_search_10_5000.csv",
    SEARCH_DIR / "repos_search_5001_10000.csv",
    SEARCH_DIR / "repos_search_10001_35000.csv",
    SEARCH_DIR / "repos_search_35001_50000.csv",
    ]

OUTPUT_APPROVED_PATH = FILTERED_DIR / "repositories_filtered.csv"
OUTPUT_REJECTED_PATH = FILTERED_DIR / "repositories_rejected.csv"

MIN_ISSUES = 15
MIN_PULL_REQUESTS = 10
MIN_RELEASES = 2
RECENT_ACTIVITY_DAYS = 730


NEGATIVE_KEYWORDS = {
    "tutorial", "course", "courses", "study", "studies", "learning", "learn",
    "awesome", "resources", "resource", "roadmap", "guide", "guides",
    "book", "books", "cookbook", "recipes", "recipe",
    "interview", "interviews", "leetcode", "algorithms", "algorithm",
    "notes", "note", "docs", "documentation", "cheatsheet",
    "boilerplate", "template", "templates", "example", "examples",
    "curriculum", "exercise", "exercises", "submission", "submissions",
    "textbook", "paper", "papers"
}

POSITIVE_KEYWORDS = {
    "software", "library", "framework", "tool", "tools", "sdk", "api",
    "server", "client", "app", "application", "applications",
    "backend", "frontend", "database", "compiler", "parser", "engine",
    "platform", "service", "services", "cli", "package", "plugin",
    "extension", "system", "systems", "module", "modules"
}

NON_SOFTWARE_LANGUAGES = {
    "Markdown", "TeX", "Rich Text Format", "Text", "AsciiDoc"
}


def parse_datetime(dt_str: str):
    if not dt_str:
        return None
    return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))


def is_recent_enough(pushed_at: str) -> bool:
    pushed_date = parse_datetime(pushed_at)
    if pushed_date is None:
        return False
    cutoff = datetime.now(UTC) - timedelta(days=RECENT_ACTIVITY_DAYS)
    return pushed_date >= cutoff


def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    return str(text).strip().lower()


def tokenize_topics(topics: str | None) -> set[str]:
    if not topics:
        return set()

    return {
        token.strip().lower()
        for token in str(topics).split("|")
        if token.strip()
    }


def repository_appears_to_represent_software(repo: dict) -> bool:
    description = normalize_text(repo.get("description"))
    topics = tokenize_topics(repo.get("topics"))
    language = repo.get("primary_language")

    combined_text = f"{description} {' '.join(topics)}"

    has_positive_signal = any(keyword in combined_text for keyword in POSITIVE_KEYWORDS)
    has_negative_signal = any(keyword in combined_text for keyword in NEGATIVE_KEYWORDS)

    if language in NON_SOFTWARE_LANGUAGES and not has_positive_signal:
        return False

    if has_negative_signal and not has_positive_signal:
        return False

    return True


def evaluate_repository(repo: dict):
    reasons = []

    issues_total = int(repo["issues_total"])
    pull_requests_total = int(repo["pull_requests_total"])
    releases_total = int(repo["releases_total"])
    pushed_at = repo["pushed_at"]

    if issues_total < MIN_ISSUES:
        reasons.append(f"issues_total < {MIN_ISSUES}")

    if pull_requests_total < MIN_PULL_REQUESTS:
        reasons.append(f"pull_requests_total < {MIN_PULL_REQUESTS}")

    if releases_total < MIN_RELEASES:
        reasons.append(f"releases_total < {MIN_RELEASES}")

    if not is_recent_enough(pushed_at):
        reasons.append(f"pushed_at older than {RECENT_ACTIVITY_DAYS} days")

    if not repository_appears_to_represent_software(repo):
        reasons.append("repository does not appear to represent software")

    return reasons


def read_csv(input_path: Path):
    if not input_path.exists():
        print(f"Arquivo não encontrado: {input_path.resolve()}")
        return []

    with input_path.open(mode="r", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        return list(reader)


def read_all_search_results(input_paths: list[Path]):
    all_rows = []

    for path in input_paths:
        rows = read_csv(path)
        print(f"Lidos {len(rows)} registros de: {path.name}")
        all_rows.extend(rows)

    return all_rows


def deduplicate_repositories(rows: list[dict]):
    unique = {}
    for row in rows:
        full_name = row["full_name"]
        if full_name not in unique:
            unique[full_name] = row
    return list(unique.values())


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


def main():
    repositories = read_all_search_results(INPUT_PATHS)

    if not repositories:
        print("Nenhum repositório encontrado nos arquivos de entrada.")
        return

    total_before_dedup = len(repositories)
    repositories = deduplicate_repositories(repositories)
    total_after_dedup = len(repositories)

    approved = []
    rejected = []

    for repo in repositories:
        reasons = evaluate_repository(repo)

        if reasons:
            rejected_row = repo.copy()
            rejected_row["rejection_reasons"] = " | ".join(reasons)
            rejected.append(rejected_row)
        else:
            approved.append(repo)

    print("\n=== RESUMO DO FILTER ===")
    print(f"Total lido (antes de deduplicar): {total_before_dedup}")
    print(f"Total único (após deduplicar): {total_after_dedup}")
    print(f"Aprovados: {len(approved)}")
    print(f"Rejeitados: {len(rejected)}\n")

    if approved:
        print("Exemplos aprovados:")
        for repo in approved[:5]:
            print(
                f"- {repo['full_name']} | "
                f"Issues: {repo['issues_total']} | "
                f"PRs: {repo['pull_requests_total']} | "
                f"Releases: {repo['releases_total']} | "
                f"Pushed: {repo['pushed_at']}"
            )

    if rejected:
        print("\nExemplos rejeitados:")
        for repo in rejected[:5]:
            print(
                f"- {repo['full_name']} | "
                f"Motivos: {repo['rejection_reasons']}"
            )

    if approved:
        write_csv(approved, OUTPUT_APPROVED_PATH)

    if rejected:
        write_csv(rejected, OUTPUT_REJECTED_PATH)


if __name__ == "__main__":
    main()