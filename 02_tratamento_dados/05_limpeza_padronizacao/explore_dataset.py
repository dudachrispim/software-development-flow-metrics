import pandas as pd

FILE = "data/raw/repositories_detailed_summary.csv"

df = pd.read_csv(FILE)

language_counts = (
    df["primary_language"]
    .fillna("Unknown")
    .value_counts()
)

print("\nTop linguagens:\n")
print(language_counts.head(20))

print("\nTotal de repositórios:", len(df))
print("Total de linguagens diferentes:", df["primary_language"].nunique())
