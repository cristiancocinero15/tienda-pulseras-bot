"""
Base de datos SQLite: usuarios (con roles) y productos del catálogo.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "tienda.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute(
        """CREATE TABLE IF NOT EXISTS usuarios (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            precio REAL NOT NULL,
            imagen TEXT NOT NULL
        )"""
    )
    conn.commit()
    conn.close()


# --- Usuarios ---

def get_user(telegram_id: int):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM usuarios WHERE telegram_id = ?", (telegram_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def username_exists(username: str) -> bool:
    conn = get_conn()
    row = conn.execute(
        "SELECT 1 FROM usuarios WHERE username = ?", (username,)
    ).fetchone()
    conn.close()
    return row is not None


def sugerir_username_libre(username: str) -> str:
    """Si el nombre está cogido, prueba username1, username2... hasta encontrar libre."""
    i = 1
    candidato = f"{username}{i}"
    while username_exists(candidato):
        i += 1
        candidato = f"{username}{i}"
    return candidato


def create_user(telegram_id: int, username: str, is_admin: bool = False):
    conn = get_conn()
    conn.execute(
        "INSERT INTO usuarios (telegram_id, username, is_admin) VALUES (?, ?, ?)",
        (telegram_id, username, int(is_admin)),
    )
    conn.commit()
    conn.close()


# --- Productos ---

def add_product(nombre: str, precio: float, imagen: str) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO productos (nombre, precio, imagen) VALUES (?, ?, ?)",
        (nombre, precio, imagen),
    )
    conn.commit()
    pid = cur.lastrowid
    conn.close()
    return pid


def get_products():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM productos ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_product(pid: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM productos WHERE id = ?", (pid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def contar_productos() -> int:
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) AS n FROM productos").fetchone()["n"]
    conn.close()
    return n
