import os
import oracledb
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    try:
        return oracledb.connect(
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            dsn=os.getenv("DB_DSN"),
        )
    except Exception as e:
        print(f"Error de conexión a Oracle: {e}")
        return None


@contextmanager
def conexion():
    conn = get_connection()
    if conn is None:
        raise RuntimeError("Sin conexión a la base de datos")
    try:
        yield conn
    finally:
        conn.close()


def consultar(sql, params=None):
    """Ejecuta un SELECT y devuelve una lista de diccionarios (columnas en minúsculas)."""
    with conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params or {})
        columnas = [c[0].lower() for c in cursor.description]
        return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]


def ejecutar(sql, params=None):
    """Ejecuta un INSERT, UPDATE o DELETE con commit. Devuelve las filas afectadas."""
    with conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params or {})
        conn.commit()
        return cursor.rowcount
