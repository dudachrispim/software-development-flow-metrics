from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def find_project_root(start: Path) -> Path:
    current = start.resolve()
    for parent in [current, *current.parents]:
        if (parent / "data").exists() and parent.name == "metrics-decision-impact":
            return parent
    raise RuntimeError("Raiz do projeto não encontrada.")

PROJECT_ROOT = find_project_root(Path(__file__))
DATASET_DIR = PROJECT_ROOT / "data" / "dataset_10000_stars"

METRICS_PATH = DATASET_DIR / "repositories_metrics_final" / "repositories_metrics_final.csv"

OUTPUT_DIR = DATASET_DIR / "repositories_metrics_analysis" / "relationships"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M")


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path.resolve()}")
    return pd.read_csv(path)


def remove_outliers(df: pd.DataFrame, column: str) -> pd.DataFrame:
    series = pd.to_numeric(df[column], errors="coerce").dropna()

    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1

    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr

    return df[(df[column] >= lower) & (df[column] <= upper)]


def save_scatter(df, x_col, y_col, title, filename):
    plot_df = df[[x_col, y_col]].copy()
    plot_df[x_col] = pd.to_numeric(plot_df[x_col], errors="coerce")
    plot_df[y_col] = pd.to_numeric(plot_df[y_col], errors="coerce")
    plot_df = plot_df.dropna()

    plot_df = remove_outliers(plot_df, x_col)
    plot_df = remove_outliers(plot_df, y_col)

    plt.figure(figsize=(8, 6))
    sns.scatterplot(data=plot_df, x=x_col, y=y_col)

    plt.title(title)
    plt.tight_layout()

    path = OUTPUT_DIR / f"{filename}_{TIMESTAMP}.png"
    plt.savefig(path, dpi=300)
    plt.close()

    print(f"Gráfico salvo: {path}")


def save_heatmap(df, columns, filename):
    corr = df[columns].corr()

    plt.figure(figsize=(8, 6))
    sns.heatmap(corr, annot=True, cmap="coolwarm", fmt=".2f")

    plt.title("Correlação entre métricas")
    plt.tight_layout()

    path = OUTPUT_DIR / f"{filename}_{TIMESTAMP}.png"
    plt.savefig(path, dpi=300)
    plt.close()

    print(f"Heatmap salvo: {path}")


def main():
    df = read_csv(METRICS_PATH)

    # 🔥 usar lead_time como cycle time
    df = df.rename(columns={
        "pr_lead_time_mean_days": "pr_cycle_time_mean_days",
        "pr_lead_time_cv": "pr_cycle_time_cv",
    })

    numeric_cols = [
        "pr_cycle_time_mean_days",
        "pr_cycle_time_cv",
        "monthly_throughput_prs_mean",
        "release_interval_mean_days",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # 🔹 Scatter plots
    save_scatter(
        df,
        "pr_cycle_time_cv",
        "pr_cycle_time_mean_days",
        "Estabilidade (CV) vs Cycle Time",
        "scatter_cv_vs_cycle_time",
    )

    save_scatter(
        df,
        "pr_cycle_time_cv",
        "monthly_throughput_prs_mean",
        "Estabilidade (CV) vs Throughput",
        "scatter_cv_vs_throughput",
    )

    # 🔹 Heatmap
    save_heatmap(
        df,
        [
            "pr_cycle_time_mean_days",
            "pr_cycle_time_cv",
            "monthly_throughput_prs_mean",
            "release_interval_mean_days",
        ],
        "heatmap_correlation",
    )

    print(f"\nGráficos salvos em: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()