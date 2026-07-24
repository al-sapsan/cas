"""
03_extract_dates.py — Фильтрация по датам и времени
Парсит столбец 'Дата и время' в двух форматах
"""
import logging
import yaml
from pathlib import Path
import pandas as pd
import numpy as np

with open("config/config.yaml") as f:
    config = yaml.safe_load(f)

OUTPUT_TABLES = Path(config["paths"]["output_tables"])
OUTPUT_LOGS = Path(config["paths"]["output_logs"])
TARGET_DATES = config["analysis"]["target_dates"]
TIMEZONE = config["analysis"]["default_timezone"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(OUTPUT_LOGS / "03_extract.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

def extract_dates(df, target_dates, timezone):
    log.info("=== Извлечение по датам и времени ===")
    
    input_rows = len(df)
    date_col = "Дата и время"
    
    if date_col not in df.columns:
        log.error("Столбец '%s' не найден", date_col)
        return None
    
    # Парсить в ДВУХ форматах
    parsed_1 = pd.to_datetime(df[date_col], format="%d.%m.%Y %H:%M:%S", errors="coerce")
    parsed_2 = pd.to_datetime(df[date_col], format="ISO8601", errors="coerce")
    
    df["_dt"] = parsed_1.fillna(parsed_2)
    
    valid = df["_dt"].notna().sum()
    log.info("Распознано дат: %d / %d (fmt1: %d, fmt2: %d)", 
             valid, input_rows, parsed_1.notna().sum(), parsed_2.notna().sum())
    
    if valid == 0:
        log.error("Не удалось распознать даты")
        log.error("Примеры: %s", df[date_col].dropna().head(5).tolist())
        return None
    
    results = []
    for entry in target_dates:
        target_date = entry["date"]
        time_from = entry.get("time_from", "00:00")
        time_to = entry.get("time_to", "23:59")
        
        log.info("Обработка: %s (%s — %s)", target_date, time_from, time_to)
        
        target_dt = pd.to_datetime(target_date, format="%Y-%m-%d")
        date_mask = df["_dt"].dt.date == target_dt.date()
        subset = df[date_mask].copy()
        
        if len(subset) == 0:
            log.warning("  Нет записей за %s", target_date)
            continue
        
        t_from = pd.to_datetime(time_from, format="%H:%M").time()
        t_to = pd.to_datetime(time_to, format="%H:%M").time()
        subset_time = subset["_dt"].dt.time
        
        if t_from <= t_to:
            time_mask = (subset_time >= t_from) & (subset_time <= t_to)
        else:
            time_mask = (subset_time >= t_from) | (subset_time <= t_to)
        
        subset = subset[time_mask]
        log.info("  Записей: %d", len(subset))
        results.append(subset)
    
    if not results:
        log.warning("⚠️ Не найдено записей")
        return None
    
    result = pd.concat(results, ignore_index=True)
    result = result.drop(columns=["_dt"])
    
    log.info("ROW-COUNT: %d → %d", input_rows, len(result))
    return result

if __name__ == "__main__":
    billing = pd.read_parquet(OUTPUT_TABLES / "billing_validated.parquet")
    extracted = extract_dates(billing, TARGET_DATES, TIMEZONE)
    
    if extracted is not None and len(extracted) > 0:
        extracted.to_parquet(OUTPUT_TABLES / "billing_extracted.parquet", index=False)
        extracted.to_excel(OUTPUT_TABLES / "billing_extracted.xlsx", index=False)
        log.info("✅ Сохранено: %d записей", len(extracted))
    
    log.info("=== Извлечение завершено ===")
