"""Capa de datos SQLite para PetFletes (v2.0).

Roles: usuario, repartidor, tienda y admin. Flujo de un pedido:
  Esperando tienda -> (la tienda confirma el pago del producto) -> Buscando repartidor
  -> Aceptado -> Entregado.   El repartidor cobra únicamente el envío.
"""
import hashlib
import json
import os
import random
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta

import tarifas

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mascotas.db")
FMT = "%Y-%m-%d %H:%M:%S"

# Cuentas y datos de demostración: SOLO si se arranca con PETFLETES_DEMO=1.
DEMO = os.environ.get("PETFLETES_DEMO") == "1"

# El administrador se crea en el primer arranque. Define PETFLETES_ADMIN_PASSWORD; si no,
# se genera una contraseña aleatoria que se muestra UNA sola vez en la consola/logs.
ADMIN_EMAIL = "admin@petfletes.cr"
ADMIN_PASSWORD = os.environ.get("PETFLETES_ADMIN_PASSWORD")
CLAVE_ADMIN_ANTIGUA = "admin123"  # valor por defecto de la v1: se avisa si sigue en uso

# Duración de la puja (5 minutos). Para pruebas: PETFLETES_PUJA_SEGUNDOS=30
PUJA_SEGUNDOS = int(os.environ.get("PETFLETES_PUJA_SEGUNDOS", "300"))
PASO_TARIFA = 100

E_ESPERA = "Esperando tienda"
E_BUSCANDO = "Buscando repartidor"
E_AGOTADO = "Tiempo agotado"
E_ACEPTADO = "Aceptado"
E_ENTREGADO = "Entregado"
E_CANCELADO = "Cancelado"
ESTADOS_EN_CURSO = (E_ESPERA, E_BUSCANDO, E_AGOTADO, E_ACEPTADO)
_EN_CURSO_SQL = ",".join(f"'{e}'" for e in ESTADOS_EN_CURSO)

SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    telefono TEXT,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    rol TEXT NOT NULL DEFAULT 'usuario',
    activo INTEGER NOT NULL DEFAULT 1,
    creado TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tiendas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    direccion TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    descripcion TEXT,
    activa INTEGER NOT NULL DEFAULT 1,
    sinpe TEXT,
    telefono TEXT,
    usuario_id INTEGER
);

CREATE TABLE IF NOT EXISTS productos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tienda_id INTEGER NOT NULL REFERENCES tiendas(id),
    nombre TEXT NOT NULL,
    precio INTEGER NOT NULL,
    peso_kg REAL NOT NULL,
    categoria TEXT,
    activo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS repartidores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    sinpe TEXT NOT NULL,
    vehiculo TEXT NOT NULL,
    usuario_id INTEGER
);

CREATE TABLE IF NOT EXISTS pedidos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    tienda_id INTEGER NOT NULL REFERENCES tiendas(id),
    items_json TEXT NOT NULL,
    peso_total REAL NOT NULL,
    subtotal INTEGER NOT NULL,
    distancia_km REAL NOT NULL,
    tarifa_minima INTEGER NOT NULL,
    oferta INTEGER NOT NULL,
    oferta_inicial INTEGER,
    origen_nombre TEXT,
    origen_lat REAL,
    origen_lon REAL,
    destino_nombre TEXT NOT NULL,
    destino_senas TEXT NOT NULL,
    destino_lat REAL NOT NULL,
    destino_lon REAL NOT NULL,
    estado TEXT NOT NULL DEFAULT 'Esperando tienda',
    repartidor_id INTEGER REFERENCES repartidores(id),
    creado TEXT NOT NULL,
    publicado_en TEXT,
    aceptado_en TEXT,
    entregado_en TEXT,
    pago_confirmado_en TEXT,
    listo_en TEXT,
    nota_tienda TEXT
);

CREATE TABLE IF NOT EXISTS publicaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    tipo TEXT NOT NULL,
    titulo TEXT NOT NULL,
    contenido TEXT NOT NULL,
    creado TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ofertas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id INTEGER NOT NULL REFERENCES pedidos(id),
    repartidor_id INTEGER NOT NULL REFERENCES repartidores(id),
    monto INTEGER NOT NULL,
    estado TEXT NOT NULL DEFAULT 'pendiente',
    creado TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mensajes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canal TEXT NOT NULL,
    pedido_id INTEGER,
    usuario_id INTEGER,
    autor_id INTEGER NOT NULL REFERENCES usuarios(id),
    texto TEXT NOT NULL,
    creado TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS calificaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id INTEGER NOT NULL REFERENCES pedidos(id),
    autor_rol TEXT NOT NULL,
    estrellas INTEGER NOT NULL,
    comentario TEXT,
    creado TEXT NOT NULL,
    UNIQUE (pedido_id, autor_rol)
);
"""
_TABLAS = re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", SCHEMA)

# La migración SOLO agrega columnas y tablas nuevas; nunca borra ni modifica datos existentes.
_MIGRACIONES = [
    ("usuarios", "rol", "TEXT NOT NULL DEFAULT 'usuario'"),
    ("repartidores", "usuario_id", "INTEGER"),
    ("pedidos", "origen_nombre", "TEXT"),
    ("pedidos", "origen_lat", "REAL"),
    ("pedidos", "origen_lon", "REAL"),
    ("pedidos", "oferta_inicial", "INTEGER"),
    ("pedidos", "publicado_en", "TEXT"),
    ("pedidos", "aceptado_en", "TEXT"),
    ("pedidos", "entregado_en", "TEXT"),
    ("usuarios", "activo", "INTEGER NOT NULL DEFAULT 1"),
    ("tiendas", "activa", "INTEGER NOT NULL DEFAULT 1"),
    ("productos", "categoria", "TEXT"),
    ("productos", "activo", "INTEGER NOT NULL DEFAULT 1"),
    # --- v2.0
    ("tiendas", "sinpe", "TEXT"),
    ("tiendas", "telefono", "TEXT"),
    ("tiendas", "usuario_id", "INTEGER"),
    ("pedidos", "pago_confirmado_en", "TEXT"),
    ("pedidos", "listo_en", "TEXT"),
    ("pedidos", "nota_tienda", "TEXT"),
]

TIENDAS_MOCK = [
    {
        "nombre": "PetZone Escazú", "sinpe": "8800-1001", "telefono": "2288-1001",
        "direccion": "Avenida Escazú, 200 m norte del Multiplaza, Escazú",
        "lat": 9.9181, "lon": -84.1400,
        "descripcion": "Alimento premium y accesorios para perros y gatos.",
        "productos": [
            ("Arena sanitaria para gatos 10 kg", 7500, 10.0),
            ("Alimento perro adulto 15 kg", 28900, 15.0),
            ("Alimento gato adulto 7.5 kg", 16500, 7.5),
            ("Snacks dentales para perro", 3200, 0.4),
            ("Collar antipulgas", 6900, 0.1),
        ],
    },
    {
        "nombre": "Mundo Mascota Heredia", "sinpe": "8800-1002", "telefono": "2288-1002",
        "direccion": "Frente al Parque Central, Heredia centro",
        "lat": 9.9981, "lon": -84.1165,
        "descripcion": "Todo para tu mascota, con precios accesibles.",
        "productos": [
            ("Arena aglomerante 5 kg", 4800, 5.0),
            ("Alimento cachorro 8 kg", 17900, 8.0),
            ("Rascador para gato", 12500, 2.5),
            ("Shampoo hipoalergénico", 4500, 0.5),
            ("Juguete mordedor", 2800, 0.2),
        ],
    },
    {
        "nombre": "Huellitas Curridabat", "sinpe": "8800-1003", "telefono": "2288-1003",
        "direccion": "Contiguo a Plaza del Sol, Curridabat",
        "lat": 9.9137, "lon": -84.0334,
        "descripcion": "Boutique de mascotas con productos naturales.",
        "productos": [
            ("Arena perfumada 20 kg", 13900, 20.0),
            ("Alimento premium gato 3 kg", 11200, 3.0),
            ("Cama mediana acolchada", 15000, 1.8),
            ("Pipeta antipulgas", 8400, 0.05),
            ("Comedero de acero inoxidable", 3900, 0.6),
        ],
    },
]

# Repartidores de demostración (sin cuenta): hacen ofertas simuladas (solo en modo demo).
REPARTIDORES_MOCK = [
    ("Carlos Mora", "8801-2345", "Moto"),
    ("Daniela Vargas", "6012-3456", "Carro pequeño"),
    ("Andrés Solano", "7099-4567", "Pick-up"),
    ("Derek Solís", "8555-0101", "Moto"),
    ("Ale Rojas", "8555-0202", "Bicicleta"),
]

_SELECT_PEDIDO = """
SELECT p.*, t.nombre AS tienda_nombre, t.direccion AS tienda_direccion,
       t.lat AS tienda_lat, t.lon AS tienda_lon, t.sinpe AS tienda_sinpe,
       t.telefono AS tienda_telefono, t.usuario_id AS tienda_usuario_id,
       r.nombre AS repartidor_nombre, r.sinpe AS repartidor_sinpe,
       r.vehiculo AS repartidor_vehiculo, r.usuario_id AS repartidor_usuario_id,
       u.nombre AS cliente_nombre, u.telefono AS cliente_telefono,
       (SELECT COUNT(*) FROM ofertas o WHERE o.pedido_id = p.id AND o.estado = 'pendiente') AS n_ofertas
FROM pedidos p
JOIN tiendas t ON t.id = p.tienda_id
JOIN usuarios u ON u.id = p.usuario_id
LEFT JOIN repartidores r ON r.id = p.repartidor_id
"""


@contextmanager
def conexion():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ahora():
    return datetime.now().strftime(FMT)


def _hash_password(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000
    ).hex()


# -------------------------------------------------------------- Inicio y migración
def _migracion_pendiente():
    """True si la base existente no tiene alguna tabla o columna de esta versión."""
    with conexion() as conn:
        tablas = {f["name"] for f in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if any(t not in tablas for t in _TABLAS):
            return True
        for tabla, columna, _ in _MIGRACIONES:
            if columna not in [f["name"] for f in conn.execute(f"PRAGMA table_info({tabla})")]:
                return True
    return False


def respaldar_base():
    """Copia consistente de la base (API de respaldo de SQLite) antes de migrar. Devuelve la ruta."""
    destino = f"{DB_PATH}.bak-{datetime.now():%Y%m%d-%H%M%S}"
    origen, copia = sqlite3.connect(DB_PATH), sqlite3.connect(destino)
    try:
        origen.backup(copia)
    finally:
        copia.close()
        origen.close()
    return destino


def init_db():
    """Crea tablas, migra bases anteriores (con copia previa) y crea el administrador si falta."""
    if os.path.exists(DB_PATH) and os.path.getsize(DB_PATH) > 0 and _migracion_pendiente():
        print(f"[PetFletes] Migración pendiente. Copia de seguridad creada en: {respaldar_base()}")
    with conexion() as conn:
        conn.executescript(SCHEMA)
        _migrar(conn)
        _asegurar_admin(conn)
        if DEMO:
            _sembrar_demo(conn)


def _migrar(conn):
    for tabla, columna, definicion in _MIGRACIONES:
        columnas = [f["name"] for f in conn.execute(f"PRAGMA table_info({tabla})")]
        if columna not in columnas:
            conn.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {definicion}")
    # Solo rellena valores vacíos de columnas agregadas por versiones previas.
    conn.execute("UPDATE pedidos SET publicado_en = creado WHERE publicado_en IS NULL")
    conn.execute("UPDATE pedidos SET oferta_inicial = oferta WHERE oferta_inicial IS NULL")
    for f in conn.execute("SELECT id, nombre FROM productos WHERE categoria IS NULL").fetchall():
        conn.execute("UPDATE productos SET categoria = ? WHERE id = ?", (_categorizar(f["nombre"]), f["id"]))


def _asegurar_cuenta(conn, nombre, email, telefono, password, rol, sinpe=None, vehiculo=None):
    """Crea la cuenta si no existe (y su perfil de repartidor). Devuelve el id del usuario."""
    fila = conn.execute("SELECT id FROM usuarios WHERE email = ?", (email,)).fetchone()
    if fila:
        return fila["id"]
    salt = secrets.token_hex(16)
    uid = conn.execute(
        "INSERT INTO usuarios (nombre, email, telefono, password_hash, salt, rol, creado) VALUES (?,?,?,?,?,?,?)",
        (nombre, email, telefono, _hash_password(password, salt), salt, rol, ahora()),
    ).lastrowid
    if rol == "repartidor":
        conn.execute(
            "INSERT INTO repartidores (nombre, sinpe, vehiculo, usuario_id) VALUES (?,?,?,?)",
            (nombre, sinpe, vehiculo, uid),
        )
    return uid


def _asegurar_admin(conn):
    """Primer arranque: crea el administrador solo si todavía no existe ninguno."""
    if conn.execute("SELECT 1 FROM usuarios WHERE rol = 'admin'").fetchone():
        return
    password = ADMIN_PASSWORD
    generada = not password
    if generada:
        password = secrets.token_urlsafe(9)
    _asegurar_cuenta(conn, "Administrador", ADMIN_EMAIL, "", password, "admin")
    if generada:
        print("=" * 64)
        print(f"[PetFletes] Administrador creado: {ADMIN_EMAIL}")
        print(f"[PetFletes] Contraseña inicial (se muestra solo esta vez): {password}")
        print("=" * 64)


def _sembrar_demo(conn):
    """Datos de demostración (solo con PETFLETES_DEMO=1)."""
    if conn.execute("SELECT COUNT(*) FROM tiendas").fetchone()[0] == 0:
        for t in TIENDAS_MOCK:
            tid = conn.execute(
                "INSERT INTO tiendas (nombre, direccion, lat, lon, descripcion, sinpe, telefono) VALUES (?,?,?,?,?,?,?)",
                (t["nombre"], t["direccion"], t["lat"], t["lon"], t["descripcion"], t["sinpe"], t["telefono"]),
            ).lastrowid
            conn.executemany(
                "INSERT INTO productos (tienda_id, nombre, precio, peso_kg, categoria) VALUES (?,?,?,?,?)",
                [(tid, *p, _categorizar(p[0])) for p in t["productos"]],
            )
    for n, t in enumerate(TIENDAS_MOCK, 1):  # una cuenta de tienda demo por tienda
        fila = conn.execute("SELECT id, usuario_id FROM tiendas WHERE nombre = ?", (t["nombre"],)).fetchone()
        if fila and fila["usuario_id"] is None:
            sufijo = "" if n == 1 else str(n)
            uid = _asegurar_cuenta(conn, f"Tienda Demo {t['nombre']}", f"tienda{sufijo}@petfletes.cr",
                                   t["telefono"], "demo123", "tienda")
            conn.execute("UPDATE tiendas SET usuario_id = ? WHERE id = ?", (uid, fila["id"]))
            conn.execute("UPDATE tiendas SET sinpe = ?, telefono = ? WHERE id = ? AND sinpe IS NULL",
                         (t["sinpe"], t["telefono"], fila["id"]))
    for nombre, sinpe, vehiculo in REPARTIDORES_MOCK:
        if not conn.execute("SELECT 1 FROM repartidores WHERE nombre = ?", (nombre,)).fetchone():
            conn.execute("INSERT INTO repartidores (nombre, sinpe, vehiculo) VALUES (?,?,?)",
                         (nombre, sinpe, vehiculo))

    demo_id = _asegurar_cuenta(conn, "Usuario Demo", "demo@petfletes.cr", "8888-0000", "demo123", "usuario")
    _asegurar_cuenta(conn, "Repartidor Demo", "repartidor@petfletes.cr", "8777-1111", "demo123",
                     "repartidor", sinpe="8777-1111", vehiculo="Moto")

    if conn.execute("SELECT COUNT(*) FROM publicaciones").fetchone()[0] == 0:
        ahora_dt = datetime.now()
        posts = [
            ("Oferta de tienda", "2x1 en snacks dentales en PetZone Escazú",
             "Este fin de semana llevá 2 snacks dentales por el precio de 1. ¡Hasta agotar existencias!",
             ahora_dt - timedelta(hours=26)),
            ("Tip de mascotas", "¿Cada cuánto cambiar la arena?",
             "Retirá los residuos a diario y cambiá toda la arena aglomerante cada 2 a 3 semanas.",
             ahora_dt - timedelta(hours=5)),
            ("Pregunta", "¿Recomiendan alimento para gato esterilizado?",
             "Mi gata acaba de ser esterilizada y busco un alimento con control de peso. ¡Gracias!",
             ahora_dt - timedelta(hours=1)),
        ]
        conn.executemany(
            "INSERT INTO publicaciones (usuario_id, tipo, titulo, contenido, creado) VALUES (?,?,?,?,?)",
            [(demo_id, tipo, titulo, cont, dt.strftime(FMT)) for tipo, titulo, cont, dt in posts],
        )


# ---------------------------------------------------------------- Usuarios
def _normalizar_sinpe(numero):
    digitos = "".join(c for c in (numero or "") if c.isdigit())
    if len(digitos) != 8:
        raise ValueError("El número de SINPE Móvil debe tener 8 dígitos.")
    return f"{digitos[:4]}-{digitos[4:]}"


def _tienda_id_de(conn, usuario_id):
    f = conn.execute("SELECT id FROM tiendas WHERE usuario_id = ? ORDER BY id LIMIT 1", (usuario_id,)).fetchone()
    return f["id"] if f else None


def _usuario_dict(conn, fila):
    rep = conn.execute("SELECT id FROM repartidores WHERE usuario_id = ?", (fila["id"],)).fetchone()
    return {"id": fila["id"], "nombre": fila["nombre"], "email": fila["email"],
            "telefono": fila["telefono"], "rol": fila["rol"],
            "repartidor_id": rep["id"] if rep else None,
            "tienda_id": _tienda_id_de(conn, fila["id"]) if fila["rol"] == "tienda" else None}


def crear_usuario(nombre, email, telefono, password, rol="usuario", sinpe="", vehiculo="", tienda=None):
    """Registra un usuario, repartidor o tienda. Lanza ValueError si los datos no son válidos.

    tienda: dict con nombre, direccion, lat, lon, sinpe, descripcion (solo para rol='tienda').
    La tienda queda OCULTA hasta que el administrador la apruebe (activa = 0).
    """
    nombre, email, telefono = nombre.strip(), email.strip().lower(), telefono.strip()
    if rol not in ("usuario", "repartidor", "tienda"):
        raise ValueError("Tipo de cuenta no válido.")
    if not nombre or "@" not in email:
        raise ValueError("Ingresa un nombre y un correo válido.")
    if len(password) < 6:
        raise ValueError("La contraseña debe tener al menos 6 caracteres.")
    if rol == "repartidor":
        sinpe = _normalizar_sinpe(sinpe)
        vehiculo = vehiculo.strip()
        if not vehiculo:
            raise ValueError("Indica tu tipo de vehículo.")
    if rol == "tienda":
        tienda = tienda or {}
        t_nombre, t_dir = (tienda.get("nombre") or "").strip(), (tienda.get("direccion") or "").strip()
        if not t_nombre or not t_dir:
            raise ValueError("La tienda necesita nombre y dirección.")
        t_sinpe = _normalizar_sinpe(tienda.get("sinpe"))
        t_lat, t_lon = float(tienda["lat"]), float(tienda["lon"])
        if not (-90 <= t_lat <= 90 and -180 <= t_lon <= 180):
            raise ValueError("Coordenadas no válidas.")
    salt = secrets.token_hex(16)
    try:
        with conexion() as conn:
            uid = conn.execute(
                "INSERT INTO usuarios (nombre, email, telefono, password_hash, salt, rol, creado) VALUES (?,?,?,?,?,?,?)",
                (nombre, email, telefono, _hash_password(password, salt), salt, rol, ahora()),
            ).lastrowid
            rid = tid = None
            if rol == "repartidor":
                rid = conn.execute(
                    "INSERT INTO repartidores (nombre, sinpe, vehiculo, usuario_id) VALUES (?,?,?,?)",
                    (nombre, sinpe, vehiculo, uid),
                ).lastrowid
            if rol == "tienda":
                tid = conn.execute(
                    """INSERT INTO tiendas (nombre, direccion, lat, lon, descripcion, activa, sinpe, telefono, usuario_id)
                       VALUES (?,?,?,?,?,0,?,?,?)""",
                    (t_nombre, t_dir, t_lat, t_lon, (tienda.get("descripcion") or "").strip(),
                     t_sinpe, telefono, uid),
                ).lastrowid
    except sqlite3.IntegrityError:
        raise ValueError("Ese correo ya está registrado.")
    return {"id": uid, "nombre": nombre, "email": email, "telefono": telefono,
            "rol": rol, "repartidor_id": rid, "tienda_id": tid}


def autenticar(email, password):
    """Devuelve el usuario (dict con su rol) si las credenciales son correctas; si no, None."""
    with conexion() as conn:
        fila = conn.execute("SELECT * FROM usuarios WHERE email = ?", (email.strip().lower(),)).fetchone()
        if fila is None:
            return None
        if not secrets.compare_digest(_hash_password(password, fila["salt"]), fila["password_hash"]):
            return None
        if not fila["activo"]:
            raise ValueError("Tu cuenta está suspendida. Contacta al administrador.")
        return _usuario_dict(conn, fila)


def cambiar_password(usuario_id, actual, nueva):
    """Cambia la contraseña del propio usuario (exige la actual)."""
    if len(nueva) < 6:
        raise ValueError("La contraseña nueva debe tener al menos 6 caracteres.")
    with conexion() as conn:
        f = conn.execute("SELECT salt, password_hash FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
        if f is None or not secrets.compare_digest(_hash_password(actual, f["salt"]), f["password_hash"]):
            raise ValueError("La contraseña actual no es correcta.")
        salt = secrets.token_hex(16)
        conn.execute("UPDATE usuarios SET password_hash = ?, salt = ? WHERE id = ?",
                     (_hash_password(nueva, salt), salt, usuario_id))


def admin_usa_clave_antigua():
    """True si alguna cuenta de administrador sigue con la contraseña por defecto de la v1."""
    with conexion() as conn:
        return any(secrets.compare_digest(_hash_password(CLAVE_ADMIN_ANTIGUA, f["salt"]), f["password_hash"])
                   for f in conn.execute("SELECT salt, password_hash FROM usuarios WHERE rol = 'admin'"))


# ------------------------------------------------------ Tiendas y productos
CATEGORIAS = ["Alimento", "Higiene", "Juguetes", "Accesorios", "Salud"]


def _categorizar(nombre):
    n = nombre.lower()
    for categoria, palabras in (
        ("Salud", ("antipulgas", "pipeta", "vitamina", "medic")),
        ("Higiene", ("arena", "shampoo", "higien", "jabón", "cepillo")),
        ("Alimento", ("alimento", "snack", "croqueta", "comida")),
        ("Juguetes", ("juguete", "mordedor", "rascador", "pelota")),
    ):
        if any(p in n for p in palabras):
            return categoria
    return "Accesorios"


def listar_tiendas(solo_activas=True):
    donde = "WHERE activa = 1" if solo_activas else ""
    with conexion() as conn:
        return [dict(f) for f in conn.execute(f"SELECT * FROM tiendas {donde} ORDER BY nombre")]


def obtener_tienda(tienda_id):
    with conexion() as conn:
        fila = conn.execute("SELECT * FROM tiendas WHERE id = ?", (tienda_id,)).fetchone()
    return dict(fila) if fila else None


def obtener_tienda_de_usuario(usuario_id):
    with conexion() as conn:
        fila = conn.execute("SELECT * FROM tiendas WHERE usuario_id = ? ORDER BY id LIMIT 1",
                            (usuario_id,)).fetchone()
    return dict(fila) if fila else None


def listar_productos(tienda_id, categoria=None, solo_activos=True):
    sql, params = "SELECT * FROM productos WHERE tienda_id = ?", [tienda_id]
    if solo_activos:
        sql += " AND activo = 1"
    if categoria:
        sql += " AND categoria = ?"
        params.append(categoria)
    with conexion() as conn:
        return [dict(f) for f in conn.execute(sql + " ORDER BY nombre", params)]


def buscar_productos(texto, categoria=None):
    """Búsqueda de productos (por nombre o tienda) en todas las tiendas activas."""
    like = f"%{texto.strip()}%"
    sql = """SELECT p.*, t.nombre AS tienda_nombre FROM productos p JOIN tiendas t ON t.id = p.tienda_id
             WHERE p.activo = 1 AND t.activa = 1 AND (p.nombre LIKE ? OR t.nombre LIKE ?)"""
    params = [like, like]
    if categoria:
        sql += " AND p.categoria = ?"
        params.append(categoria)
    with conexion() as conn:
        return [dict(f) for f in conn.execute(sql + " ORDER BY p.nombre", params)]


def obtener_productos(ids):
    """Devuelve {id: producto} de los productos activos con esos ids."""
    ids = list(ids)
    if not ids:
        return {}
    marcas = ",".join("?" * len(ids))
    with conexion() as conn:
        return {f["id"]: dict(f) for f in conn.execute(
            f"SELECT * FROM productos WHERE activo = 1 AND id IN ({marcas})", ids)}


def _validar_producto(nombre, precio, peso_kg, categoria):
    if not nombre.strip():
        raise ValueError("El producto necesita un nombre.")
    if int(precio) <= 0:
        raise ValueError("El precio debe ser mayor a cero.")
    if float(peso_kg) < 0:
        raise ValueError("El peso no puede ser negativo.")
    if categoria not in CATEGORIAS:
        raise ValueError("Categoría no válida.")


def crear_producto(tienda_id, nombre, precio, peso_kg, categoria):
    _validar_producto(nombre, precio, peso_kg, categoria)
    with conexion() as conn:
        return conn.execute(
            "INSERT INTO productos (tienda_id, nombre, precio, peso_kg, categoria) VALUES (?,?,?,?,?)",
            (tienda_id, nombre.strip(), int(precio), float(peso_kg), categoria)).lastrowid


def actualizar_producto(producto_id, nombre, precio, peso_kg, categoria, activo):
    _validar_producto(nombre, precio, peso_kg, categoria)
    with conexion() as conn:
        conn.execute(
            "UPDATE productos SET nombre = ?, precio = ?, peso_kg = ?, categoria = ?, activo = ? WHERE id = ?",
            (nombre.strip(), int(precio), float(peso_kg), categoria, 1 if activo else 0, producto_id))


def crear_producto_tienda(usuario_id, nombre, precio, peso_kg, categoria):
    """La tienda agrega un producto a SU catálogo (el id de tienda sale de la cuenta, no del formulario)."""
    with conexion() as conn:
        tid = _tienda_id_de(conn, usuario_id)
    if tid is None:
        raise ValueError("Tu cuenta no tiene una tienda asociada.")
    return crear_producto(tid, nombre, precio, peso_kg, categoria)


def actualizar_producto_tienda(usuario_id, producto_id, nombre, precio, peso_kg, categoria, activo):
    """La tienda edita solo productos de su propio catálogo."""
    _validar_producto(nombre, precio, peso_kg, categoria)
    with conexion() as conn:
        tid = _tienda_id_de(conn, usuario_id)
        cur = conn.execute(
            """UPDATE productos SET nombre = ?, precio = ?, peso_kg = ?, categoria = ?, activo = ?
               WHERE id = ? AND tienda_id = ?""",
            (nombre.strip(), int(precio), float(peso_kg), categoria, 1 if activo else 0, producto_id, tid))
        if cur.rowcount != 1:
            raise ValueError("Ese producto no pertenece a tu tienda.")


def crear_tienda(nombre, direccion, lat, lon, descripcion="", sinpe="", telefono=""):
    if not nombre.strip() or not direccion.strip():
        raise ValueError("La tienda necesita nombre y dirección.")
    if not (-90 <= float(lat) <= 90 and -180 <= float(lon) <= 180):
        raise ValueError("Coordenadas no válidas.")
    sinpe = _normalizar_sinpe(sinpe) if sinpe.strip() else None
    with conexion() as conn:
        return conn.execute(
            """INSERT INTO tiendas (nombre, direccion, lat, lon, descripcion, activa, sinpe, telefono)
               VALUES (?,?,?,?,?,1,?,?)""",
            (nombre.strip(), direccion.strip(), float(lat), float(lon), descripcion.strip(),
             sinpe, telefono.strip() or None)).lastrowid


def actualizar_tienda(tienda_id, nombre, direccion, descripcion, activa, sinpe=None, telefono=None):
    """Uso del administrador. sinpe/telefono = None conserva el valor actual."""
    if not nombre.strip() or not direccion.strip():
        raise ValueError("La tienda necesita nombre y dirección.")
    sinpe = _normalizar_sinpe(sinpe) if sinpe and sinpe.strip() else None
    telefono = telefono.strip() if telefono and telefono.strip() else None
    with conexion() as conn:
        conn.execute(
            """UPDATE tiendas SET nombre = ?, direccion = ?, descripcion = ?, activa = ?,
               sinpe = COALESCE(?, sinpe), telefono = COALESCE(?, telefono) WHERE id = ?""",
            (nombre.strip(), direccion.strip(), descripcion.strip(), 1 if activa else 0,
             sinpe, telefono, tienda_id))


def actualizar_mi_tienda(usuario_id, nombre, direccion, descripcion, sinpe, telefono):
    """La tienda edita sus propios datos (no puede cambiar su visibilidad: eso es del administrador)."""
    if not nombre.strip() or not direccion.strip():
        raise ValueError("La tienda necesita nombre y dirección.")
    sinpe = _normalizar_sinpe(sinpe)
    with conexion() as conn:
        cur = conn.execute(
            """UPDATE tiendas SET nombre = ?, direccion = ?, descripcion = ?, sinpe = ?, telefono = ?
               WHERE usuario_id = ?""",
            (nombre.strip(), direccion.strip(), descripcion.strip(), sinpe, telefono.strip() or None, usuario_id))
        if cur.rowcount < 1:
            raise ValueError("Tu cuenta no tiene una tienda asociada.")


def listar_tiendas_admin():
    with conexion() as conn:
        return [dict(f) for f in conn.execute(
            """SELECT t.*, (SELECT COUNT(*) FROM productos p WHERE p.tienda_id = t.id AND p.activo = 1) AS n_productos,
                      (SELECT COUNT(*) FROM pedidos o WHERE o.tienda_id = t.id) AS n_pedidos,
                      (SELECT email FROM usuarios u WHERE u.id = t.usuario_id) AS propietario
               FROM tiendas t ORDER BY t.id""")]


def set_usuario_activo(usuario_id, activo):
    """Suspende o reactiva una cuenta (no aplica a administradores)."""
    with conexion() as conn:
        cur = conn.execute("UPDATE usuarios SET activo = ? WHERE id = ? AND rol <> 'admin'",
                           (1 if activo else 0, usuario_id))
        return cur.rowcount == 1


# ----------------------------------------------------------------- Pedidos
def _expirar(conn):
    """Pasa a 'Tiempo agotado' las pujas que superaron el tiempo límite."""
    limite = (datetime.now() - timedelta(seconds=PUJA_SEGUNDOS)).strftime(FMT)
    conn.execute(
        "UPDATE pedidos SET estado = 'Tiempo agotado' WHERE estado = 'Buscando repartidor' AND publicado_en <= ?",
        (limite,),
    )


def _pedido_dict(fila):
    p = dict(fila)
    if p.get("origen_lat") is None:  # pedidos antiguos: el origen era la tienda
        p["origen_lat"], p["origen_lon"] = p["tienda_lat"], p["tienda_lon"]
    if not p.get("origen_nombre"):
        p["origen_nombre"] = p["tienda_nombre"]
    if p.get("oferta_inicial") is None:
        p["oferta_inicial"] = p["oferta"]
    restante = 0
    if p["estado"] == E_BUSCANDO and p.get("publicado_en"):
        transcurrido = (datetime.now() - datetime.strptime(p["publicado_en"], FMT)).total_seconds()
        restante = max(0, int(PUJA_SEGUNDOS - transcurrido))
    p["segundos_restantes"] = restante
    p["puja_segundos"] = PUJA_SEGUNDOS
    p["tope_envio"] = tarifas.tope_envio(p["subtotal"])
    p["items"] = json.loads(p["items_json"])
    return p


def _consultar_pedidos(where="", params=()):
    with conexion() as conn:
        _expirar(conn)
        filas = conn.execute(f"{_SELECT_PEDIDO} {where}", params).fetchall()
    return [_pedido_dict(f) for f in filas]


def crear_pedido(usuario_id, tienda_id, items, peso_total, subtotal, distancia_km, tarifa_minima,
                 oferta, origen_nombre, origen_lat, origen_lon,
                 destino_nombre, destino_senas, destino_lat, destino_lon):
    """Guarda un pedido nuevo en 'Esperando tienda' y devuelve su id.

    Reglas: el envío no puede superar el costo de los productos; el mínimo efectivo es el menor
    entre el mínimo del algoritmo y ese tope. El pedido no se publica a repartidores hasta que
    la tienda confirme el pago del producto.
    """
    subtotal, oferta = int(subtotal), int(oferta)
    if subtotal != sum(int(i["precio"]) * int(i["cantidad"]) for i in items) or subtotal <= 0:
        raise ValueError("El subtotal no coincide con los productos del carrito.")
    minimo = tarifas.minimo_efectivo(tarifa_minima, subtotal)
    if oferta > tarifas.tope_envio(subtotal):
        raise ValueError(f"El envío no puede superar el costo de los productos (₡{subtotal:,}).")
    if oferta < minimo:
        raise ValueError(f"La oferta de envío mínima es ₡{minimo:,}.")
    momento = ahora()
    with conexion() as conn:
        t = conn.execute("SELECT activa FROM tiendas WHERE id = ?", (tienda_id,)).fetchone()
        if t is None or not t["activa"]:
            raise ValueError("Esa tienda no está disponible.")
        return conn.execute(
            """INSERT INTO pedidos (usuario_id, tienda_id, items_json, peso_total, subtotal,
               distancia_km, tarifa_minima, oferta, oferta_inicial, origen_nombre, origen_lat,
               origen_lon, destino_nombre, destino_senas, destino_lat, destino_lon, estado,
               creado, publicado_en)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (usuario_id, tienda_id, json.dumps(items, ensure_ascii=False), peso_total, subtotal,
             distancia_km, minimo, oferta, oferta, origen_nombre, origen_lat, origen_lon,
             destino_nombre, destino_senas, destino_lat, destino_lon,
             E_ESPERA, momento, momento),
        ).lastrowid


def listar_pedidos_usuario(usuario_id):
    return _consultar_pedidos("WHERE p.usuario_id = ? ORDER BY p.id DESC", (usuario_id,))


def obtener_pedido(pedido_id, usuario_id):
    pedidos = _consultar_pedidos("WHERE p.id = ? AND p.usuario_id = ?", (pedido_id, usuario_id))
    return pedidos[0] if pedidos else None


def obtener_pedido_repartidor(pedido_id, repartidor_id):
    pedidos = _consultar_pedidos("WHERE p.id = ? AND p.repartidor_id = ?", (pedido_id, repartidor_id))
    return pedidos[0] if pedidos else None


def estado_pedido(pedido_id):
    pedidos = _consultar_pedidos("WHERE p.id = ?", (pedido_id,))
    return pedidos[0]["estado"] if pedidos else None


def listar_pedidos_disponibles():
    """Pedidos con puja abierta (la tienda ya confirmó el pago del producto)."""
    return _consultar_pedidos("WHERE p.estado = 'Buscando repartidor' ORDER BY p.id DESC")


def listar_entregas_repartidor(repartidor_id):
    return _consultar_pedidos("WHERE p.repartidor_id = ? ORDER BY p.id DESC", (repartidor_id,))


# ----------------------------------------------------- Pedidos: lado de la tienda
def listar_pedidos_tienda(usuario_id):
    with conexion() as conn:
        tid = _tienda_id_de(conn, usuario_id)
    if tid is None:
        return []
    return _consultar_pedidos("WHERE p.tienda_id = ? ORDER BY p.id DESC", (tid,))


def confirmar_pedido_tienda(pedido_id, usuario_id):
    """La tienda confirma que recibió el pago del producto: empieza a prepararse y se abre la puja."""
    momento = ahora()
    with conexion() as conn:
        tid = _tienda_id_de(conn, usuario_id)
        cur = conn.execute(
            """UPDATE pedidos SET estado = 'Buscando repartidor', pago_confirmado_en = ?, publicado_en = ?
               WHERE id = ? AND tienda_id = ? AND estado = 'Esperando tienda'""",
            (momento, momento, pedido_id, tid))
        return cur.rowcount == 1


def rechazar_pedido_tienda(pedido_id, usuario_id, nota=""):
    """La tienda no puede atender el pedido (o no recibió el pago): queda cancelado, con una nota."""
    with conexion() as conn:
        tid = _tienda_id_de(conn, usuario_id)
        cur = conn.execute(
            """UPDATE pedidos SET estado = 'Cancelado', nota_tienda = ?
               WHERE id = ? AND tienda_id = ? AND estado = 'Esperando tienda'""",
            (nota.strip()[:300] or None, pedido_id, tid))
        return cur.rowcount == 1


def marcar_listo_tienda(pedido_id, usuario_id):
    """La tienda avisa que el pedido ya está listo para que lo recoja el repartidor."""
    with conexion() as conn:
        tid = _tienda_id_de(conn, usuario_id)
        cur = conn.execute(
            """UPDATE pedidos SET listo_en = ? WHERE id = ? AND tienda_id = ? AND listo_en IS NULL
               AND estado IN ('Buscando repartidor', 'Tiempo agotado', 'Aceptado')""",
            (ahora(), pedido_id, tid))
        return cur.rowcount == 1


def admin_confirmar_pedido(pedido_id):
    """Solo para tiendas SIN cuenta propia (p. ej. creadas por el administrador): confirma en su nombre."""
    momento = ahora()
    with conexion() as conn:
        cur = conn.execute(
            """UPDATE pedidos SET estado = 'Buscando repartidor', pago_confirmado_en = ?, publicado_en = ?
               WHERE id = ? AND estado = 'Esperando tienda'
                 AND tienda_id IN (SELECT id FROM tiendas WHERE usuario_id IS NULL)""",
            (momento, momento, pedido_id))
        return cur.rowcount == 1


# ------------------------------------------------------- Puja y ofertas
def ajustar_tarifa(pedido_id, usuario_id, delta):
    """Nueva tarifa = tarifa actual + delta, entre el mínimo efectivo y el tope (costo de los productos)."""
    with conexion() as conn:
        _expirar(conn)
        cur = conn.execute(
            """UPDATE pedidos SET oferta = MIN(subtotal, MAX(MIN(tarifa_minima, subtotal), oferta + ?))
               WHERE id = ? AND usuario_id = ? AND estado = 'Buscando repartidor'""",
            (int(delta), pedido_id, usuario_id),
        )
        return cur.rowcount == 1


def enviar_oferta(pedido_id, repartidor_id, monto):
    """Un repartidor ofrece un monto por el envío (reemplaza su oferta anterior)."""
    monto = int(monto)
    if monto < 500:
        raise ValueError("La oferta mínima es de ₡500.")
    with conexion() as conn:
        _expirar(conn)
        _verificar_repartidor_activo(conn, repartidor_id)
        fila = conn.execute("SELECT estado, subtotal FROM pedidos WHERE id = ?", (pedido_id,)).fetchone()
        if not fila or fila["estado"] != E_BUSCANDO:
            raise ValueError("Este pedido ya no está disponible.")
        if monto > tarifas.tope_envio(fila["subtotal"]):
            raise ValueError(f"El envío no puede superar el costo de los productos (₡{fila['subtotal']:,}).")
        conn.execute(
            "UPDATE ofertas SET estado = 'retirada' WHERE pedido_id = ? AND repartidor_id = ? AND estado = 'pendiente'",
            (pedido_id, repartidor_id),
        )
        conn.execute(
            "INSERT INTO ofertas (pedido_id, repartidor_id, monto, estado, creado) VALUES (?,?,?,?,?)",
            (pedido_id, repartidor_id, monto, "pendiente", ahora()),
        )


def obtener_oferta_repartidor(pedido_id, repartidor_id):
    with conexion() as conn:
        fila = conn.execute(
            "SELECT * FROM ofertas WHERE pedido_id = ? AND repartidor_id = ? AND estado = 'pendiente'",
            (pedido_id, repartidor_id),
        ).fetchone()
    return dict(fila) if fila else None


def listar_ofertas(pedido_id):
    """Ofertas pendientes de un pedido, de la más barata a la más cara."""
    with conexion() as conn:
        filas = conn.execute(
            """SELECT o.*, r.nombre AS repartidor_nombre, r.vehiculo AS vehiculo
               FROM ofertas o JOIN repartidores r ON r.id = o.repartidor_id
               WHERE o.pedido_id = ? AND o.estado = 'pendiente' ORDER BY o.monto ASC, o.id ASC""",
            (pedido_id,),
        ).fetchall()
        ofertas = []
        for f in filas:
            o = dict(f)
            o["promedio"], o["n_cal"] = _promedio_repartidor(conn, o["repartidor_id"])
            ofertas.append(o)
    return ofertas


def elegir_oferta(pedido_id, oferta_id, usuario_id):
    """El cliente elige la oferta de un repartidor: el pedido queda 'Aceptado' con esa tarifa."""
    with conexion() as conn:
        _expirar(conn)
        o = conn.execute(
            """SELECT o.* FROM ofertas o JOIN pedidos p ON p.id = o.pedido_id
               WHERE o.id = ? AND o.pedido_id = ? AND p.usuario_id = ?
                 AND o.estado = 'pendiente' AND p.estado = 'Buscando repartidor'""",
            (oferta_id, pedido_id, usuario_id),
        ).fetchone()
        if o is None:
            return False
        conn.execute(
            "UPDATE pedidos SET estado = 'Aceptado', repartidor_id = ?, oferta = ?, aceptado_en = ? WHERE id = ?",
            (o["repartidor_id"], o["monto"], ahora(), pedido_id),
        )
        conn.execute("UPDATE ofertas SET estado = 'aceptada' WHERE id = ?", (oferta_id,))
        conn.execute(
            "UPDATE ofertas SET estado = 'rechazada' WHERE pedido_id = ? AND id <> ? AND estado = 'pendiente'",
            (pedido_id, oferta_id),
        )
        return True


def reactivar_pedido(pedido_id, usuario_id):
    """Tras el timeout: republica la orden y reinicia el ciclo de puja."""
    with conexion() as conn:
        cur = conn.execute(
            """UPDATE pedidos SET estado = 'Buscando repartidor', publicado_en = ?
               WHERE id = ? AND usuario_id = ? AND estado = 'Tiempo agotado'""",
            (ahora(), pedido_id, usuario_id),
        )
        if cur.rowcount:
            conn.execute("UPDATE ofertas SET estado = 'vencida' WHERE pedido_id = ? AND estado = 'pendiente'",
                         (pedido_id,))
        return cur.rowcount == 1


def cancelar_pedido(pedido_id, usuario_id):
    with conexion() as conn:
        cur = conn.execute(
            """UPDATE pedidos SET estado = 'Cancelado'
               WHERE id = ? AND usuario_id = ?
                 AND estado IN ('Esperando tienda', 'Buscando repartidor', 'Tiempo agotado')""",
            (pedido_id, usuario_id),
        )
        if cur.rowcount:
            conn.execute("UPDATE ofertas SET estado = 'vencida' WHERE pedido_id = ? AND estado = 'pendiente'",
                         (pedido_id,))
        return cur.rowcount == 1


def simular_ofertas(pedido_id):
    """Solo modo demo: repartidores de demostración hacen ofertas cercanas a la tarifa del cliente."""
    if not DEMO:
        return 0
    with conexion() as conn:
        _expirar(conn)
        p = conn.execute("SELECT oferta, subtotal, estado FROM pedidos WHERE id = ?", (pedido_id,)).fetchone()
        if not p or p["estado"] != E_BUSCANDO:
            return 0
        ids = [f["id"] for f in conn.execute("SELECT id FROM repartidores WHERE usuario_id IS NULL")]
        elegidos = random.sample(ids, min(3, len(ids)))
        for rid in elegidos:
            monto = min(tarifas.tope_envio(p["subtotal"]),
                        max(500, p["oferta"] + random.choice([-200, -100, 0, 100, 200, 300])))
            conn.execute(
                "UPDATE ofertas SET estado = 'retirada' WHERE pedido_id = ? AND repartidor_id = ? AND estado = 'pendiente'",
                (pedido_id, rid),
            )
            conn.execute(
                "INSERT INTO ofertas (pedido_id, repartidor_id, monto, estado, creado) VALUES (?,?,?,?,?)",
                (pedido_id, rid, monto, "pendiente", ahora()),
            )
        return len(elegidos)


def marcar_entregado_usuario(pedido_id, usuario_id):
    with conexion() as conn:
        cur = conn.execute(
            "UPDATE pedidos SET estado = 'Entregado', entregado_en = ? WHERE id = ? AND usuario_id = ? AND estado = 'Aceptado'",
            (ahora(), pedido_id, usuario_id),
        )
        return cur.rowcount == 1


def marcar_entregado_repartidor(pedido_id, repartidor_id):
    with conexion() as conn:
        cur = conn.execute(
            "UPDATE pedidos SET estado = 'Entregado', entregado_en = ? WHERE id = ? AND repartidor_id = ? AND estado = 'Aceptado'",
            (ahora(), pedido_id, repartidor_id),
        )
        return cur.rowcount == 1


def _verificar_repartidor_activo(conn, repartidor_id):
    f = conn.execute(
        """SELECT COALESCE(u.activo, 1) AS activo FROM repartidores r
           LEFT JOIN usuarios u ON u.id = r.usuario_id WHERE r.id = ?""", (repartidor_id,)).fetchone()
    if f is None or not f["activo"]:
        raise ValueError("Tu cuenta de repartidor no está activa.")


def aceptar_viaje(pedido_id, repartidor_id):
    """El repartidor acepta el viaje a la tarifa del cliente (queda asignado de inmediato)."""
    with conexion() as conn:
        _expirar(conn)
        _verificar_repartidor_activo(conn, repartidor_id)
        p = conn.execute("SELECT oferta FROM pedidos WHERE id = ? AND estado = 'Buscando repartidor'",
                         (pedido_id,)).fetchone()
        if p is None:
            return False
        conn.execute("UPDATE ofertas SET estado = 'rechazada' WHERE pedido_id = ? AND estado = 'pendiente'",
                     (pedido_id,))
        conn.execute("INSERT INTO ofertas (pedido_id, repartidor_id, monto, estado, creado) VALUES (?,?,?,?,?)",
                     (pedido_id, repartidor_id, p["oferta"], "aceptada", ahora()))
        conn.execute("UPDATE pedidos SET estado = 'Aceptado', repartidor_id = ?, aceptado_en = ? WHERE id = ?",
                     (repartidor_id, ahora(), pedido_id))
        return True


def admin_cancelar_pedido(pedido_id):
    """El administrador cancela un pedido que sigue en curso."""
    with conexion() as conn:
        cur = conn.execute(
            f"UPDATE pedidos SET estado = 'Cancelado' WHERE id = ? AND estado IN ({_EN_CURSO_SQL})", (pedido_id,))
        if cur.rowcount:
            conn.execute("UPDATE ofertas SET estado = 'vencida' WHERE pedido_id = ? AND estado = 'pendiente'",
                         (pedido_id,))
        return cur.rowcount == 1


# ----------------------------------------------------------- Calificaciones
def _promedio_repartidor(conn, repartidor_id):
    f = conn.execute(
        """SELECT AVG(c.estrellas) AS a, COUNT(*) AS n FROM calificaciones c
           JOIN pedidos p ON p.id = c.pedido_id
           WHERE c.autor_rol = 'usuario' AND p.repartidor_id = ?""", (repartidor_id,)).fetchone()
    return (round(f["a"], 1) if f["n"] else None, f["n"])


def promedio_repartidor(repartidor_id):
    with conexion() as conn:
        return _promedio_repartidor(conn, repartidor_id)


def promedio_usuario(usuario_id):
    with conexion() as conn:
        f = conn.execute(
            """SELECT AVG(c.estrellas) AS a, COUNT(*) AS n FROM calificaciones c
               JOIN pedidos p ON p.id = c.pedido_id
               WHERE c.autor_rol = 'repartidor' AND p.usuario_id = ?""", (usuario_id,)).fetchone()
    return (round(f["a"], 1) if f["n"] else None, f["n"])


def obtener_calificacion(pedido_id, autor_rol):
    with conexion() as conn:
        fila = conn.execute("SELECT * FROM calificaciones WHERE pedido_id = ? AND autor_rol = ?",
                            (pedido_id, autor_rol)).fetchone()
    return dict(fila) if fila else None


def guardar_calificacion(pedido_id, autor_rol, actor_id, estrellas, comentario=""):
    """Calificación mutua tras la entrega. actor_id: id de usuario (cliente) o de repartidor."""
    estrellas = int(estrellas)
    if not 1 <= estrellas <= 5:
        raise ValueError("La calificación debe ser de 1 a 5 estrellas.")
    if autor_rol not in ("usuario", "repartidor"):
        raise ValueError("Rol no válido.")
    campo = "usuario_id" if autor_rol == "usuario" else "repartidor_id"
    try:
        with conexion() as conn:
            p = conn.execute(f"SELECT estado FROM pedidos WHERE id = ? AND {campo} = ?",
                             (pedido_id, actor_id)).fetchone()
            if p is None:
                raise ValueError("No puedes calificar este pedido.")
            if p["estado"] != "Entregado":
                raise ValueError("Solo se califica cuando el pedido fue entregado.")
            conn.execute(
                "INSERT INTO calificaciones (pedido_id, autor_rol, estrellas, comentario, creado) VALUES (?,?,?,?,?)",
                (pedido_id, autor_rol, estrellas, comentario.strip(), ahora()),
            )
    except sqlite3.IntegrityError:
        raise ValueError("Ya enviaste tu calificación para este pedido.")


# ------------------------------------------------------------------- Chats
def _limpiar_texto(texto):
    texto = texto.strip()
    if not texto:
        raise ValueError("Escribe un mensaje.")
    return texto[:500]


def enviar_mensaje_pedido(pedido_id, autor_id, texto):
    """Chat cliente <-> repartidor, solo mientras el viaje está activo."""
    texto = _limpiar_texto(texto)
    with conexion() as conn:
        f = conn.execute(
            """SELECT p.usuario_id, p.estado, r.usuario_id AS rep_usuario
               FROM pedidos p LEFT JOIN repartidores r ON r.id = p.repartidor_id WHERE p.id = ?""",
            (pedido_id,)).fetchone()
        if f is None or autor_id not in (f["usuario_id"], f["rep_usuario"]):
            raise ValueError("No puedes escribir en este chat.")
        if f["estado"] != "Aceptado":
            raise ValueError("El chat solo está activo mientras dura el viaje.")
        conn.execute(
            "INSERT INTO mensajes (canal, pedido_id, autor_id, texto, creado) VALUES ('pedido',?,?,?,?)",
            (pedido_id, autor_id, texto, ahora()))


def listar_mensajes_pedido(pedido_id, usuario_id):
    with conexion() as conn:
        f = conn.execute(
            """SELECT p.usuario_id, r.usuario_id AS rep_usuario
               FROM pedidos p LEFT JOIN repartidores r ON r.id = p.repartidor_id WHERE p.id = ?""",
            (pedido_id,)).fetchone()
        if f is None or usuario_id not in (f["usuario_id"], f["rep_usuario"]):
            return []
        return [dict(m) for m in conn.execute(
            """SELECT m.*, u.nombre AS autor FROM mensajes m JOIN usuarios u ON u.id = m.autor_id
               WHERE m.canal = 'pedido' AND m.pedido_id = ? ORDER BY m.id""", (pedido_id,))]


def enviar_mensaje_soporte(hilo_usuario_id, autor_id, texto):
    """Chat de soporte: el hilo pertenece a un usuario/repartidor/tienda y lo responde el administrador."""
    texto = _limpiar_texto(texto)
    with conexion() as conn:
        autor = conn.execute("SELECT rol FROM usuarios WHERE id = ?", (autor_id,)).fetchone()
        hilo = conn.execute("SELECT rol FROM usuarios WHERE id = ?", (hilo_usuario_id,)).fetchone()
        if autor is None or hilo is None or hilo["rol"] == "admin":
            raise ValueError("Conversación no válida.")
        if autor_id != hilo_usuario_id and autor["rol"] != "admin":
            raise ValueError("No puedes escribir en este chat.")
        conn.execute(
            "INSERT INTO mensajes (canal, usuario_id, autor_id, texto, creado) VALUES ('soporte',?,?,?,?)",
            (hilo_usuario_id, autor_id, texto, ahora()))


def listar_mensajes_soporte(hilo_usuario_id, solicitante_id):
    with conexion() as conn:
        s = conn.execute("SELECT rol FROM usuarios WHERE id = ?", (solicitante_id,)).fetchone()
        if s is None or (solicitante_id != hilo_usuario_id and s["rol"] != "admin"):
            return []
        return [dict(m) for m in conn.execute(
            """SELECT m.*, u.nombre AS autor FROM mensajes m JOIN usuarios u ON u.id = m.autor_id
               WHERE m.canal = 'soporte' AND m.usuario_id = ? ORDER BY m.id""", (hilo_usuario_id,))]


def listar_hilos_soporte():
    """Conversaciones de soporte; 'pendiente' = el último mensaje lo escribió el usuario."""
    with conexion() as conn:
        filas = conn.execute(
            """SELECT u.id, u.nombre, u.rol, COUNT(m.id) AS total, MAX(m.id) AS ultimo_id
               FROM mensajes m JOIN usuarios u ON u.id = m.usuario_id
               WHERE m.canal = 'soporte' GROUP BY u.id""").fetchall()
        hilos = []
        for f in filas:
            ult = conn.execute("SELECT autor_id, texto, creado FROM mensajes WHERE id = ?",
                               (f["ultimo_id"],)).fetchone()
            hilos.append({"id": f["id"], "nombre": f["nombre"], "rol": f["rol"], "total": f["total"],
                          "ultimo_texto": ult["texto"], "ultimo_creado": ult["creado"],
                          "pendiente": ult["autor_id"] == f["id"]})
    return sorted(hilos, key=lambda h: h["id"])


# --------------------------------------------------------- Centro de control
def estadisticas_admin():
    with conexion() as conn:
        _expirar(conn)

        def contar(sql):
            return conn.execute(sql).fetchone()[0]
        return {
            "esperando": contar("SELECT COUNT(*) FROM pedidos WHERE estado = 'Esperando tienda'"),
            "buscando": contar("SELECT COUNT(*) FROM pedidos WHERE estado = 'Buscando repartidor'"),
            "agotados": contar("SELECT COUNT(*) FROM pedidos WHERE estado = 'Tiempo agotado'"),
            "aceptados": contar("SELECT COUNT(*) FROM pedidos WHERE estado = 'Aceptado'"),
            "entregados": contar("SELECT COUNT(*) FROM pedidos WHERE estado = 'Entregado'"),
            "usuarios": contar("SELECT COUNT(*) FROM usuarios WHERE rol = 'usuario'"),
            "repartidores": contar("SELECT COUNT(*) FROM repartidores"),
        }


def listar_pedidos_admin(solo_en_curso=True):
    where = f"WHERE p.estado IN ({_EN_CURSO_SQL}) " if solo_en_curso else ""
    return _consultar_pedidos(where + "ORDER BY p.id DESC")


def listar_repartidores_admin():
    with conexion() as conn:
        return [dict(f) for f in conn.execute(
            """SELECT r.id, r.nombre, u.email, u.telefono, r.sinpe, r.vehiculo,
                      r.usuario_id, COALESCE(u.activo, 1) AS activo,
                      CASE WHEN r.usuario_id IS NULL THEN 'Demo' ELSE 'Registrado' END AS tipo,
                      u.creado AS registrado,
                      (SELECT COUNT(*) FROM pedidos p WHERE p.repartidor_id = r.id AND p.estado = 'Aceptado') AS en_curso,
                      (SELECT COUNT(*) FROM pedidos p WHERE p.repartidor_id = r.id AND p.estado = 'Entregado') AS entregas,
                      (SELECT ROUND(AVG(c.estrellas), 1) FROM calificaciones c JOIN pedidos p ON p.id = c.pedido_id
                        WHERE c.autor_rol = 'usuario' AND p.repartidor_id = r.id) AS calificacion,
                      (SELECT COUNT(*) FROM calificaciones c JOIN pedidos p ON p.id = c.pedido_id
                        WHERE c.autor_rol = 'usuario' AND p.repartidor_id = r.id) AS n_cal
               FROM repartidores r LEFT JOIN usuarios u ON u.id = r.usuario_id
               ORDER BY r.id DESC""")]


def listar_usuarios_admin():
    with conexion() as conn:
        return [dict(f) for f in conn.execute(
            """SELECT u.id, u.nombre, u.email, u.telefono, u.creado AS registrado, u.activo,
                      (SELECT COUNT(*) FROM pedidos p WHERE p.usuario_id = u.id) AS pedidos,
                      (SELECT ROUND(AVG(c.estrellas), 1) FROM calificaciones c JOIN pedidos p ON p.id = c.pedido_id
                        WHERE c.autor_rol = 'repartidor' AND p.usuario_id = u.id) AS calificacion,
                      (SELECT COUNT(*) FROM calificaciones c JOIN pedidos p ON p.id = c.pedido_id
                        WHERE c.autor_rol = 'repartidor' AND p.usuario_id = u.id) AS n_cal
               FROM usuarios u WHERE u.rol = 'usuario' ORDER BY u.id DESC""")]


# --------------------------------------------------------------- Comunidad
def crear_publicacion(usuario_id, tipo, titulo, contenido):
    with conexion() as conn:
        conn.execute(
            "INSERT INTO publicaciones (usuario_id, tipo, titulo, contenido, creado) VALUES (?,?,?,?,?)",
            (usuario_id, tipo, titulo.strip(), contenido.strip(), ahora()),
        )


def listar_publicaciones(tipo=None):
    """Publicaciones ordenadas de la más reciente a la más antigua."""
    consulta = """SELECT p.*, u.nombre AS autor FROM publicaciones p
                  JOIN usuarios u ON u.id = p.usuario_id"""
    params = ()
    if tipo:
        consulta += " WHERE p.tipo = ?"
        params = (tipo,)
    consulta += " ORDER BY p.creado DESC, p.id DESC"
    with conexion() as conn:
        return [dict(f) for f in conn.execute(consulta, params)]


# ------------------------------------------------- Prueba social (pantalla de inicio)
def _primer_nombre(nombre):
    return (nombre.split() or [""])[0]


def actividad_comunidad(limite=12):
    """Últimas publicaciones y reseñas reales (con comentario), de la más reciente a la más antigua."""
    with conexion() as conn:
        pubs = conn.execute(
            """SELECT p.tipo, p.titulo, p.contenido, p.creado, u.nombre AS autor
               FROM publicaciones p JOIN usuarios u ON u.id = p.usuario_id
               ORDER BY p.creado DESC, p.id DESC LIMIT ?""", (limite,)).fetchall()
        revs = conn.execute(
            """SELECT c.estrellas, c.comentario, c.creado, u.nombre AS autor
               FROM calificaciones c JOIN pedidos p ON p.id = c.pedido_id JOIN usuarios u ON u.id = p.usuario_id
               WHERE c.autor_rol = 'usuario' AND TRIM(COALESCE(c.comentario, '')) <> ''
               ORDER BY c.creado DESC LIMIT ?""", (limite,)).fetchall()
    items = [{"clase": "publicacion", "tipo": f["tipo"], "titulo": f["titulo"], "texto": f["contenido"],
              "creado": f["creado"], "autor": _primer_nombre(f["autor"])} for f in pubs]
    items += [{"clase": "resena", "estrellas": f["estrellas"], "texto": f["comentario"],
               "creado": f["creado"], "autor": _primer_nombre(f["autor"])} for f in revs]
    items.sort(key=lambda i: i["creado"], reverse=True)
    return items[:limite]


def estadisticas_publicas():
    with conexion() as conn:
        entregados = conn.execute("SELECT COUNT(*) FROM pedidos WHERE estado = 'Entregado'").fetchone()[0]
        repartidores = conn.execute("SELECT COUNT(*) FROM repartidores").fetchone()[0]
        f = conn.execute("SELECT AVG(estrellas) AS a, COUNT(*) AS n FROM calificaciones WHERE autor_rol = 'usuario'").fetchone()
    return {"entregados": entregados, "repartidores": repartidores,
            "promedio": round(f["a"], 1) if f["n"] else None, "n_cal": f["n"]}


if __name__ == "__main__":
    init_db()
    print(f"Base de datos lista en: {DB_PATH}")
