"""
02_validate.py — Нормализация + Hex→Dec + извлечение LAC/CI
"""

import logging
import yaml
from pathlib import Path
import pandas as pd

with open("config/config.yaml") as f:
    config = yaml.safe_load(f)
with open("config/column_aliases.yaml") as f:
    COLUMN_ALIASES = yaml.safe_load(f)

OUTPUT_TABLES = Path(config["paths"]["output_tables"])
OUTPUT_LOGS = Path(config["paths"]["output_logs"])

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(OUTPUT_LOGS / "02_validate.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

def extract_lac_ci(df):
    """Извлечь LAC и CI из поля М/П абонента (формат: MCC/MNC/LAC/CI или MCC/LAC/CI)."""
    mp_col = None
    for c in df.columns:
        if "М/П" in c or "м/п" in c or "БС абонента" in c:
            mp_col = c
            break
    
    if not mp_col:
        log.warning("Столбец М/П абонента не найден")
        return df
    
    log.info("Извлечение LAC/CI из: %s", mp_col)
    
    parts = df[mp_col].str.split("/", expand=True)
    
    if parts.shape[1] >= 4:
        # Формат: MCC/MNC/LAC/CI
        df["lac"] = pd.to_numeric(parts[2], errors="coerce").astype("Int64")
        df["ci"] = pd.to_numeric(parts[3], errors="coerce").astype("Int64")
        log.info("Формат: MCC/MNC/LAC/CI")
    elif parts.shape[1] >= 3:
        # Формат: MCC/LAC/CI
        df["lac"] = pd.to_numeric(parts[1], errors="coerce").astype("Int64")
        df["ci"] = pd.to_numeric(parts[2], errors="coerce").astype("Int64")
        log.info("Формат: MCC/LAC/CI")
    else:
        log.warning("Неизвестный формат М/П: %s", parts.shape[1])
        return df
    
    log.info("LAC извлечён: %d значений (null: %d)", df["lac"].notna().sum(), df["lac"].isna().sum())
    log.info("CI извлечён: %d значений (null: %d)", df["ci"].notna().sum(), df["ci"].isna().sum())
    
    return df

def normalize_lac_ci(value):
    """Hex→Dec нормализация."""
    if pd.isna(value):
        return None
    if isinstance(value, str) and value.strip().startswith("0x"):
        return int(value.strip(), 16)
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None

def normalize_columns(df, label=""):
    found = {}
    rename_map = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for col in df.columns:
            if col.strip() in aliases:
                rename_map[col] = canonical
                found[canonical] = col
                break
    if rename_map:
        df = df.rename(columns=rename_map)
        log.info("%s: Нормализовано: %s", label, list(rename_map.values()))
    return df

def validate(df, label):
    log.info("=== Валидация: %s ===", label)
    input_rows = len(df)
    df = normalize_columns(df, label)
    
    # Извлечь LAC/CI из М/П, если нет отдельных столбцов
    if "lac" not in df.columns or "ci" not in df.columns:
        df = extract_lac_ci(df)
    
    # Hex→Dec для lac и ci (если есть)
    for col in ["lac", "ci"]:
        if col in df.columns:
            df[col] = df[col].apply(normalize_lac_ci)
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
            log.info("%s → Int64 (null: %d)", col, df[col].isna().sum())
    
    dups = df.duplicated().sum()
    log.info("Дубликатов: %d", dups)
    log.info("ROW-COUNT: %d → %d", input_rows, len(df))
    
    return df

if __name__ == "__main__":
    billing = pd.read_parquet(OUTPUT_TABLES / "billing_raw.parquet")
    stations = pd.read_parquet(OUTPUT_TABLES / "stations_raw.parquet")
    
    billing = validate(billing, "Детализация")
    stations = validate(stations, "Справочник БС")
    
    billing.to_parquet(OUTPUT_TABLES / "billing_validated.parquet", index=False)
    stations.to_parquet(OUTPUT_TABLES / "stations_validated.parquet", index=False)
    log.info("=== Валидация завершена ===")
