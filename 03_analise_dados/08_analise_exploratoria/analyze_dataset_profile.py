from pathlib import Path
from datetime import datetime

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
COLLECTED_SUMMARY_PATH = DATASET_DIR / "repositories_metrics_collected" / "repositories_detailed_summary.csv"

ANALYSIS_DIR = DATASET_DIR / "repositories_metrics_analysis" / "dataset_profile"
PLOTS_DIR = ANALYSIS_DIR / "plots"

PLOTS_DIR.mkdir(parents=True, exist_ok=True)

QUARTILE_LABELS = ["Q1", "Q2", "Q3", "Q4"]
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M")


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path.resolve()}")
    return pd.read_csv(path)


def add_star_quartile_column(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["stars"] = pd.to_numeric(df["stars"], errors="coerce")
    df = df[df["stars"].notna()].copy()

    df["star_quartile"] = pd.qcut(
        df["stars"],
        q=4,
        labels=QUARTILE_LABELS,
        duplicates="drop"
    )

    return df


def add_value_labels(ax, values, suffix=""):
    for i, value in enumerate(values):
        ax.text(
            i,
            value,
            f"{value:.2f}{suffix}",
            ha="center",
            va="bottom",
            fontsize=9
        )


def add_horizontal_value_labels(ax, values, suffix="%"):
    for i, value in enumerate(values):
        ax.text(
            value,
            i,
            f"{value:.2f}{suffix}",
            va="center",
            fontsize=9
        )


def save_bar_plot_with_labels(series, title, ylabel, filename, suffix=""):
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 6))
    series.plot(kind="bar", ax=ax)

    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.set_xticklabels(series.index, rotation=0)

    add_value_labels(ax, series.values, suffix=suffix)

    plt.tight_layout()

    output_path = PLOTS_DIR / f"{filename}_{TIMESTAMP}.png"
    plt.savefig(output_path, dpi=300)
    plt.close()

    print(f"Gráfico salvo: {output_path}")


def save_horizontal_bar_plot_with_labels(series, title, xlabel, filename):
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    series = series.sort_values()

    fig, ax = plt.subplots(figsize=(10, 6))
    series.plot(kind="barh", ax=ax)

    ax.set_title(title)
    ax.set_xlabel(xlabel)

    add_horizontal_value_labels(ax, series.values)

    plt.tight_layout()

    output_path = PLOTS_DIR / f"{filename}_{TIMESTAMP}.png"
    plt.savefig(output_path, dpi=300)
    plt.close()

    print(f"Gráfico salvo: {output_path}")


def save_boxplots_as_subplots_by_quartile(df, column, title, ylabel, filename):
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    axes = axes.flatten()

    for i, quartile in enumerate(QUARTILE_LABELS):
        ax = axes[i]

        values = pd.to_numeric(
            df.loc[df["star_quartile"] == quartile, column],
            errors="coerce"
        ).dropna()

        if values.empty:
            ax.set_title(f"{quartile} - sem dados")
            ax.axis("off")
            continue

        ax.boxplot(
            values,
            showfliers=False,
            showmeans=True,
            meanprops={
                "marker": "D",
                "markerfacecolor": "white",
                "markeredgecolor": "black",
                "markersize": 5,
            }
        )

        ax.set_title(f"{quartile}")
        ax.set_ylabel(ylabel)
        ax.set_xticks([1])
        ax.set_xticklabels([quartile])

    fig.suptitle(title)
    plt.tight_layout()

    output_path = PLOTS_DIR / f"{filename}_{TIMESTAMP}.png"
    plt.savefig(output_path, dpi=300)
    plt.close()

    print(f"Gráfico salvo: {output_path}")

    return output_path


def combine_images_vertically(image_paths, filename):
    images = [Image.open(path).convert("RGB") for path in image_paths]

    max_width = max(img.width for img in images)
    total_height = sum(img.height for img in images)

    combined = Image.new("RGB", (max_width, total_height), color="white")

    y_offset = 0
    for img in images:
        x_offset = (max_width - img.width) // 2
        combined.paste(img, (x_offset, y_offset))
        y_offset += img.height

    output_path = PLOTS_DIR / f"{filename}_{TIMESTAMP}.png"
    combined.save(output_path)

    print(f"Imagem combinada salva: {output_path}")

    return output_path


def main():
    filtered_df = read_csv(FILTERED_PATH)
    summary_df = read_csv(COLLECTED_SUMMARY_PATH)

    filtered_df = add_star_quartile_column(filtered_df)

    summary_df["issues_collected"] = pd.to_numeric(summary_df["issues_collected"], errors="coerce")
    summary_df["prs_collected"] = pd.to_numeric(summary_df["prs_collected"], errors="coerce")
    summary_df["releases_collected"] = pd.to_numeric(summary_df["releases_collected"], errors="coerce")

    merged_df = filtered_df.merge(
        summary_df[["full_name", "issues_collected", "prs_collected", "releases_collected"]],
        on="full_name",
        how="left"
    )

    # 1. Repositórios por quartil em percentual com valor no gráfico
    repos_by_quartile_percent = (
            merged_df["star_quartile"]
            .value_counts(normalize=True)
            .reindex(QUARTILE_LABELS, fill_value=0) * 100
    )

    save_bar_plot_with_labels(
        repos_by_quartile_percent,
        "Distribuição Percentual de Repositórios por Quartil",
        "Percentual (%)",
        "repositories_by_quartile_percent",
        suffix="%"
    )

    # 2. Totais globais de artefatos
    totals_series = pd.Series({
        "Issues": merged_df["issues_collected"].fillna(0).sum(),
        "PRs": merged_df["prs_collected"].fillna(0).sum(),
        "Releases": merged_df["releases_collected"].fillna(0).sum(),
    })

    save_bar_plot_with_labels(
        totals_series,
        "Quantidade Total de Artefatos",
        "Quantidade",
        "global_totals",
        suffix=""
    )

    # 3. Linguagens com Pareto 80% e percentual escrito
    language_percent = (
            merged_df["primary_language"]
            .fillna("Unknown")
            .value_counts(normalize=True) * 100
    )

    cumulative = language_percent.cumsum()
    pareto_languages = language_percent[cumulative <= 80]

    if pareto_languages.sum() < 80 and len(pareto_languages) < len(language_percent):
        next_language = language_percent.iloc[[len(pareto_languages)]]
        pareto_languages = pd.concat([pareto_languages, next_language])

    save_horizontal_bar_plot_with_labels(
        pareto_languages,
        "Linguagens que Representam Aproximadamente 80% dos Repositórios",
        "Percentual (%)",
        "language_pareto_80"
    )

    # 4. Boxplots separados
    issues_path = save_boxplots_as_subplots_by_quartile(
        merged_df,
        "issues_collected",
        "Distribuição de Issues por Quartil",
        "Issues",
        "boxplot_issues"
    )

    prs_path = save_boxplots_as_subplots_by_quartile(
        merged_df,
        "prs_collected",
        "Distribuição de Pull Requests por Quartil",
        "PRs",
        "boxplot_prs"
    )

    releases_path = save_boxplots_as_subplots_by_quartile(
        merged_df,
        "releases_collected",
        "Distribuição de Releases por Quartil",
        "Releases",
        "boxplot_releases"
    )

    # 5. Imagem única vertical com os três boxplots
    combine_images_vertically(
        [issues_path, prs_path, releases_path],
        "boxplot_artifacts_combined"
    )

    print(f"\nGráficos salvos em: {PLOTS_DIR.resolve()}")


if __name__ == "__main__":
    main()