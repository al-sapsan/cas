"""AI-форматы для CAS"""

import pandas as pd

def save_ai_formats(matched, unmatched, output_dir):
    # TSV
    matched.to_csv(output_dir / "matched.tsv", sep="\t", index=False, encoding="utf-8")
    print("✅ matched.tsv")
    
    # TXT (выровненная таблица)
    with open(output_dir / "matched.txt", "w") as f:
        f.write(matched.to_string(index=False))
    print("✅ matched.txt")
    
    # JSON
    matched.to_json(output_dir / "matched.json", orient="records", force_ascii=False, indent=2, date_format="iso")
    print("✅ matched.json")
    
    # Markdown
    with open(output_dir / "matched.md", "w") as f:
        f.write("# Сопоставленные записи\n\n")
        f.write(matched.head(100).to_markdown(index=False))
    print("✅ matched.md")
    
    if len(unmatched) > 0:
        unmatched.to_csv(output_dir / "unmatched.tsv", sep="\t", index=False, encoding="utf-8")
        unmatched.to_json(output_dir / "unmatched.json", orient="records", force_ascii=False, indent=2, date_format="iso")
        print("✅ unmatched.tsv + unmatched.json")
