from pathlib import Path

import pandas as pd
from scipy.stats import kruskal


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


def main():

    df = pd.read_csv(FLOW_PATH)

    issue_to_pr = (
        pd.to_numeric(
            df.loc[
                df["stage"] == "issue_to_pr",
                "days"
            ],
            errors="coerce"
        )
        .dropna()
    )

    pr_to_merge = (
        pd.to_numeric(
            df.loc[
                df["stage"] == "pr_to_merge",
                "days"
            ],
            errors="coerce"
        )
        .dropna()
    )

    merge_to_release = (
        pd.to_numeric(
            df.loc[
                df["stage"] == "merge_to_release",
                "days"
            ],
            errors="coerce"
        )
        .dropna()
    )

    stat, p_value = kruskal(
        issue_to_pr,
        pr_to_merge,
        merge_to_release
    )

    print("\n=== TESTE KRUSKAL-WALLIS - QP2 ===\n")

    print(f"Estatística: {stat:.4f}")

    print(f"p-value: {p_value:.4e}")

    if p_value < 0.05:
        print(
            "Diferença significativa entre as etapas do fluxo"
        )

    else:
        print(
            "Não existe diferença significativa entre as etapas"
        )


if __name__ == "__main__":
    main()