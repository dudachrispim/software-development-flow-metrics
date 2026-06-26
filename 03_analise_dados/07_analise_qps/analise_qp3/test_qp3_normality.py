from pathlib import Path

import pandas as pd
from scipy.stats import shapiro


BASE_DIR = Path(__file__).resolve().parent.parent

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


VARIABLES = [
    "pr_lead_time_cv",
    "monthly_throughput_prs_cv",
    "release_interval_cv",
    "monthly_throughput_prs_mean",
]


def main():

    df = pd.read_csv(METRICS_PATH)

    print("\n=== TESTE DE NORMALIDADE - QP3 ===\n")

    for column in VARIABLES:

        series = (
            pd.to_numeric(
                df[column],
                errors="coerce"
            )
            .dropna()
        )

        stat, p_value = shapiro(series)

        print(column)

        print(f"Estatística: {stat:.4f}")

        print(f"p-value: {p_value:.4e}")

        if p_value < 0.05:
            print("Distribuição NÃO normal")

        else:
            print("Distribuição normal")

        print("-" * 40)


if __name__ == "__main__":
    main()