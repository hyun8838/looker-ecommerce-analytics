"""Create the core and page marts in dependency order."""
import os
from pathlib import Path

from google.cloud import bigquery

PROJECT = os.environ.get("BQ_PROJECT", "thelooker-ecommerce")
DATASET = os.environ.get("BQ_DATASET", "data_mart")
SQL_DIR = Path(__file__).resolve().parents[1] / "sql"
SQL_FILES = [
    "01_core.sql",
    "02_growth.sql",
    "03_sessions.sql",
    "04_transitions.sql",
    "05_cohorts.sql",
    "06_retention.sql",
    "07_products.sql",
    "08_customers.sql",
]


def main():
    client = bigquery.Client(project=PROJECT)
    for name in SQL_FILES:
        path = SQL_DIR / name
        query = path.read_text(encoding="utf-8")
        query = query.replace("{{PROJECT}}", PROJECT).replace("{{DATASET}}", DATASET)
        print("Running:", path.name)
        client.query(query).result()
    print("All marts refreshed.")


if __name__ == "__main__":
    main()
