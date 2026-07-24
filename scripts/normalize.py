"""
Нормализация исходных файлов с контролем целостности.
Извлекает LAC/CI из форматов: 12322/116175413 и 12362-115902250
"""
import pandas as pd
from pathlib import Path

INPUT_DIR = Path("input/billing")
OUTPUT_DIR = Path("input/normalized")
OUTPUT_DIR.mkdir(exist_ok=True)

def find_col(df, keywords):
    for kw in keywords:
        for c in df.columns:
            if kw.lower() in c.lower():
                return c
    return None

def extract_lac_ci(value):
    """Извлечь LAC и CI из строки: 12322/116175413 или 12362-115902250"""
    if pd.isna(value):
        return None, None
    s = str(value).strip().replace(" ", "")
    if not s or s in ["nan", "None", ""]:
        return None, None
    
    # Формат 1: 12322/116175413
    if "/" in s:
        parts = s.split("/")
        if len(parts) >= 3:
            return parts[-2], parts[-1]
        if len(parts) == 2:
            return parts[0], parts[1]
    
    # Формат 2: 12362-115902250
    if "-" in s:
        parts = s.split("-")
        if len(parts) == 2:
            return parts[0], parts[1]
    
    # Формат 3: просто число (только CI, LAC из другого столбца)
    if s.isdigit():
        return None, s
    
    return None, None

def fill_rate(col, total):
    return (col.notna().sum() / total * 100) if total > 0 else 0

def normalize_file(filepath):
    print(f"\n{'='*60}")
    print(f"📄 {filepath.name}")
    print(f"{'='*60}")
    
    engine = "pyxlsb" if filepath.suffix == ".xlsb" else "openpyxl"
    try:
        excel = pd.ExcelFile(filepath, engine=engine)
    except:
        engine = "openpyxl" if engine == "pyxlsb" else "pyxlsb"
        excel = pd.ExcelFile(filepath, engine=engine)
    
    all_sheets = []
    total_rows_in = 0
    
    for sheet in excel.sheet_names:
        df = pd.read_excel(excel, sheet_name=sheet)
        rows = len(df)
        total_rows_in += rows
        norm = pd.DataFrame()
        
        # Дата и время
        col = find_col(df, ["время начала", "дата и время", "date", "time", "timestamp"])
        if col:
            norm["Дата и время"] = df[col]
        
        # Номер абонента
        col = find_col(df, ["номер абонента", "номер а", "caller", "абонент"])
        if col:
            norm["Номер абонента"] = df[col].astype(str).str.strip().replace({"nan": "", "None": ""})
        
        # Номер контакта
        col = find_col(df, ["номер контакта", "номер б", "номер в", "callee", "вызываемый"])
        if col:
            norm["Номер контакта"] = df[col].astype(str).str.strip().replace({"nan": "", "None": ""})
        
        # Тип соединения
        col = find_col(df, ["тип соединения", "тип", "event", "call type"])
        if col:
            norm["Тип соединения"] = df[col]
        
        # Длительность
        col = find_col(df, ["длительность", "продолжительность", "duration"])
        if col:
            norm["Длительность (сек)"] = df[col]
        
        # IMEI
        col = find_col(df, ["imei", "IMEI"])
        if col:
            norm["IMEI"] = df[col]
        
        # LAC и CI — поиск по всем возможным столбцам
        lac_col = find_col(df, ["lac", "лак"])
        ci_col = find_col(df, ["ci", "си"])
        
        # Столбцы с составными идентификаторами
        bs_cols = []
        for c in df.columns:
            if "бс" in c.lower() or "м/п" in c.lower() or "мп" in c.lower() or "bs" in c.lower():
                bs_cols.append(c)
        
        # Извлечь LAC/CI из всех найденных столбцов
        lacs = [None] * rows
        cis = [None] * rows
        
        for bs_col in bs_cols:
            for i, v in enumerate(df[bs_col]):
                if lacs[i] is None and cis[i] is None:
                    lac, ci = extract_lac_ci(v)
                    if lac:
                        lacs[i] = lac
                    if ci:
                        cis[i] = ci
        
        # Если есть отдельные столбцы LAC/CI
        if lac_col:
            for i, v in enumerate(df[lac_col]):
                if lacs[i] is None:
                    lacs[i] = str(v).strip() if not pd.isna(v) else None
        if ci_col:
            for i, v in enumerate(df[ci_col]):
                if cis[i] is None:
                    cis[i] = str(v).strip() if not pd.isna(v) else None
        
        norm["LAC"] = lacs
        norm["CI"] = cis
        
        # Адрес БС
        col = find_col(df, ["адрес бс", "адрес", "address", "location"])
        if col:
            norm["Адрес БС"] = df[col].astype(str).str.strip().replace({"nan": "", "None": ""})
        
        # Азимут
        col = find_col(df, ["азимут", "azimuth"])
        if col:
            norm["Азимут"] = df[col]
        
        all_sheets.append(norm)
    
    result = pd.concat(all_sheets, ignore_index=True)
    total_rows_out = len(result)
    
    # Статистика
    print(f"\n  Строк: {total_rows_in} → {total_rows_out}")
    if total_rows_in == total_rows_out:
        print(f"  ✅ ROW-COUNT: совпадает ({total_rows_out})")
    else:
        print(f"  ❌ ROW-COUNT: расхождение на {total_rows_in - total_rows_out}")
    
    print(f"\n  Заполнение (% от {total_rows_out}):")
    for c in result.columns:
        rate = fill_rate(result[c], total_rows_out)
        bar = "█" * int(rate / 5) + "░" * (20 - int(rate / 5))
        status = "✅" if rate > 50 else "⚠️" if rate > 0 else "❌"
        print(f"  {status} {c:25s} {rate:5.1f}% {bar}")
    
    out_path = OUTPUT_DIR / f"{filepath.stem}_normalized.xlsx"
    result.to_excel(out_path, index=False)
    print(f"\n  ✅ {out_path.name}")
    
    return result, total_rows_in, total_rows_out

grand_in = 0
grand_out = 0
for f in sorted(INPUT_DIR.glob("*")):
    _, ri, ro = normalize_file(f)
    grand_in += ri
    grand_out += ro

print(f"\n{'='*60}")
print(f"ИТОГО: {grand_in} → {grand_out} строк")
print(f"{'='*60}")
