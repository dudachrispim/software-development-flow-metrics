import csv
from collections import Counter
from datetime import datetime, timedelta, UTC
from pathlib import Path
from statistics import mean, median


def find_project_root(start: Path) -> Path:
    current = start.resolve()
    for parent in [current, *current.parents]:
        if (parent / "data").exists() and parent.name == "metrics-decision-impact":
            return parent
    raise RuntimeError("Raiz do projeto não encontrada.")

PROJECT_ROOT = find_project_root(Path(__file__))
DATASET_DIR = PROJECT_ROOT / "data" / "dataset_10000_stars"
FILTERED_DIR = DATASET_DIR / "repositories_filtered"

REJECTED_PATH = FILTERED_DIR / "repositories_rejected.csv"
APPROVED_PATH = FILTERED_DIR / "repositories_filtered.csv"


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        print(f"Arquivo não encontrado: {path.resolve()}")
        return []

    with path.open(mode="r", encoding="utf-8") as csvfile:
        return list(csv.DictReader(csvfile))


def parse_datetime(dt_str: str):
    if not dt_str:
        return None
    return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))


def days_since_pushed(pushed_at: str) -> int | None:
    pushed_date = parse_datetime(pushed_at)
    if pushed_date is None:
        return None

    now = datetime.now(UTC)
    delta = now - pushed_date
    return delta.days


def summarize_pushed_dates(rows: list[dict], title: str):
    values = []

    for row in rows:
        days = days_since_pushed(row.get("pushed_at"))
        if days is not None:
            values.append(days)

    print(f"\n=== {title} ===")
    if not values:
        print("Nenhum dado de pushed_at disponível.")
        return

    print(f"Quantidade com pushed_at válido: {len(values)}")
    print(f"Média de dias desde último push: {round(mean(values), 2)}")
    print(f"Mediana de dias desde último push: {round(median(values), 2)}")
    print(f"Mínimo de dias desde último push: {min(values)}")
    print(f"Máximo de dias desde último push: {max(values)}")

    within_365 = sum(1 for v in values if v <= 365)
    within_730 = sum(1 for v in values if v <= 730)
    over_365 = sum(1 for v in values if v > 365)
    between_366_730 = sum(1 for v in values if 365 < v <= 730)
    over_730 = sum(1 for v in values if v > 730)

    print(f"Até 365 dias: {within_365}")
    print(f"Até 730 dias: {within_730}")
    print(f"Mais de 365 dias: {over_365}")
    print(f"Entre 366 e 730 dias: {between_366_730}")
    print(f"Mais de 730 dias: {over_730}")


def summarize_rejection_reasons(rejected_rows: list[dict]):
    reason_counter = Counter()
    combination_counter = Counter()

    for row in rejected_rows:
        reasons_raw = row.get("rejection_reasons", "")
        reasons = [reason.strip() for reason in reasons_raw.split("|") if reason.strip()]

        for reason in reasons:
            reason_counter[reason] += 1

        if reasons:
            combination_counter[" | ".join(reasons)] += 1

    print("\n=== MOTIVOS DE REJEIÇÃO (INDIVIDUAIS) ===")
    for reason, count in reason_counter.most_common():
        print(f"{reason}: {count}")

    print("\n=== COMBINAÇÕES DE MOTIVOS DE REJEIÇÃO ===")
    for combo, count in combination_counter.most_common(15):
        print(f"{combo}: {count}")


def simulate_recent_activity_change(rejected_rows: list[dict], approved_rows: list[dict]):
    would_be_recovered = []
    still_rejected = []

    for row in rejected_rows:
        reasons_raw = row.get("rejection_reasons", "")
        reasons = [reason.strip() for reason in reasons_raw.split("|") if reason.strip()]

        days = days_since_pushed(row.get("pushed_at"))

        if days is None:
            still_rejected.append(row)
            continue

        # remove motivo de 365 dias, se existir
        new_reasons = [r for r in reasons if r != "pushed_at older than 365 days"]

        # se ainda está acima de 730, continua rejeitado por atividade
        if days > 730:
            new_reasons.append("pushed_at older than 730 days")

        if not new_reasons:
            would_be_recovered.append(row)
        else:
            row_copy = row.copy()
            row_copy["simulated_rejection_reasons_730"] = " | ".join(new_reasons)
            still_rejected.append(row_copy)

    print("\n=== SIMULAÇÃO: CRITÉRIO DE ATIVIDADE RECENTE = 730 DIAS ===")
    print(f"Aprovados atuais: {len(approved_rows)}")
    print(f"Rejeitados atuais: {len(rejected_rows)}")
    print(f"Repositórios que seriam recuperados ao mudar de 365 para 730 dias: {len(would_be_recovered)}")
    print(f"Novo total estimado de aprovados: {len(approved_rows) + len(would_be_recovered)}")

    if would_be_recovered:
        print("\nExemplos de repositórios recuperados:")
        for row in would_be_recovered[:10]:
            days = days_since_pushed(row.get('pushed_at'))
            print(
                f"- {row['full_name']} | "
                f"Pushed há {days} dias | "
                f"Motivos antigos: {row['rejection_reasons']}"
            )


def main():
    rejected_rows = read_csv(REJECTED_PATH)
    approved_rows = read_csv(APPROVED_PATH)

    if not rejected_rows:
        print("Nenhum rejeitado encontrado.")
        return

    print("=== RESUMO GERAL ===")
    print(f"Aprovados: {len(approved_rows)}")
    print(f"Rejeitados: {len(rejected_rows)}")

    summarize_rejection_reasons(rejected_rows)
    summarize_pushed_dates(rejected_rows, "PUSHED_AT DOS REJEITADOS")
    summarize_pushed_dates(approved_rows, "PUSHED_AT DOS APROVADOS")
    simulate_recent_activity_change(rejected_rows, approved_rows)


if __name__ == "__main__":
    main()