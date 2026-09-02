"""
Base de datos SQLite: usuarios (con roles), productos del catálogo y
verificación por email (código pendiente).
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
            email TEXT,
            is_admin INTEGER NOT NULL DEFAULT 0,
            activa INTEGER NOT NULL DEFAULT 1
        )"""
    )
    # Migración suave por si la base ya existía sin la columna 'email'.
    try:
        conn.execute("ALTER TABLE usuarios ADD COLUMN email TEXT")
    except sqlite3.OperationalError:
        pass  # ya existía

    conn.execute(
        """CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            categoria TEXT NOT NULL DEFAULT 'General',
            precio REAL NOT NULL,
            imagen TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS pendientes_verificacion (
            telegram_id INTEGER PRIMARY KEY,
            codigo TEXT NOT NULL,
            purpose TEXT,
            username TEXT,
            email TEXT,
            mensaje_id INTEGER,
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    conn.commit()
    conn.close()


# --- Usuarios ---

def get_user(telegram_id: int):
    """Solo devuelve el usuario si su sesión está activa (no ha cerrado sesión)."""
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM usuarios WHERE telegram_id = ? AND activa = 1", (telegram_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def set_activa(telegram_id: int, activa: bool):
    conn = get_conn()
    conn.execute(
        "UPDATE usuarios SET activa = ? WHERE telegram_id = ?", (int(activa), telegram_id)
    )
    conn.commit()
    conn.close()


def get_all_users():
    """Lista de usuarios SIN el email (privacidad, ni siquiera para el admin)."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT username, is_admin, activa FROM usuarios ORDER BY username"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


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


def create_user(telegram_id: int, username: str, email: str = None, is_admin: bool = False):
    conn = get_conn()
    conn.execute(
        "INSERT INTO usuarios (telegram_id, username, email, is_admin) VALUES (?, ?, ?, ?)",
        (telegram_id, username, email, int(is_admin)),
    )
    conn.commit()
    conn.close()


def get_user_by_username(username: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM usuarios WHERE username = ?", (username,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_telegram_id(username: str, new_telegram_id: int):
    """Mueve la cuenta (con ese username) a un nuevo telegram_id y reactiva la sesión."""
    conn = get_conn()
    conn.execute(
        "UPDATE usuarios SET telegram_id = ?, activa = 1 WHERE username = ?",
        (new_telegram_id, username),
    )
    conn.commit()
    conn.close()


# --- Verificación por email ---

def set_pendiente(telegram_id: int, codigo: str, purpose: str = None, username: str = None, email: str = None):
    """Crea/reemplaza el código pendiente. Si purpose/username/email se omiten
    (ej. al regenerar el código), se conservan los que ya había."""
    conn = get_conn()
    conn.execute(
        "INSERT INTO pendientes_verificacion (telegram_id, codigo, purpose, username, email) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(telegram_id) DO UPDATE SET "
        "codigo = excluded.codigo, "
        "purpose = COALESCE(excluded.purpose, pendientes_verificacion.purpose), "
        "username = COALESCE(excluded.username, pendientes_verificacion.username), "
        "email = COALESCE(excluded.email, pendientes_verificacion.email), "
        "mensaje_id = NULL, creado_en = CURRENT_TIMESTAMP",
        (telegram_id, codigo, purpose, username, email),
    )
    conn.commit()
    conn.close()


def set_mensaje(telegram_id: int, mensaje_id: int):
    conn = get_conn()
    conn.execute(
        "UPDATE pendientes_verificacion SET mensaje_id = ? WHERE telegram_id = ?",
        (mensaje_id, telegram_id),
    )
    conn.commit()
    conn.close()


def get_pendiente(telegram_id: int):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM pendientes_verificacion WHERE telegram_id = ?", (telegram_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def borrar_pendiente(telegram_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM pendientes_verificacion WHERE telegram_id = ?", (telegram_id,))
    conn.commit()
    conn.close()


# --- Productos ---

def add_product(nombre: str, precio: float, imagen: str, categoria: str = "General") -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO productos (nombre, categoria, precio, imagen) VALUES (?, ?, ?, ?)",
        (nombre, categoria, precio, imagen),
    )
    conn.commit()
    pid = cur.lastrowid
    conn.close()
    return pid


def get_products(categoria: str = None):
    conn = get_conn()
    if categoria:
        rows = conn.execute(
            "SELECT * FROM productos WHERE categoria = ? ORDER BY id", (categoria,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM productos ORDER BY categoria, id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_categories():
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT categoria FROM productos ORDER BY categoria"
    ).fetchall()
    conn.close()
    return [r["categoria"] for r in rows]


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
