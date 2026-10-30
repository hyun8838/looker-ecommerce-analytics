from pathlib import Path
from functools import lru_cache
import pandas as pd

# 앱 디렉터리를 기준으로 데이터 경로 계산
BASE_DIR = Path(__file__).resolve().parent.parent
PARQUET_DIR = BASE_DIR / "data" / "parquet"

@lru_cache(maxsize=32)
def load_parquet(table_name: str) -> pd.DataFrame:
    """
    parquet 파일명에서 .parquet를 제외한 table_name을 넣으면 DataFrame 반환
    예: load_parquet("mart_growth_kpi")
    """
    path = PARQUET_DIR / f"{table_name}.parquet"

    if not path.exists():
        raise FileNotFoundError(f"Parquet 파일이 없습니다: {path}")

    return pd.read_parquet(path)

def clear_parquet_cache():
    load_parquet.cache_clear()