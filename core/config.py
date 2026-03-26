# core/config.py

import os
from dotenv import load_dotenv


# Wczytanie .env (z root projektu)
load_dotenv()


class ConfigError(Exception):
    """Błąd konfiguracji aplikacji."""
    pass


def _get_env_var(name: str) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        raise ConfigError(f"Brak wymaganej zmiennej środowiskowej: {name}")
    return value


# --- Konfiguracja bazy danych ---

DB_SERVER = _get_env_var("DB_SERVER")
DB_NAME = _get_env_var("DB_NAME")
DB_USER = _get_env_var("DB_USER")
DB_PASSWORD = _get_env_var("DB_PASSWORD")

# Opcjonalne (z sensownymi domyślnymi)
DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")
DB_TRUST_CERT = os.getenv("DB_TRUST_CERT", "yes")

