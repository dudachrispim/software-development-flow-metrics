from pathlib import Path

import pandas as pd
import scikit_posthocs as sp


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

OUTPUT_DIR = Path(__file__).resolve().parent

QUARTILE_LABELS = ["Q1", "Q2", "Q3", "Q4"]

METRICS = {
    "pr_lead_time_cv": "Cycle Time CV",
    "monthly_throughput_prs_cv": "Throughput CV",
    "release_interval_cv": "Release Interval CV"
}


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


def format_p_value(p):
    if p < 0.001:
        return "< 0.001"
    return f"{p:.6f}"


def main():
    filtered_df = pd.read_csv(FILTERED_PATH)
    metrics_df = pd.read_csv(METRICS_PATH)

    filtered_df = add_star_quartile_column(filtered_df)

    df = filtered_df[
        ["full_name", "star_quartile"]
    ].merge(
        metrics_df,
        on="full_name",
        how="inner"
    )

    print("=== PÓS-TESTE DE DUNN - QP1 ===\n")
    print("Correção utilizada: Holm\n")

    all_results = []

    for metric, metric_label in METRICS.items():
        test_df = df[["star_quartile", metric]].copy()

        test_df[metric] = pd.to_numeric(
            test_df[metric],
            errors="coerce"
        )

        test_df = test_df.dropna(subset=["star_quartile", metric])

        dunn_result = sp.posthoc_dunn(
            test_df,
            val_col=metric,
            group_col="star_quartile",
            p_adjust="holm"
        )

        dunn_result = dunn_result.loc[
            QUARTILE_LABELS,
            QUARTILE_LABELS
        ]

        print(metric_label)
        print(dunn_result)
        print("\nComparações significativas (p < 0.05):")

        for i, q1 in enumerate(QUARTILE_LABELS):
            for q2 in QUARTILE_LABELS[i + 1:]:
                p_value = dunn_result.loc[q1, q2]

                significant = p_value < 0.05

                all_results.append({
                    "metric": metric_label,
                    "comparison": f"{q1} x {q2}",
                    "p_value": p_value,
                    "significant": significant
                })

                if significant:
                    print(
                        f"{q1} x {q2}: "
                        f"p-value = {format_p_value(p_value)}"
                    )

        print("-" * 50)

    results_df = pd.DataFrame(all_results)

    output_path = OUTPUT_DIR / "qp1_dunn_results.csv"
    results_df.to_csv(output_path, index=False, encoding="utf-8-sig")

    print("\nArquivo salvo em:")
    print(output_path)


if __name__ == "__main__":
    main()