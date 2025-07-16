from sqlalchemy import create_engine
import urllib
import os

def get_engine():
    db_server = os.getenv("DB_SERVER", "vdrsapps.database.windows.net")
    db_user = os.getenv("DB_USER", "VDRSAdmin")
    db_password = os.getenv("DB_PASSWORD", "Oz01%O0wi")
    db_name = os.getenv("DB_NAME", "PowerAppsDatabase")
    params = urllib.parse.quote_plus(
        f"Driver={{ODBC Driver 17 for SQL Server}};"
        f"Server={db_server};"
        f"Database={db_name};"
        f"Uid={db_user};"
        f"Pwd={db_password};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )
    engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")
    return engine 