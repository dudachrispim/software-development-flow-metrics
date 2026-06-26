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
SUMMARY_PATH = DATASET_DIR / "repositories_metrics_collected" / "repositories_detailed_summary.csv"
METRICS_PATH = DATASET_DIR / "repositories_metrics_final" / "repositories_metrics_final.csv"

OUTPUT_DIR = DATASET_DIR / "repositories_metrics_analysis" / "outliers"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_PATH = OUTPUT_DIR / "metric_outliers.csv"


METRICS = {
    "cycle_time": {
        "column": "pr_lead_time_mean_days",
        "label": "Cycle Time médio de PR",
        "unit": "dias",
    },
    "throughput": {
        "column": "monthly_throughput_prs_mean",
        "label": "Throughput médio mensal",
        "unit": "PRs/mês",
    },
    "release_interval": {
        "column": "release_interval_mean_days",
        "label": "Intervalo médio entre releases",
        "unit": "dias",
    },
    "cycle_time_cv": {
        "column": "pr_lead_time_cv",
        "label": "Coeficiente de variação do Cycle Time",
        "unit": "",
    },
    "throughput_cv": {
        "column": "monthly_throughput_prs_cv",
        "label": "Coeficiente de variação do Throughput",
        "unit": "",
    },
    "release_interval_cv": {
        "column": "release_interval_cv",
        "label": "Coeficiente de variação do intervalo entre releases",
        "unit": "",
    },
}


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path.resolve()}")
    return pd.read_csv(path)


def first_existing_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def build_repo_url(full_name: str) -> str:
    if pd.isna(full_name):
        return ""
    return f"https://github.com/{full_name}"


def detect_upper_outliers(df: pd.DataFrame, metric_key: str, metric_info: dict) -> pd.DataFrame:
    metric_col = metric_info["column"]

    if metric_col not in df.columns:
        print(f"[AVISO] Coluna não encontrada para {metric_info['label']}: {metric_col}")
        return pd.DataFrame()

    temp = df.copy()
    temp[metric_col] = pd.to_numeric(temp[metric_col], errors="coerce")
    temp = temp[temp[metric_col].notna()].copy()

    if temp.empty:
        return pd.DataFrame()

    q1 = temp[metric_col].quantile(0.25)
    q3 = temp[metric_col].quantile(0.75)
    iqr = q3 - q1
    upper_limit = q3 + 1.5 * iqr

    outliers = temp[temp[metric_col] > upper_limit].copy()
    outliers = outliers.sort_values(by=metric_col, ascending=False)

    if outliers.empty:
        return pd.DataFrame()

    language_col = first_existing_column(outliers, ["primary_language", "language"])
    description_col = first_existing_column(outliers, ["description", "repo_description"])
    contributors_col = first_existing_column(outliers, ["contributors_count", "contributors"])
    stars_col = first_existing_column(outliers, ["stars"])
    issues_col = first_existing_column(outliers, ["issues_collected", "issues_total"])
    prs_col = first_existing_column(outliers, ["prs_collected", "pull_requests_total", "prs_total"])
    releases_col = first_existing_column(outliers, ["releases_collected", "releases_total"])

    result = pd.DataFrame()
    result["metric_key"] = metric_key
    result["metric_label"] = metric_info["label"]
    result["metric_unit"] = metric_info["unit"]
    result["full_name"] = outliers["full_name"]
    result["url"] = outliers["full_name"].apply(build_repo_url)
    result["metric_value"] = outliers[metric_col]
    result["outlier_limit"] = upper_limit

    result["stars"] = outliers[stars_col] if stars_col else None
    result["language"] = outliers[language_col] if language_col else None
    result["contributors"] = outliers[contributors_col] if contributors_col else None
    result["issues"] = outliers[issues_col] if issues_col else None
    result["prs"] = outliers[prs_col] if prs_col else None
    result["releases"] = outliers[releases_col] if releases_col else None
    result["description"] = outliers[description_col] if description_col else None

    return result


def main():
    filtered_df = read_csv(FILTERED_PATH)
    summary_df = read_csv(SUMMARY_PATH)
    metrics_df = read_csv(METRICS_PATH)

    df = filtered_df.merge(summary_df, on="full_name", how="left")
    df = df.merge(metrics_df, on="full_name", how="left")

    all_outliers = []

    print("=== IDENTIFICAÇÃO DE OUTLIERS ===")

    for metric_key, metric_info in METRICS.items():
        outliers = detect_upper_outliers(df, metric_key, metric_info)

        print(f"\n--- {metric_info['label']} ---")
        print(f"Total de outliers: {len(outliers)}")

        if not outliers.empty:
            print("Top 3 maiores:")
            for _, row in outliers.head(3).iterrows():
                value = round(row["metric_value"], 2)
                unit = row["metric_unit"]

                print(
                    f"- {row['full_name']} | "
                    f"{value} {unit} | "
                    f"Linguagem: {row['language']} | "
                    f"Stars: {row['stars']} | "
                    f"Contribuidores: {row['contributors']} | "
                    f"URL: {row['url']} | "
                    f"Descrição: {row['description']}"
                )

            all_outliers.append(outliers)

    if all_outliers:
        final_df = pd.concat(all_outliers, ignore_index=True)
        final_df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
        print(f"\nCSV salvo em: {OUTPUT_PATH.resolve()}")
    else:
        print("\nNenhum outlier identificado.")


if __name__ == "__main__":
    main()