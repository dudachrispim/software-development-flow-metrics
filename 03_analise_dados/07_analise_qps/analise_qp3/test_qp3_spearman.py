from pathlib import Path

import pandas as pd
from scipy.stats import spearmanr


BASE_DIR = Path(__file__).resolve().parents[2]

DATASET_DIR = (
        BASE_DIR
        / "data"
        / "dataset_10000_stars"
)

METRICS_PATH = (
        DATASET_DIR
        / "repositories_metrics_final"
        / "repositories_metrics_final.csv"
)


THROUGHPUT_COLUMN = "monthly_throughput_prs_mean"

CV_COLUMNS = [
    "pr_lead_time_cv",
    "monthly_throughput_prs_cv",
    "release_interval_cv",
]


def main():

    df = pd.read_csv(METRICS_PATH)

    print("\n=== CORRELAÇÃO SPEARMAN - QP3 ===\n")

    for cv_column in CV_COLUMNS:

        temp = df[
            [
                cv_column,
                THROUGHPUT_COLUMN
            ]
        ].copy()

        temp = temp.apply(
            pd.to_numeric,
            errors="coerce"
        ).dropna()

        rho, p_value = spearmanr(
            temp[cv_column],
            temp[THROUGHPUT_COLUMN]
        )

        print(
            f"{cv_column} × {THROUGHPUT_COLUMN}"
        )

        print(f"Spearman rho: {rho:.4f}")

        print(f"p-value: {p_value:.4e}")

        if p_value < 0.05:
            print("Correlação significativa")

        else:
            print("Correlação NÃO significativa")

        print("-" * 40)


if __name__ == "__main__":
    main()