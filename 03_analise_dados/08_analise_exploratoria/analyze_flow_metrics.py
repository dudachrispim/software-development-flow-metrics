from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image


def find_project_root(start: Path) -> Path:
    current = start.resolve()
    for parent in [current, *current.parents]:
        if (parent / "data").exists() and parent.name == "metrics-decision-impact":
            return parent
    raise RuntimeError("Raiz do projeto não encontrada.")

PROJECT_ROOT = find_project_root(Path(__file__))
DATASET_DIR = PROJECT_ROOT / "data" / "dataset_10000_stars"

FILTERED_PATH = DATASET_DIR / "repositories_filtered" / "repositories_filtered.csv"
METRICS_PATH = DATASET_DIR / "repositories_metrics_final" / "repositories_metrics_final.csv"

ANALYSIS_DIR = DATASET_DIR / "repositories_metrics_analysis" / "flow_metrics"
PLOTS_DIR = ANALYSIS_DIR / "plots"
TABLES_DIR = ANALYSIS_DIR / "tables"

PLOTS_DIR.mkdir(parents=True, exist_ok=True)
TABLES_DIR.mkdir(parents=True, exist_ok=True)

QUARTILE_LABELS = ["Q1", "Q2", "Q3", "Q4"]
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M")


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Arquivo não encontrado: {path.resolve()}"
        )

    return pd.read_csv(path)


def add_star_quartile_column(df: pd.DataFrame) -> pd.DataFrame:
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


def print_top_outliers(
        df: pd.DataFrame,
        metric_col: str,
        label: str,
        top_n: int = 5
):
    temp = df[
        [
            "full_name",
            "stars",
            "star_quartile",
            metric_col
        ]
    ].copy()

    temp[metric_col] = pd.to_numeric(
        temp[metric_col],
        errors="coerce"
    )

    temp = temp.dropna(subset=[metric_col])

    if temp.empty:
        return

    q1 = temp[metric_col].quantile(0.25)
    q3 = temp[metric_col].quantile(0.75)

    iqr = q3 - q1
    upper = q3 + 1.5 * iqr

    outliers = temp[
        temp[metric_col] > upper
        ].sort_values(
        by=metric_col,
        ascending=False
    )

    print(f"\n=== Top outliers - {label} ===")
    print(f"Total de outliers: {len(outliers)}")

    if outliers.empty:
        return

    for _, row in outliers.head(top_n).iterrows():
        print(
            f"- {row['full_name']} | "
            f"Quartil: {row['star_quartile']} | "
            f"Stars: {int(row['stars'])} | "
            f"Valor: {round(row[metric_col], 2)}"
        )


def save_boxplot_by_quartile(
        df,
        column,
        title,
        ylabel,
        filename
):
    data = []
    labels = []

    for q in QUARTILE_LABELS:
        values = pd.to_numeric(
            df.loc[
                df["star_quartile"] == q,
                column
            ],
            errors="coerce"
        ).dropna()

        if not values.empty:
            data.append(values)
            labels.append(q)

    if not data:
        return None

    plt.figure(figsize=(10, 6))

    plt.boxplot(
        data,
        tick_labels=labels,
        showfliers=False,
        showmeans=True,
        meanprops={
            "marker": "D",
            "markerfacecolor": "white",
            "markeredgecolor": "black",
            "markersize": 6
        }
    )

    plt.title(title)
    plt.ylabel(ylabel)
    plt.xlabel("Quartil de Stars")

    plt.tight_layout()

    path = (
            PLOTS_DIR /
            f"{filename}_{TIMESTAMP}.png"
    )

    plt.savefig(path, dpi=300)
    plt.close()

    print(f"Gráfico salvo: {path}")

    return path


def combine_images_horizontally(
        image_paths,
        filename
):
    images = [
        Image.open(path).convert("RGB")
        for path in image_paths
    ]

    # escala das imagens
    scale = 0.65

    resized_images = []

    for img in images:
        new_width = int(img.width * scale)
        new_height = int(img.height * scale)

        resized_images.append(
            img.resize(
                (new_width, new_height),
                Image.LANCZOS
            )
        )

    total_width = sum(
        img.width for img in resized_images
    )

    max_height = max(
        img.height for img in resized_images
    )

    combined = Image.new(
        "RGB",
        (total_width, max_height),
        color="white"
    )

    x_offset = 0

    for img in resized_images:
        y_offset = (
                           max_height - img.height
                   ) // 2

        combined.paste(
            img,
            (x_offset, y_offset)
        )

        x_offset += img.width

    output_path = (
            PLOTS_DIR /
            f"{filename}_{TIMESTAMP}.png"
    )

    combined.save(output_path)

    print(f"Imagem combinada salva: {output_path}")

    return output_path


def save_stats_by_quartile(
        df: pd.DataFrame
):
    stats = (
        df.groupby(
            "star_quartile",
            observed=False
        )
        .agg(
            cycle_time_mean=(
                "pr_lead_time_mean_days",
                "mean"
            ),

            cycle_time_median=(
                "pr_lead_time_mean_days",
                "median"
            ),

            cycle_time_std=(
                "pr_lead_time_mean_days",
                "std"
            ),

            throughput_mean=(
                "monthly_throughput_prs_mean",
                "mean"
            ),

            throughput_median=(
                "monthly_throughput_prs_mean",
                "median"
            ),

            throughput_std=(
                "monthly_throughput_prs_mean",
                "std"
            ),

            release_interval_mean=(
                "release_interval_mean_days",
                "mean"
            ),

            release_interval_median=(
                "release_interval_mean_days",
                "median"
            ),

            release_interval_std=(
                "release_interval_mean_days",
                "std"
            ),
        )
        .reindex(QUARTILE_LABELS)
        .reset_index()
    )

    output_path = (
            TABLES_DIR /
            f"flow_metrics_stats_by_quartile_{TIMESTAMP}.csv"
    )

    stats.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig"
    )

    print(
        f"Tabela de estatísticas salva: "
        f"{output_path}"
    )


def main():
    filtered_df = read_csv(FILTERED_PATH)
    metrics_df = read_csv(METRICS_PATH)

    filtered_df = add_star_quartile_column(
        filtered_df
    )

    merged_df = filtered_df[
        [
            "full_name",
            "stars",
            "star_quartile"
        ]
    ].merge(
        metrics_df,
        on="full_name",
        how="inner"
    )

    numeric_cols = [
        "pr_lead_time_mean_days",
        "pr_lead_time_median_days",
        "pr_lead_time_std_days",
        "pr_lead_time_cv",

        "monthly_throughput_prs_mean",
        "monthly_throughput_prs_median",
        "monthly_throughput_prs_std",
        "monthly_throughput_prs_cv",

        "release_interval_mean_days",
        "release_interval_median_days",
        "release_interval_std_days",
        "release_interval_cv",
    ]

    for col in numeric_cols:
        if col in merged_df.columns:
            merged_df[col] = pd.to_numeric(
                merged_df[col],
                errors="coerce"
            )

    print(
        f"Total de repositórios analisados: "
        f"{len(merged_df)}"
    )

    # OUTLIERS
    print_top_outliers(
        merged_df,
        "pr_lead_time_mean_days",
        "Cycle Time"
    )

    print_top_outliers(
        merged_df,
        "monthly_throughput_prs_mean",
        "Throughput"
    )

    print_top_outliers(
        merged_df,
        "release_interval_mean_days",
        "Release Interval"
    )

    # TABELA
    save_stats_by_quartile(
        merged_df
    )

    # BOXPLOTS
    cycle_time_path = save_boxplot_by_quartile(
        merged_df,
        "pr_lead_time_mean_days",
        "Cycle Time Médio de PR por Quartil de Stars",
        "Dias",
        "boxplot_cycle_time"
    )

    throughput_path = save_boxplot_by_quartile(
        merged_df,
        "monthly_throughput_prs_mean",
        "Throughput Médio Mensal por Quartil",
        "PRs/mês",
        "boxplot_throughput"
    )

    release_interval_path = save_boxplot_by_quartile(
        merged_df,
        "release_interval_mean_days",
        "Intervalo Médio entre Releases por Quartil",
        "Dias",
        "boxplot_release_interval"
    )

    # IMAGEM COMBINADA
    combine_images_horizontally(
        [
            cycle_time_path,
            throughput_path,
            release_interval_path
        ],
        "boxplot_flow_metrics_combined_horizontal"
    )

    print(f"\nGráficos salvos em: {PLOTS_DIR}")
    print(f"Tabelas salvas em: {TABLES_DIR}")


if __name__ == "__main__":
    main()