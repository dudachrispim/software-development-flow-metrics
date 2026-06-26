from pathlib import Path

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[2]
DATASET_DIR = BASE_DIR / "data" / "dataset_10000_stars"

LINKS_PATH = DATASET_DIR / "repositories_metrics_final" / "issue_pr_links_batched.csv"
RELEASES_PATH = DATASET_DIR / "repositories_metrics_clean" / "releases_detailed_clean.csv"

OUTPUT_DIR = DATASET_DIR / "repositories_metrics_final" / "qp2_flow_stages"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DETAILED_OUTPUT = OUTPUT_DIR / "flow_stage_metrics_detailed.csv"
LONG_OUTPUT = OUTPUT_DIR / "flow_stage_metrics_long.csv"
SUMMARY_OUTPUT = OUTPUT_DIR / "flow_stage_metrics_summary.csv"


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path.resolve()}")
    return pd.read_csv(path)


def parse_dates(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    df = df.copy()

    for col in columns:
        df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)

    return df


def build_release_map(releases_df: pd.DataFrame) -> dict:
    releases_df = releases_df.copy()

    releases_df["published_at"] = pd.to_datetime(
        releases_df["published_at"],
        errors="coerce",
        utc=True
    )

    releases_df = releases_df.dropna(subset=["full_name", "published_at"])

    return {
        repo: list(group["published_at"].sort_values())
        for repo, group in releases_df.groupby("full_name")
    }


def get_next_release_days(full_name, pr_merged_at, release_map):
    releases = release_map.get(full_name)

    if not releases or pd.isna(pr_merged_at):
        return np.nan

    for release_date in releases:
        if release_date >= pr_merged_at:
            return (release_date - pr_merged_at).total_seconds() / 86400

    return np.nan


def calculate_detailed_metrics(links_df: pd.DataFrame, release_map: dict) -> pd.DataFrame:
    df = links_df.copy()

    df = parse_dates(
        df,
        [
            "issue_created_at",
            "pr_created_at",
            "pr_merged_at",
        ]
    )

    df["issue_to_pr_days"] = (
                                     df["pr_created_at"] - df["issue_created_at"]
                             ).dt.total_seconds() / 86400

    df["pr_to_merge_days"] = (
                                     df["pr_merged_at"] - df["pr_created_at"]
                             ).dt.total_seconds() / 86400

    df["merge_to_release_days"] = df.apply(
        lambda row: get_next_release_days(
            row["full_name"],
            row["pr_merged_at"],
            release_map
        ),
        axis=1
    )

    for col in [
        "issue_to_pr_days",
        "pr_to_merge_days",
        "merge_to_release_days",
    ]:
        df.loc[df[col] < 0, col] = np.nan

    return df


def build_long_format(detailed_df: pd.DataFrame) -> pd.DataFrame:
    rows = []

    # issue -> PR: uma linha por relação issue-PR
    issue_stage = detailed_df[
        ["full_name", "pr_number", "issue_number", "issue_to_pr_days"]
    ].dropna(subset=["issue_to_pr_days"])

    for _, row in issue_stage.iterrows():
        rows.append({
            "full_name": row["full_name"],
            "pr_number": row["pr_number"],
            "issue_number": row["issue_number"],
            "stage": "issue_to_pr",
            "days": row["issue_to_pr_days"],
        })

    # PR -> merge: uma linha por PR único
    pr_stage = (
        detailed_df[
            ["full_name", "pr_number", "pr_to_merge_days"]
        ]
        .dropna(subset=["pr_to_merge_days"])
        .drop_duplicates(subset=["full_name", "pr_number"])
    )

    for _, row in pr_stage.iterrows():
        rows.append({
            "full_name": row["full_name"],
            "pr_number": row["pr_number"],
            "issue_number": np.nan,
            "stage": "pr_to_merge",
            "days": row["pr_to_merge_days"],
        })

    # merge -> release: uma linha por PR único
    release_stage = (
        detailed_df[
            ["full_name", "pr_number", "merge_to_release_days"]
        ]
        .dropna(subset=["merge_to_release_days"])
        .drop_duplicates(subset=["full_name", "pr_number"])
    )

    for _, row in release_stage.iterrows():
        rows.append({
            "full_name": row["full_name"],
            "pr_number": row["pr_number"],
            "issue_number": np.nan,
            "stage": "merge_to_release",
            "days": row["merge_to_release_days"],
        })

    return pd.DataFrame(rows)


def build_summary(long_df: pd.DataFrame) -> pd.DataFrame:
    return (
        long_df.groupby("stage")
        .agg(
            count=("days", "count"),
            mean_days=("days", "mean"),
            median_days=("days", "median"),
            std_days=("days", "std"),
            min_days=("days", "min"),
            max_days=("days", "max"),
        )
        .reset_index()
    )


def main():
    print("Lendo relações issue ↔ PR...")
    links_df = read_csv(LINKS_PATH)

    print("Lendo releases...")
    releases_df = read_csv(RELEASES_PATH)

    print("Preparando mapa de releases...")
    release_map = build_release_map(releases_df)

    print("Calculando métricas das etapas...")
    detailed_df = calculate_detailed_metrics(links_df, release_map)

    print("Gerando formato longo para testes estatísticos...")
    long_df = build_long_format(detailed_df)

    print("Gerando resumo...")
    summary_df = build_summary(long_df)

    detailed_df.to_csv(DETAILED_OUTPUT, index=False, encoding="utf-8-sig")
    long_df.to_csv(LONG_OUTPUT, index=False, encoding="utf-8-sig")
    summary_df.to_csv(SUMMARY_OUTPUT, index=False, encoding="utf-8-sig")

    print("\nArquivos gerados:")
    print(DETAILED_OUTPUT.resolve())
    print(LONG_OUTPUT.resolve())
    print(SUMMARY_OUTPUT.resolve())

    print("\nResumo das etapas:")
    print(summary_df.to_string(index=False))


if __name__ == "__main__":
    main()