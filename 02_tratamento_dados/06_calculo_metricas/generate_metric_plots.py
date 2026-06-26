import csv
import math
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


def find_project_root(start: Path) -> Path:
    current = start.resolve()
    for parent in [current, *current.parents]:
        if (parent / "data").exists() and parent.name == "metrics-decision-impact":
            return parent
    raise RuntimeError("Raiz do projeto não encontrada.")

PROJECT_ROOT = find_project_root(Path(__file__))
DATASET_DIR = PROJECT_ROOT / "data" / "dataset_10000_stars"

INPUT_PATH = DATASET_DIR / "repositories_metrics_final" / "repositories_metrics_final.csv"

ANALYSIS_DIR = DATASET_DIR / "repositories_metrics_analysis"
PLOTS_DIR = ANALYSIS_DIR / "plots"

PLOTS_DIR.mkdir(parents=True, exist_ok=True)


def read_metrics_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path.resolve()}")

    df = pd.read_csv(path)
    return df


def save_histogram(df: pd.DataFrame, column: str, title: str, filename: str, bins: int = 30):
    data = pd.to_numeric(df[column], errors="coerce").dropna()
    if data.empty:
        print(f"Sem dados para histograma: {column}")
        return

    plt.figure(figsize=(10, 6))
    plt.hist(data, bins=bins)
    plt.xlabel(column)
    plt.ylabel("Frequência")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / filename, dpi=300)
    plt.close()


def save_boxplot(df: pd.DataFrame, columns: list[str], title: str, filename: str):
    cleaned = []
    labels = []

    for col in columns:
        data = pd.to_numeric(df[col], errors="coerce").dropna()
        if not data.empty:
            cleaned.append(data)
            labels.append(col)

    if not cleaned:
        print(f"Sem dados para boxplot: {columns}")
        return

    plt.figure(figsize=(10, 6))
    plt.boxplot(cleaned, tick_labels=labels)
    plt.ylabel("Valor")
    plt.title(title)
    plt.xticks(rotation=20)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / filename, dpi=300)
    plt.close()


def save_scatter(df: pd.DataFrame, x_col: str, y_col: str, title: str, filename: str):
    plot_df = df[[x_col, y_col]].copy()
    plot_df[x_col] = pd.to_numeric(plot_df[x_col], errors="coerce")
    plot_df[y_col] = pd.to_numeric(plot_df[y_col], errors="coerce")
    plot_df = plot_df.dropna()

    if plot_df.empty:
        print(f"Sem dados para scatter: {x_col} x {y_col}")
        return

    plt.figure(figsize=(10, 6))
    plt.scatter(plot_df[x_col], plot_df[y_col], alpha=0.6)
    plt.xlabel(x_col)
    plt.ylabel(y_col)
    plt.title(title)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / filename, dpi=300)
    plt.close()


def save_correlation_heatmap(df: pd.DataFrame, columns: list[str], filename: str):
    corr_df = df[columns].copy()
    for col in columns:
        corr_df[col] = pd.to_numeric(corr_df[col], errors="coerce")

    corr = corr_df.corr(numeric_only=True)

    if corr.empty:
        print("Sem dados para heatmap de correlação.")
        return

    plt.figure(figsize=(10, 8))
    plt.imshow(corr, aspect="auto")
    plt.colorbar()
    plt.xticks(range(len(corr.columns)), corr.columns, rotation=45, ha="right")
    plt.yticks(range(len(corr.index)), corr.index)
    plt.title("Heatmap de Correlação entre Métricas")
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / filename, dpi=300)
    plt.close()


def main():
    df = read_metrics_csv(INPUT_PATH)

    print(f"Total de repositórios no arquivo final: {len(df)}")

    # Histogramas
    save_histogram(
        df,
        "pr_cycle_time_mean_days",
        "Distribuição da Média do Lead Time de PR por Repositório",
        "hist_pr_cycle_time_mean.png",
    )

    save_histogram(
        df,
        "monthly_throughput_prs_mean",
        "Distribuição do Throughput Médio Mensal de PRs",
        "hist_throughput_mean.png",
    )

    save_histogram(
        df,
        "release_interval_mean_days",
        "Distribuição do Intervalo Médio entre Releases",
        "hist_release_interval_mean.png",
    )

    # Boxplots de estabilidade
    save_boxplot(
        df,
        [
            "pr_cycle_time_cv",
            "monthly_throughput_prs_cv",
            "release_interval_cv",
        ],
        "Comparação da Variabilidade das Métricas de Fluxo",
        "boxplot_metric_cvs.png",
    )

    save_boxplot(
        df,
        [
            "pr_cycle_time_mean_days",
            "pr_review_time_mean_days",
            "release_interval_mean_days",
        ],
        "Comparação das Métricas Temporais",
        "boxplot_temporal_metrics.png",
    )

    # Scatter plots para RQ3
    save_scatter(
        df,
        "pr_cycle_time_cv",
        "pr_cycle_time_mean_days",
        "Estabilidade vs Lead Time Médio de PR",
        "scatter_cv_vs_pr_cycle_time_mean.png",
    )

    save_scatter(
        df,
        "pr_cycle_time_cv",
        "monthly_throughput_prs_mean",
        "Estabilidade vs Throughput Médio Mensal",
        "scatter_cv_vs_throughput_mean.png",
    )

    save_scatter(
        df,
        "release_interval_cv",
        "release_interval_mean_days",
        "Variabilidade vs Intervalo Médio entre Releases",
        "scatter_release_cv_vs_mean.png",
    )

    # Heatmap de correlação
    correlation_columns = [
        "pr_cycle_time_mean_days",
        "pr_cycle_time_std_days",
        "pr_cycle_time_cv",
        "monthly_throughput_prs_mean",
        "monthly_throughput_prs_std",
        "monthly_throughput_prs_cv",
        "release_interval_mean_days",
        "release_interval_std_days",
        "release_interval_cv",
        "pr_review_time_mean_days",
        "pr_review_time_std_days",
        "pr_review_time_cv",
    ]

    save_correlation_heatmap(
        df,
        correlation_columns,
        "heatmap_correlations.png",
    )

    print(f"Gráficos salvos em: {PLOTS_DIR.resolve()}")


if __name__ == "__main__":
    main()