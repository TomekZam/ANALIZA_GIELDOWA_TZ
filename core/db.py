# core/db.py

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from core.config import (
    DB_SERVER,
    DB_NAME,
    DB_USER,
    DB_PASSWORD,
    DB_DRIVER,
    DB_TRUST_CERT,
)


def _build_connection_string() -> str:
    return (
        f"mssql+pyodbc://{DB_USER}:{DB_PASSWORD}"
        f"@{DB_SERVER}/{DB_NAME}"
        f"?driver={DB_DRIVER.replace(' ', '+')}"
        f"&TrustServerCertificate={DB_TRUST_CERT}"
    )


def get_engine(echo: bool = False) -> Engine:
    """
    Zwraca silnik SQLAlchemy do bazy AnGG.
    """
    connection_string = _build_connection_string()
    engine = create_engine(connection_string, echo=echo, future=True)
    return engine


def test_connection() -> None:
    """
    Test połączenia z bazą danych.
    Zasada: test ZAWSZE próbuje realnego połączenia (bez blokady cache).
    """
    engine = get_engine()
    engine.dispose()  # wymusza nowe połączenie (bez użycia starego connection poola)

    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
        if result != 1:
            raise RuntimeError("Test połączenia z bazą nie powiódł się.")



def update_db_connection_status() -> None:
    """
    Aktualizuje parametr DB_CONNECTION_AVAILABLE oraz APP_TEST_ON_CSV_FILES
    na podstawie testu połączenia z bazą danych.
    """
    from config.app_params import set_param
    try:
        test_connection()
        set_param("DB_CONNECTION_AVAILABLE", True)
        set_param("APP_TEST_ON_CSV_FILES", False)
    except Exception:
        set_param("DB_CONNECTION_AVAILABLE", False)
        set_param("APP_TEST_ON_CSV_FILES", True)

