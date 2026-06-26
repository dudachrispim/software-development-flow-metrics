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

METRICS = {
    "Cycle Time": ("pr_lead_time_mean_days", "dias"),
    "Throughput": ("monthly_throughput_prs_mean", "PRs/mês"),
    "Intervalo entre Releases": ("release_interval_mean_days", "dias"),
}


def main():
    filtered_df = pd.read_csv(FILTERED_PATH)
    metrics_df = pd.read_csv(METRICS_PATH)

    df = filtered_df.merge(metrics_df, on="full_name", how="inner")

    print("=== PRINCIPAIS OUTLIERS POR MÉTRICA ===")

    for label, (col, unit) in METRICS.items():
        df[col] = pd.to_numeric(df[col], errors="coerce")
        temp = df.dropna(subset=[col]).copy()

        q1 = temp[col].quantile(0.25)
        q3 = temp[col].quantile(0.75)
        iqr = q3 - q1
        upper = q3 + 1.5 * iqr

        outliers = temp[temp[col] > upper].copy()

        if outliers.empty:
            print(f"\n{label}: nenhum outlier encontrado.")
            continue

        top = outliers.sort_values(col, ascending=False).iloc[0]

        print(f"\n--- {label} ---")
        print(f"Total de outliers: {len(outliers)}")
        print(f"Repositório: {top['full_name']}")
        print(f"URL: https://github.com/{top['full_name']}")
        print(f"Linguagem: {top.get('primary_language', 'Não informado')}")
        print(f"Stars: {int(top['stars'])}")
        print(f"Valor: {round(top[col], 2)} {unit}")
        print(f"Descrição: {top.get('description', 'Não informado')}")


if __name__ == "__main__":
    main()