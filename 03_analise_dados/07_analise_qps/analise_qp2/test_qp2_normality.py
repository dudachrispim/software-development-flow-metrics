from pathlib import Path

import pandas as pd
from scipy.stats import shapiro


BASE_DIR = Path(__file__).resolve().parents[2]

DATASET_DIR = (
        BASE_DIR
        / "data"
        / "dataset_10000_stars"
)

FLOW_PATH = (
        DATASET_DIR
        / "repositories_metrics_final"
        / "qp2_flow_stages"
        / "flow_stage_metrics_long.csv"
)


STAGES = [
    "issue_to_pr",
    "pr_to_merge",
    "merge_to_release",
]


def main():

    df = pd.read_csv(FLOW_PATH)

    print("\n=== TESTE DE NORMALIDADE - QP2 ===\n")

    for stage in STAGES:

        series = (
            pd.to_numeric(
                df.loc[
                    df["stage"] == stage,
                    "days"
                ],
                errors="coerce"
            )
            .dropna()
        )

        stat, p_value = shapiro(series)

        print(stage)

        print(f"Estatística: {stat:.4f}")

        print(f"p-value: {p_value:.4e}")

        if p_value < 0.05:
            print("Distribuição NÃO normal")

        else:
            print("Distribuição normal")

        print("-" * 40)


if __name__ == "__main__":
    main()