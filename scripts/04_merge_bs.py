"""
04_merge_bs.py — Сопоставление с БС по адресу + row-count балансировка
"""

import logging
import yaml
from pathlib import Path
import pandas as pd

with open("config/config.yaml") as f:
    config = yaml.safe_load(f)

OUTPUT_TABLES = Path(config["paths"]["output_tables"])
OUTPUT_LOGS = Path(config["paths"]["output_logs"])

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(OUTPUT_LOGS / "04_merge.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

def normalize_address(series):
    """Очистить адрес: нижний регистр, убрать лишние пробелы."""
    return series.astype(str).str.lower().str.strip().str.replace(r'\s+', ' ', regex=True)

def merge_with_report(billing, stations):
    log.info("=== Сопоставление с БС по адресу ===")
    
    input_rows = len(billing)
    
    # Найти столбцы с адресом
    billing_addr_col = None
    for c in billing.columns:
        if "адрес" in c.lower() and "начало" in c.lower():
            billing_addr_col = c
            break
    if not billing_addr_col:
        for c in billing.columns:
            if "адрес" in c.lower():
                billing_addr_col = c
                break
    
    stations_addr_col = None
    for c in stations.columns:
        if c == "address" or "адрес" in c.lower() or "место размещения" in c.lower():
            stations_addr_col = c
            break
    
    log.info("Адрес в детализации: %s", billing_addr_col)
    log.info("Адрес в справочнике: %s", stations_addr_col)
    
    # Проверить примеры НЕпустых адресов
    billing_sample = billing[billing[billing_addr_col].notna() & (billing[billing_addr_col].astype(str).str.strip() != "")]
    stations_sample = stations[stations[stations_addr_col].notna() & (stations[stations_addr_col].astype(str).str.strip() != "")]
    
    log.info("Пример адреса (детализация, непустой): %s", 
             billing_sample[billing_addr_col].iloc[0] if not billing_sample.empty else "ВСЕ ПУСТЫЕ")
    log.info("Пример адреса (справочник, непустой): %s", 
             stations_sample[stations_addr_col].iloc[0] if not stations_sample.empty else "ВСЕ ПУСТЫЕ")
    
    # Нормализация адресов
    billing["_addr_norm"] = normalize_address(billing[billing_addr_col])
    stations["_addr_norm"] = normalize_address(stations[stations_addr_col])
    
    # Убрать пустые и NaN из ключей
    billing["_addr_norm"] = billing["_addr_norm"].replace({"nan": None, "": None, "none": None})
    stations["_addr_norm"] = stations["_addr_norm"].replace({"nan": None, "": None, "none": None})
    
    # Разделить на записи с адресом и без
    billing_with_addr = billing[billing["_addr_norm"].notna()].copy()
    billing_without_addr = billing[billing["_addr_norm"].isna()].copy()
    
    log.info("Записей с адресом: %d, без адреса: %d", len(billing_with_addr), len(billing_without_addr))
    
    if len(billing_with_addr) == 0:
        log.warning("⚠️ Все записи без адреса — сопоставление невозможно")
        return billing, pd.DataFrame()
    
    # Merge по нормализованному адресу (только для записей с адресом)
    merged = billing_with_addr.merge(
        stations[stations["_addr_norm"].notna()].drop_duplicates(subset=["_addr_norm"]),
        on="_addr_norm",
        how="left",
        suffixes=("_billing", "_bs"),
        indicator=True
    )
    
    matched = merged[merged["_merge"] == "both"].drop(columns=["_merge", "_addr_norm"])
    unmatched_with_addr = merged[merged["_merge"] == "left_only"].drop(columns=["_merge", "_addr_norm"])
    
    # Объединить несопоставленные: те, что без адреса + те, что с адресом но не нашлись
    unmatched = pd.concat([billing_without_addr.drop(columns=["_addr_norm"]), unmatched_with_addr], ignore_index=True)
    
    log.info("Сопоставлено: %d / %d (%.1f%%)", len(matched), input_rows, 100*len(matched)/input_rows)
    log.info("НЕ сопоставлено: %d (без адреса: %d, адрес не найден: %d)", 
             len(unmatched), len(billing_without_addr), len(unmatched_with_addr))
    
    # Row-count балансировка
    balance = len(matched) + len(unmatched)
    if balance == input_rows:
        log.info("✅ БАЛАНС: %d = %d + %d", input_rows, len(matched), len(unmatched))
    else:
        log.error("❌ ДИСБАЛАНС: %d ≠ %d + %d (разница: %d)", input_rows, len(matched), len(unmatched), input_rows - balance)
    
    return matched, unmatched

if __name__ == "__main__":
    billing = pd.read_parquet(OUTPUT_TABLES / "billing_extracted.parquet")
    stations = pd.read_parquet(OUTPUT_TABLES / "stations_validated.parquet")
    
    matched, unmatched = merge_with_report(billing, stations)
    
    matched.to_parquet(OUTPUT_TABLES / "matched.parquet", index=False)
    matched.to_excel(OUTPUT_TABLES / "matched.xlsx", index=False)
    
    if len(unmatched) > 0:
        unmatched.to_parquet(OUTPUT_TABLES / "unmatched.parquet", index=False)
        unmatched.to_excel(OUTPUT_TABLES / "unmatched.xlsx", index=False)
    
    from ai_formats import save_ai_formats
    save_ai_formats(matched, unmatched, OUTPUT_TABLES)
    
    log.info("=== Сопоставление завершено ===")
