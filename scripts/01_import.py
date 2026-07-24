"""
01_import.py — Импорт файлов + SHA-256 + все листы + row-count
Сохраняет промежуточные данные в Parquet (.parquet)
"""

import hashlib
import logging
import yaml
from pathlib import Path
from datetime import datetime
import pandas as pd

with open("config/config.yaml") as f:
    config = yaml.safe_load(f)

INPUT_BS = Path(config["paths"]["input_bs"])
INPUT_BILLING = Path(config["paths"]["input_billing"])
OUTPUT_MANIFESTS = Path(config["paths"]["output_manifests"])
OUTPUT_TABLES = Path(config["paths"]["output_tables"])
OUTPUT_LOGS = Path(config["paths"]["output_logs"])

for d in [OUTPUT_MANIFESTS, OUTPUT_TABLES, OUTPUT_LOGS]:
    d.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(OUTPUT_LOGS / "01_import.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

MANIFEST_FILE = OUTPUT_MANIFESTS / "manifest_sha256.csv"

def compute_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def check_manifest(filepath, sha256):
    if MANIFEST_FILE.exists():
        manifest = pd.read_csv(MANIFEST_FILE)
        row = manifest[manifest["filepath"] == str(filepath)]
        if not row.empty:
            old_sha = row.iloc[0]["sha256"]
            if old_sha != sha256:
                log.error("⚠️ Файл изменён: %s", filepath.name)
                return False
            log.info("✅ Файл не изменён: %s", filepath.name)
            return True
    log.info("🆕 Новый файл: %s", filepath.name)
    return True

def update_manifest(filepath, sha256, rows, sheets, size_mb):
    record = {
        "timestamp": datetime.now().isoformat(),
        "filename": filepath.name,
        "filepath": str(filepath),
        "sha256": sha256,
        "size_mb": round(size_mb, 2),
        "rows": rows,
        "sheets": ",".join(sheets) if sheets else "0",
        "modified": datetime.fromtimestamp(filepath.stat().st_mtime).isoformat()
    }
    df = pd.DataFrame([record])
    if MANIFEST_FILE.exists():
        existing = pd.read_csv(MANIFEST_FILE)
        existing = existing[existing["filepath"] != str(filepath)]
        df = pd.concat([existing, df], ignore_index=True)
    df.to_csv(MANIFEST_FILE, index=False)

def read_excel_all_sheets(filepath):
    log.info("📄 Чтение: %s", filepath.name)
    
    sheets = []
    df = None
    
    if filepath.suffix == ".xlsb":
        # Пробуем calamine, затем pyxlsb, затем openpyxl
        for engine in ["calamine", "pyxlsb"]:
            try:
                excel = pd.ExcelFile(filepath, engine=engine)
                sheets = excel.sheet_names
                if sheets:
                    log.info("  Движок: %s", engine)
                    break
                else:
                    log.warning("  %s: листов не найдено", engine)
            except Exception as e:
                log.warning("  %s: %s", engine, e)
        
        if not sheets:
            log.error("  ❌ Не удалось прочитать файл ни одним движком")
            return None, [], 0
    else:
        excel = pd.ExcelFile(filepath, engine="openpyxl")
        sheets = excel.sheet_names
    
    if not sheets:
        log.warning("  ⚠️ Файл пустой (нет листов)")
        return None, [], 0
    
    log.info("  Листов: %d — %s", len(sheets), sheets)
    
    dfs = []
    total_rows = 0
    for sheet in sheets:
        df_sheet = pd.read_excel(excel, sheet_name=sheet)
        total_rows += len(df_sheet)
        log.info("  Лист '%s': %d строк", sheet, len(df_sheet))
        dfs.append(df_sheet)
    
    result = pd.concat(dfs, ignore_index=True)
    
    # Преобразовать все столбцы в строки для совместимости с Parquet
    for col in result.columns:
        try:
            result[col] = result[col].astype(str)
        except Exception:
            pass
    
    log.info("  Всего строк: %d", total_rows)
    
    return result, sheets, total_rows

def import_all(category, input_dir, output_name):
    log.info("=== Импорт: %s ===", category)
    files = list(input_dir.glob("*.xls*"))
    
    if not files:
        log.error("Файлы не найдены в %s", input_dir)
        return None, 0
    
    all_dfs = []
    grand_total = 0
    
    for f in files:
        sha = compute_sha256(f)
        check_manifest(f, sha)
        size_mb = f.stat().st_size / (1024 * 1024)
        
        try:
            df, sheets, rows = read_excel_all_sheets(f)
            if df is not None:
                all_dfs.append(df)
                grand_total += rows
                update_manifest(f, sha, rows, sheets, size_mb)
            else:
                update_manifest(f, sha, 0, sheets, size_mb)
        except Exception as e:
            log.error("  ❌ Ошибка: %s", e)
    
    if all_dfs:
        result = pd.concat(all_dfs, ignore_index=True)
        result.to_parquet(OUTPUT_TABLES / f"{output_name}.parquet", index=False)
        log.info("✅ %s сохранён: %d файлов, %d строк", output_name, len(files), grand_total)
        return result, grand_total
    return None, 0

if __name__ == "__main__":
    billing, billing_rows = import_all("Детализации", INPUT_BILLING, "billing_raw")
    stations, stations_rows = import_all("Справочники БС", INPUT_BS, "stations_raw")
    
    log.info("=== ROW-COUNT ===")
    log.info("Детализации: %d строк", billing_rows)
    log.info("Справочники БС: %d строк", stations_rows)
    log.info("=== Импорт завершён ===")
