from pathlib import Path
from datetime import datetime

import matplotlib.pyplot as plt
import pandas as pd


from pathlib import Path
from datetime import datetime

import matplotlib.pyplot as plt
import pandas as pd


# Script localizado em:
# data/dataset_10000_stars/repositories_metrics_analysis/relationships/

DATASET_DIR = Path(__file__).resolve().parents[2]

FILTERED_PATH = DATASET_DIR / "repositories_filtered" / "repositories_filtered.csv"
SUMMARY_PATH = DATASET_DIR / "repositories_metrics_collected" / "repositories_detailed_summary.csv"
METRICS_PATH = DATASET_DIR / "repositories_metrics_final" / "repositories_metrics_final.csv"

OUTPUT_DIR = DATASET_DIR / "repositories_metrics_analysis" / "relationships"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M")


def read_csv(path):
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path.resolve()}")
    return pd.read_csv(path)


def main():
    filtered = read_csv(FILTERED_PATH)
    summary = read_csv(SUMMARY_PATH)
    metrics = read_csv(METRICS_PATH)

    df = filtered.merge(summary, on="full_name", how="inner")
    df = df.merge(metrics, on="full_name", how="inner")

    # usa as colunas antigas de lead_time como cycle_time, sem recalcular
    df = df.rename(columns={
        "pr_lead_time_mean_days": "pr_cycle_time_mean_days",
        "pr_lead_time_cv": "pr_cycle_time_cv",
        "pr_lead_time_std_days": "pr_cycle_time_std_days",
    })

    columns = {
        "stars": "Stars",
        "forks": "Forks",
        "contributors_count_x": "Contributors",
        "issues_collected": "Issues",
        "prs_collected": "PRs",
        "releases_collected": "Releases",
        "pr_cycle_time_mean_days": "Cycle Time",
        "pr_cycle_time_cv": "Cycle Time CV",
        "monthly_throughput_prs_mean": "Throughput",
        "monthly_throughput_prs_cv": "Throughput CV",
        "release_interval_mean_days": "Release Interval",
        "release_interval_cv": "Release Interval CV",
    }

    available = {col: label for col, label in columns.items() if col in df.columns}
    corr_df = df[list(available.keys())].copy()
    corr_df = corr_df.rename(columns=available)

    for col in corr_df.columns:
        corr_df[col] = pd.to_numeric(corr_df[col], errors="coerce")

    corr = corr_df.corr(numeric_only=True)

    fig, ax = plt.subplots(figsize=(12, 9))
    im = ax.imshow(corr, aspect="auto")
    fig.colorbar(im)

    ax.set_xticks(range(len(corr.columns)))
    ax.set_yticks(range(len(corr.index)))
    ax.set_xticklabels(corr.columns, rotation=45, ha="right")
    ax.set_yticklabels(corr.index)

    for i in range(len(corr.index)):
        for j in range(len(corr.columns)):
            value = corr.iloc[i, j]
            if pd.notna(value):
                ax.text(j, i, f"{value:.2f}", ha="center", va="center", fontsize=8)

    ax.set_title("Correlação entre características dos repositórios e métricas de fluxo")
    plt.tight_layout()

    output_path = OUTPUT_DIR / f"heatmap_full_repository_metrics_{TIMESTAMP}.png"
    plt.savefig(output_path, dpi=300)
    plt.close()

    print(f"Heatmap salvo em: {output_path.resolve()}")


if __name__ == "__main__":
    main()