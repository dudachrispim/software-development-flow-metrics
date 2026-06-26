from pathlib import Path

import pandas as pd
from scipy.stats import shapiro


BASE_DIR = Path(__file__).resolve().parent
DATASET_DIR = BASE_DIR / "data" / "dataset_10000_stars"

METRICS_PATH = (
        DATASET_DIR /
        "repositories_metrics_final" /
        "repositories_metrics_final.csv"
)

metrics = [
    "pr_lead_time_cv",
    "monthly_throughput_prs_cv",
    "release_interval_cv"
]


def main():
    df = pd.read_csv(METRICS_PATH)

    print("=== TESTE DE NORMALIDADE ===\n")

    for metric in metrics:
        values = pd.to_numeric(df[metric], errors="coerce").dropna()

        sample = values.sample(
            min(5000, len(values)),
            random_state=42
        )

        stat, p = shapiro(sample)

        print(f"{metric}")
        print(f"Estatística: {stat:.6e}")
        print(f"p-value: {p:.6e}")

        if p < 0.05:
            print("Distribuição NÃO normal")
        else:
            print("Distribuição normal")

        print("-" * 40)


if __name__ == "__main__":
    main()