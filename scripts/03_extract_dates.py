"""
03_extract_dates.py — Фильтрация по датам и времени
Парсит каждый столбец в своём формате
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
    log.info("Часовой пояс: %s", timezone)
    
    input_rows = len(df)
    
    # Объединить даты из всех столбцов, парся каждый в своём формате
    df["_date_combined"] = pd.NaT
    
    # Столбец 1: ДД.ММ.ГГГГ ЧЧ:ММ:СС
    if "Время начала соединения" in df.columns:
        parsed = pd.to_datetime(df["Время начала соединения"], format="%d.%m.%Y %H:%M:%S", errors="coerce")
        df["_date_combined"] = df["_date_combined"].fillna(parsed)
        log.info("Время начала соединения: распознано %d", parsed.notna().sum())
    
    # Столбец 2: ISO (YYYY-MM-DD HH:MM:SS)
    if "Дата и время" in df.columns:
        parsed = pd.to_datetime(df["Дата и время"], format="ISO8601", errors="coerce")
        df["_date_combined"] = df["_date_combined"].fillna(parsed)
        log.info("Дата и время: распознано %d", parsed.notna().sum())
    
    valid = df["_date_combined"].notna().sum()
    log.info("Всего распознано дат: %d / %d", valid, input_rows)
    
    if valid == 0:
        log.error("Не удалось распознать ни одной даты")
        return None
    
    # Фильтрация
    results = []
    for entry in target_dates:
        target_date = entry["date"]
        time_from = entry.get("time_from", "00:00")
        time_to = entry.get("time_to", "23:59")
        
        log.info("Обработка: %s (%s — %s)", target_date, time_from, time_to)
        
        target_dt = pd.to_datetime(target_date, format="%Y-%m-%d")
        date_mask = df["_date_combined"].dt.date == target_dt.date()
        subset = df[date_mask].copy()
        
        if len(subset) == 0:
            log.warning("  Нет записей за %s", target_date)
            continue
        
        t_from = pd.to_datetime(time_from, format="%H:%M").time()
        t_to = pd.to_datetime(time_to, format="%H:%M").time()
        subset_time = subset["_date_combined"].dt.time
        
        if t_from <= t_to:
            time_mask = (subset_time >= t_from) & (subset_time <= t_to)
        else:
            time_mask = (subset_time >= t_from) | (subset_time <= t_to)
        
        subset = subset[time_mask]
        log.info("  Записей: %d", len(subset))
        results.append(subset)
    
    if not results:
        log.warning("⚠️ Не найдено записей за указанные периоды!")
        return None
    
    result = pd.concat(results, ignore_index=True)
    result = result.drop(columns=["_date_combined"])
    
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
