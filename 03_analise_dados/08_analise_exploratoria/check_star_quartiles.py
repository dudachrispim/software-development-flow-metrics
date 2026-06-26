from pathlib import Path
import pandas as pd


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


def main():
    filtered_df = pd.read_csv(FILTERED_PATH)
    metrics_df = pd.read_csv(METRICS_PATH)

    df = filtered_df.merge(
        metrics_df[["full_name"]],
        on="full_name",
        how="inner"
    )

    df["stars"] = pd.to_numeric(df["stars"], errors="coerce")
    df = df[df["stars"].notna()].copy()

    df["star_quartile"] = pd.qcut(
        df["stars"],
        q=4,
        labels=["Q1", "Q2", "Q3", "Q4"],
        duplicates="drop"
    )

    quartile_summary = (
        df.groupby("star_quartile", observed=False)
        .agg(
            repositories=("full_name", "count"),
            min_stars=("stars", "min"),
            max_stars=("stars", "max"),
            mean_stars=("stars", "mean"),
            median_stars=("stars", "median"),
        )
        .reset_index()
    )

    print("\n=== TOTAL FINAL ANALISADO ===")
    print(len(df))

    print("\n=== FAIXAS DE STARS POR QUARTIL ===")
    print(quartile_summary.to_string(index=False))

    print("\n=== PONTOS DE CORTE DOS QUARTIS ===")
    print(df["stars"].quantile([0.25, 0.50, 0.75]))


if __name__ == "__main__":
    main()