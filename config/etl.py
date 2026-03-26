# config/etl.py

"""
Konfiguracja dla procesów ETL.

Ten plik zawiera parametry stałe używane
przez skrypty importujące dane (CSV, API itd.).
"""

from pathlib import Path

# Katalog bazowy projektu (zakładamy uruchomienie z root)
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# ===== IMPORT COMPANIES =====

# Katalog z plikami do importu spółek
COMPANIES_IMPORT_DIR = PROJECT_ROOT / "import" / "prd"

# Nazwa pliku CSV ze spółkami
COMPANIES_FILENAME = "nazwy.csv"

# Pełna ścieżka do pliku
COMPANIES_CSV_PATH = COMPANIES_IMPORT_DIR / COMPANIES_FILENAME

# ===== IMPORT PRICES DAILY =====

PRICES_DAILY_IMPORT_DIR = PROJECT_ROOT / "import" / "prd" / "daily"
PRICES_DAILY_ARCHIVE_DIR = PRICES_DAILY_IMPORT_DIR / "imported"

# katalog na logi importu notowań
PRICES_DAILY_LOG_DIR = PRICES_DAILY_IMPORT_DIR / "logs"

# ==== IMPORT INDICATORS DAILY ====

INDICATORS_IMPORT_DIR = PROJECT_ROOT / "import" / "prd" / "indicators"
INDICATORS_ARCHIVE_DIR = INDICATORS_IMPORT_DIR / "imported"

# katalog na logi importu wskaźników
INDICATORS_LOG_DIR = INDICATORS_IMPORT_DIR / "logs"

