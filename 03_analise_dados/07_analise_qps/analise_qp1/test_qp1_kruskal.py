from pathlib import Path

import pandas as pd
from scipy.stats import kruskal


BASE_DIR = Path(__file__).resolve().parents[2]
DATASET_DIR = BASE_DIR / "data" / "dataset_10000_stars"

FILTERED_PATH = (
        DATASET_DIR /
        "repositories_filtered" /
        "repositories_filtered.csv"
)

METRICS_PATH = (
        DATASET_DIR /
        "repositories_metrics_final" /
        "repositories_metrics_final.csv"
)

QUARTILE_LABELS = ["Q1", "Q2", "Q3", "Q4"]

metrics = [
    "pr_lead_time_cv",
    "monthly_throughput_prs_cv",
    "release_interval_cv"
]


def add_star_quartile_column(df):
    df = df.copy()

    df["stars"] = pd.to_numeric(
        df["stars"],
        errors="coerce"
    )

    df = df[df["stars"].notna()].copy()

    df["star_quartile"] = pd.qcut(
        df["stars"],
        q=4,
        labels=QUARTILE_LABELS,
        duplicates="drop"
    )

    return df


def main():
    filtered_df = pd.read_csv(FILTERED_PATH)
    metrics_df = pd.read_csv(METRICS_PATH)

    filtered_df = add_star_quartile_column(
        filtered_df
    )

    df = filtered_df[
        ["full_name", "star_quartile"]
    ].merge(
        metrics_df,
        on="full_name",
        how="inner"
    )

    print("=== TESTE KRUSKAL-WALLIS ===\n")

    for metric in metrics:
        groups = []

        for q in QUARTILE_LABELS:
            values = pd.to_numeric(
                df.loc[
                    df["star_quartile"] == q,
                    metric
                ],
                errors="coerce"
            ).dropna()

            groups.append(values)

        stat, p = kruskal(*groups)

        print(metric)
        print(f"Estatística: {stat:.6e}")
        print(f"p-value: {p:.6e}")

        if p < 0.05:
            print("Diferença significativa entre quartis")
        else:
            print("Sem diferença significativa")

        print("-" * 40)


if __name__ == "__main__":
    main()