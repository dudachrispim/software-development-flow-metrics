import csv
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean, median


def find_project_root(start: Path) -> Path:
    current = start.resolve()
    for parent in [current, *current.parents]:
        if (parent / "data").exists() and parent.name == "metrics-decision-impact":
            return parent
    raise RuntimeError("Raiz do projeto não encontrada.")

PROJECT_ROOT = find_project_root(Path(__file__))
DATASET_DIR = PROJECT_ROOT / "data" / "dataset_10000_stars"

CLEAN_DIR = DATASET_DIR / "repositories_metrics_clean"
OUTPUT_DIR = DATASET_DIR / "repositories_metrics_final"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

REPO_SUMMARY_PATH = CLEAN_DIR / "repositories_detailed_summary_clean.csv"
PRS_PATH = CLEAN_DIR / "pull_requests_detailed_clean.csv"
RELEASES_PATH = CLEAN_DIR / "releases_detailed_clean.csv"

OUTPUT_PATH = OUTPUT_DIR / "repositories_metrics_final.csv"


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


def parse_datetime(value: str | None):
    if value is None:
        return None

    value = str(value).strip()
    if value == "" or value.lower() == "none":
        return None

    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def days_between(start, end):
    if start is None or end is None:
        return None
    delta = end - start
    return delta.total_seconds() / 86400.0


def safe_int(value) -> int:
    try:
        if value is None:
            return 0
        value = str(value).strip()
        if value == "" or value.lower() == "none":
            return 0
        return int(value)
    except (ValueError, TypeError):
        return 0


def calculate_std(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    avg = mean(values)
    variance = sum((x - avg) ** 2 for x in values) / len(values)
    return math.sqrt(variance)


def calculate_percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None

    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return float(sorted_values[0])

    k = (len(sorted_values) - 1) * percentile
    f = math.floor(k)
    c = math.ceil(k)

    if f == c:
        return float(sorted_values[int(k)])

    d0 = sorted_values[f] * (c - k)
    d1 = sorted_values[c] * (k - f)
    return float(d0 + d1)


def calculate_cv(avg: float | None, std: float | None) -> float | None:
    if avg is None or std is None:
        return None
    if avg == 0:
        return None
    return std / avg


def summarize_distribution(values: list[float], prefix: str) -> dict:
    if not values:
        return {
            f"{prefix}_count": 0,
            f"{prefix}_mean_days": None,
            f"{prefix}_std_days": None,
            f"{prefix}_median_days": None,
            f"{prefix}_p90_days": None,
            f"{prefix}_cv": None,
            f"{prefix}_min_days": None,
            f"{prefix}_max_days": None,
        }

    avg = mean(values)
    std = calculate_std(values)
    med = median(values)
    p90 = calculate_percentile(values, 0.90)
    cv = calculate_cv(avg, std)

    return {
        f"{prefix}_count": len(values),
        f"{prefix}_mean_days": round(avg, 4),
        f"{prefix}_std_days": round(std, 4),
        f"{prefix}_median_days": round(med, 4),
        f"{prefix}_p90_days": round(p90, 4) if p90 is not None else None,
        f"{prefix}_cv": round(cv, 6) if cv is not None else None,
        f"{prefix}_min_days": round(min(values), 4),
        f"{prefix}_max_days": round(max(values), 4),
    }


def summarize_throughput(values: list[int], prefix: str) -> dict:
    if not values:
        return {
            f"{prefix}_months_count": 0,
            f"{prefix}_mean": None,
            f"{prefix}_std": None,
            f"{prefix}_median": None,
            f"{prefix}_p90": None,
            f"{prefix}_cv": None,
            f"{prefix}_min": None,
            f"{prefix}_max": None,
        }

    avg = mean(values)
    std = calculate_std(values)
    med = median(values)
    p90 = calculate_percentile(values, 0.90)
    cv = calculate_cv(avg, std)

    return {
        f"{prefix}_months_count": len(values),
        f"{prefix}_mean": round(avg, 4),
        f"{prefix}_std": round(std, 4),
        f"{prefix}_median": round(med, 4),
        f"{prefix}_p90": round(p90, 4) if p90 is not None else None,
        f"{prefix}_cv": round(cv, 6) if cv is not None else None,
        f"{prefix}_min": min(values),
        f"{prefix}_max": max(values),
    }


def build_issue_cycle_time(issue_rows: list[dict]) -> dict[str, list[float]]:
    cycle_time_by_repo = defaultdict(list)

    for row in issue_rows:
        created_at = parse_datetime(row.get("created_at"))
        closed_at = parse_datetime(row.get("closed_at"))

        cycle_time_days = days_between(created_at, closed_at)
        if cycle_time_days is None:
            continue

        full_name = row.get("full_name")
        if full_name:
            cycle_time_by_repo[full_name].append(cycle_time_days)

    return cycle_time_by_repo


def build_pr_cycle_time(pr_rows: list[dict]) -> dict[str, list[float]]:
    cycle_time_by_repo = defaultdict(list)

    for row in pr_rows:
        created_at = parse_datetime(row.get("created_at"))
        merged_at = parse_datetime(row.get("merged_at"))

        cycle_time_days = days_between(created_at, merged_at)
        if cycle_time_days is None:
            continue

        full_name = row.get("full_name")
        if full_name:
            cycle_time_by_repo[full_name].append(cycle_time_days)

    return cycle_time_by_repo


def build_monthly_throughput(pr_rows: list[dict]) -> dict[str, list[int]]:
    monthly_counts_by_repo = defaultdict(lambda: defaultdict(int))

    for row in pr_rows:
        merged_at = parse_datetime(row.get("merged_at"))
        if merged_at is None:
            continue

        full_name = row.get("full_name")
        if not full_name:
            continue

        month_key = merged_at.strftime("%Y-%m")
        monthly_counts_by_repo[full_name][month_key] += 1

    throughput_by_repo = {}
    for repo, monthly_map in monthly_counts_by_repo.items():
        throughput_by_repo[repo] = list(monthly_map.values())

    return throughput_by_repo


def build_release_intervals(release_rows: list[dict]) -> dict[str, list[float]]:
    releases_by_repo = defaultdict(list)

    for row in release_rows:
        published_at = parse_datetime(row.get("published_at"))
        if published_at is None:
            continue

        full_name = row.get("full_name")
        if full_name:
            releases_by_repo[full_name].append(published_at)

    intervals_by_repo = defaultdict(list)

    for repo, release_dates in releases_by_repo.items():
        sorted_dates = sorted(release_dates)

        if len(sorted_dates) < 2:
            continue

        for i in range(1, len(sorted_dates)):
            interval_days = days_between(sorted_dates[i - 1], sorted_dates[i])
            if interval_days is not None:
                intervals_by_repo[repo].append(interval_days)

    return intervals_by_repo

def build_pr_stage_times(pr_rows: list[dict]) -> dict[str, dict[str, list[float]]]:
    stages_by_repo = defaultdict(lambda: {
        "pr_review_time": [],
    })

    for row in pr_rows:
        created_at = parse_datetime(row.get("created_at"))
        merged_at = parse_datetime(row.get("merged_at"))

        review_time = days_between(created_at, merged_at)

        if review_time is None:
            continue

        repo = row.get("full_name")
        if repo:
            stages_by_repo[repo]["pr_review_time"].append(review_time)

    return stages_by_repo

def main():
    print("Lendo arquivos limpos...")
    repo_rows = read_csv(REPO_SUMMARY_PATH)
    pr_rows = read_csv(PRS_PATH)
    release_rows = read_csv(RELEASES_PATH)

    if not repo_rows:
        print("Nenhum repositório encontrado.")
        return

    print("Calculando cycle time de PRs...")
    pr_cycle_time_by_repo = build_pr_cycle_time(pr_rows)

    print("Calculando throughput mensal de PRs...")
    throughput_by_repo = build_monthly_throughput(pr_rows)

    print("Calculando intervalos entre releases...")
    release_intervals_by_repo = build_release_intervals(release_rows)

    print("Calculando tempos de etapas (gargalos)...")
    pr_stage_times = build_pr_stage_times(pr_rows)

    final_rows = []

    for repo in repo_rows:
        full_name = repo.get("full_name")
        if not full_name:
            continue

        # Cycle time (principal)
        pr_metrics = summarize_distribution(
            pr_cycle_time_by_repo.get(full_name, []),
            "pr_cycle_time",
        )

        # Throughput
        throughput_metrics = summarize_throughput(
            throughput_by_repo.get(full_name, []),
            "monthly_throughput_prs",
        )

        # Releases
        release_metrics = summarize_distribution(
            release_intervals_by_repo.get(full_name, []),
            "release_interval",
        )

        # Gargalos (review)
        stage_metrics = {}
        stages = pr_stage_times.get(full_name, {})

        for stage_name, values in stages.items():
            stage_metrics.update(
                summarize_distribution(values, stage_name)
            )

        row = {
            "full_name": full_name,
            "primary_language": repo.get("primary_language"),
            "contributors_count": safe_int(repo.get("contributors_count")),
            "prs_collected": safe_int(repo.get("prs_collected")),
            "releases_collected": safe_int(repo.get("releases_collected")),
        }

        row.update(pr_metrics)
        row.update(throughput_metrics)
        row.update(release_metrics)
        row.update(stage_metrics)

        final_rows.append(row)

    print("\n=== RESUMO DO CÁLCULO ===")
    print(f"Repositórios processados: {len(final_rows)}")

    repos_with_pr = sum(1 for r in final_rows if r["pr_cycle_time_count"] > 0)
    repos_with_throughput = sum(1 for r in final_rows if r["monthly_throughput_prs_months_count"] > 0)
    repos_with_release = sum(1 for r in final_rows if r["release_interval_count"] > 0)

    print(f"Repositórios com cycle time de PR: {repos_with_pr}")
    print(f"Repositórios com throughput: {repos_with_throughput}")
    print(f"Repositórios com releases: {repos_with_release}")

    write_csv(final_rows, OUTPUT_PATH)


if __name__ == "__main__":
    main()