import glob, hashlib, io, os, secrets, sqlite3, sys, tempfile, contextlib, importlib
import db, tarifas

def nuevo(nombre, demo=False):
    d = tempfile.mkdtemp()
    db.DB_PATH = os.path.join(d, nombre)
    db.DEMO = demo
    return db.DB_PATH

def esperar_error(fn, *a, **k):
    try: fn(*a, **k)
    except ValueError as e: return str(e)
    raise AssertionError("no lanzó ValueError")

# ---- tarifas
assert tarifas.calcular_tarifa_minima(6, 12) == 4150
assert tarifas.minimo_efectivo(4150, 2800) == 2800 and tarifas.minimo_efectivo(2000, 9000) == 2000

# ---- 1. migración de una base v1 (sin columnas nuevas) con respaldo y sin perder datos
ruta = nuevo("v1.db")
c = sqlite3.connect(ruta)
c.executescript("""
CREATE TABLE usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL, email TEXT NOT NULL UNIQUE, telefono TEXT, password_hash TEXT NOT NULL, salt TEXT NOT NULL, rol TEXT NOT NULL DEFAULT 'usuario', activo INTEGER NOT NULL DEFAULT 1, creado TEXT NOT NULL);
CREATE TABLE tiendas (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL, direccion TEXT NOT NULL, lat REAL NOT NULL, lon REAL NOT NULL, descripcion TEXT, activa INTEGER NOT NULL DEFAULT 1);
CREATE TABLE productos (id INTEGER PRIMARY KEY AUTOINCREMENT, tienda_id INTEGER NOT NULL, nombre TEXT NOT NULL, precio INTEGER NOT NULL, peso_kg REAL NOT NULL, categoria TEXT, activo INTEGER NOT NULL DEFAULT 1);
CREATE TABLE repartidores (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL, sinpe TEXT NOT NULL, vehiculo TEXT NOT NULL, usuario_id INTEGER);
CREATE TABLE pedidos (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER NOT NULL, tienda_id INTEGER NOT NULL, items_json TEXT NOT NULL, peso_total REAL NOT NULL, subtotal INTEGER NOT NULL, distancia_km REAL NOT NULL, tarifa_minima INTEGER NOT NULL, oferta INTEGER NOT NULL, oferta_inicial INTEGER, origen_nombre TEXT, origen_lat REAL, origen_lon REAL, destino_nombre TEXT NOT NULL, destino_senas TEXT NOT NULL, destino_lat REAL NOT NULL, destino_lon REAL NOT NULL, estado TEXT NOT NULL DEFAULT 'Buscando repartidor', repartidor_id INTEGER, creado TEXT NOT NULL, publicado_en TEXT, aceptado_en TEXT, entregado_en TEXT);
""")
salt = "abc"
h = hashlib.pbkdf2_hmac("sha256", b"admin123", salt.encode(), 100_000).hex()
c.execute("INSERT INTO usuarios (nombre,email,telefono,password_hash,salt,rol,creado) VALUES ('Administrador','admin@petfletes.cr','',?,?,'admin','2026-01-01 00:00:00')", (h, salt))
c.execute("INSERT INTO usuarios (nombre,email,telefono,password_hash,salt,rol,creado) VALUES ('Cli','cli@x.cr','1',?,?,'usuario','2026-01-01 00:00:00')", (h, salt))
c.execute("INSERT INTO tiendas (nombre,direccion,lat,lon) VALUES ('Vieja','dir',9.9,-84.1)")
c.execute("INSERT INTO pedidos (usuario_id,tienda_id,items_json,peso_total,subtotal,distancia_km,tarifa_minima,oferta,destino_nombre,destino_senas,destino_lat,destino_lon,creado) VALUES (2,1,'[]',1,5000,3,2000,2500,'d','s',9.9,-84.0,datetime('now','localtime'))")
c.commit(); c.close()
antes = os.path.getsize(ruta)
with contextlib.redirect_stdout(io.StringIO()) as out:
    db.init_db()
baks = glob.glob(ruta + ".bak-*")
assert len(baks) == 1 and os.path.getsize(baks[0]) == antes, "respaldo faltante o distinto"
c = sqlite3.connect(ruta)
assert c.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == 2, "no debe crear cuentas demo ni otro admin"
assert c.execute("SELECT estado, oferta FROM pedidos").fetchone() == ("Buscando repartidor", 2500)
assert "sinpe" in [r[1] for r in c.execute("PRAGMA table_info(tiendas)")]
c.close()
assert db.admin_usa_clave_antigua() is True
db.init_db()  # segunda vez: no hay migración pendiente -> no más respaldos
assert len(glob.glob(ruta + ".bak-*")) == 1
# el pedido legado sigue visible para repartidores (flujo anterior intacto)
assert [p["id"] for p in db.listar_pedidos_disponibles()] == [1]
# cambiar contraseña
assert "actual" in esperar_error(db.cambiar_password, 1, "mala", "nueva123")
db.cambiar_password(1, "admin123", "nueva123")
assert db.admin_usa_clave_antigua() is False and db.autenticar("admin@petfletes.cr", "nueva123")
print("1 OK migración")

# ---- 2. base nueva sin demo: admin aleatorio impreso, sin datos de prueba
nuevo("nueva.db")
with contextlib.redirect_stdout(io.StringIO()) as out:
    db.init_db()
assert "Contraseña inicial" in out.getvalue()
pw = out.getvalue().split("solo esta vez): ")[1].split()[0]
assert db.autenticar("admin@petfletes.cr", pw)["rol"] == "admin"
assert db.autenticar("demo@petfletes.cr", "demo123") is None
assert db.listar_tiendas() == [] and db.estadisticas_admin()["usuarios"] == 0
assert db.simular_ofertas(1) == 0
db.init_db(); assert not glob.glob(db.DB_PATH + ".bak-*")
print("2 OK primer arranque")

# ---- 3. modo demo: flujo completo
nuevo("demo.db", demo=True)
db.ADMIN_PASSWORD = "AdminTest1"
with contextlib.redirect_stdout(io.StringIO()):
    db.init_db()
assert db.autenticar("admin@petfletes.cr", "AdminTest1")["rol"] == "admin"
tu = db.autenticar("tienda@petfletes.cr", "demo123")
assert tu["rol"] == "tienda" and tu["tienda_id"] == 1
cli = db.autenticar("demo@petfletes.cr", "demo123"); rep = db.autenticar("repartidor@petfletes.cr", "demo123")
items = [{"producto_id": 1, "nombre": "Arena", "cantidad": 1, "precio": 3000, "peso_kg": 1.0}]
args = dict(items=items, peso_total=1.0, subtotal=3000, distancia_km=8.0, tarifa_minima=3900,
            origen_nombre="T", origen_lat=9.9, origen_lon=-84.1, destino_nombre="D", destino_senas="s",
            destino_lat=9.95, destino_lon=-84.05)
# tope: envío <= productos; mínimo efectivo = min(3900, 3000) = 3000
assert "superar" in esperar_error(db.crear_pedido, cli["id"], 1, oferta=3100, **args)
assert "mínima" in esperar_error(db.crear_pedido, cli["id"], 1, oferta=2900, **args)
assert "subtotal" in esperar_error(db.crear_pedido, cli["id"], 1, **{**args, "subtotal": 100}, oferta=3000)
pid = db.crear_pedido(cli["id"], 1, oferta=3000, **args)
p = db.obtener_pedido(pid, cli["id"])
assert p["estado"] == "Esperando tienda" and p["tarifa_minima"] == 3000 and p["tienda_sinpe"] == "8800-1001"
assert db.listar_pedidos_disponibles() == [], "no debe publicarse antes de la confirmación de la tienda"
assert esperar_error(db.enviar_oferta, pid, rep["repartidor_id"], 1000)
assert db.aceptar_viaje(pid, rep["repartidor_id"]) is False
# otra tienda no puede confirmar
tu2 = db.autenticar("tienda2@petfletes.cr", "demo123")
assert db.confirmar_pedido_tienda(pid, tu2["id"]) is False
assert db.admin_confirmar_pedido(pid) is False  # la tienda tiene cuenta propia
assert db.confirmar_pedido_tienda(pid, tu["id"]) is True
assert db.confirmar_pedido_tienda(pid, tu["id"]) is False
p = db.obtener_pedido(pid, cli["id"])
assert p["estado"] == "Buscando repartidor" and p["pago_confirmado_en"] and p["segundos_restantes"] > 290
assert [x["id"] for x in db.listar_pedidos_disponibles()] == [pid]
# repartidor: contraoferta por encima del tope rechazada
assert "superar" in esperar_error(db.enviar_oferta, pid, rep["repartidor_id"], 3500)
db.enviar_oferta(pid, rep["repartidor_id"], 2500)
# ajustes del cliente respetan tope y mínimo
db.ajustar_tarifa(pid, cli["id"], 100); assert db.obtener_pedido(pid, cli["id"])["oferta"] == 3000
db.ajustar_tarifa(pid, cli["id"], -100); assert db.obtener_pedido(pid, cli["id"])["oferta"] == 3000
assert db.marcar_listo_tienda(pid, tu["id"]) is True and db.marcar_listo_tienda(pid, tu["id"]) is False
assert db.simular_ofertas(pid) == 3
assert all(o["monto"] <= 3000 for o in db.listar_ofertas(pid))
assert db.aceptar_viaje(pid, rep["repartidor_id"]) is True
p = db.obtener_pedido(pid, cli["id"]); assert p["estado"] == "Aceptado" and p["oferta"] == 3000
assert db.marcar_entregado_repartidor(pid, rep["repartidor_id"])
assert db.obtener_pedido(pid, cli["id"])["estado"] == "Entregado"

# pedido con más margen: ajustes de ₡100 dentro del rango [min, subtotal]
items2 = [{"producto_id": 2, "nombre": "Alimento", "cantidad": 1, "precio": 28900, "peso_kg": 15}]
a2 = {**args, "items": items2, "subtotal": 28900, "tarifa_minima": 3900}
pid2 = db.crear_pedido(cli["id"], 1, oferta=3900, **a2)
db.confirmar_pedido_tienda(pid2, tu["id"])
db.ajustar_tarifa(pid2, cli["id"], 100); assert db.obtener_pedido(pid2, cli["id"])["oferta"] == 4000
db.ajustar_tarifa(pid2, cli["id"], -1000); assert db.obtener_pedido(pid2, cli["id"])["oferta"] == 3900
db.ajustar_tarifa(pid2, cli["id"], 99999); assert db.obtener_pedido(pid2, cli["id"])["oferta"] == 28900
# rechazo de la tienda con nota
pid3 = db.crear_pedido(cli["id"], 1, oferta=3900, **a2)
assert db.rechazar_pedido_tienda(pid3, tu["id"], "Sin pago recibido")
p3 = db.obtener_pedido(pid3, cli["id"]); assert p3["estado"] == "Cancelado" and p3["nota_tienda"] == "Sin pago recibido"
# cancelación del cliente en espera, y del admin
pid4 = db.crear_pedido(cli["id"], 1, oferta=3900, **a2); assert db.cancelar_pedido(pid4, cli["id"])
pid5 = db.crear_pedido(cli["id"], 1, oferta=3900, **a2); assert db.admin_cancelar_pedido(pid5)
pid6 = db.crear_pedido(cli["id"], 1, oferta=3900, **a2)
assert {p["id"] for p in db.listar_pedidos_admin()} == {pid2, pid6}
assert db.estadisticas_admin()["esperando"] == 1 and len(db.listar_pedidos_tienda(tu["id"])) == 6
assert db.listar_pedidos_tienda(tu2["id"]) == []
# tienda sin cuenta: confirma el admin
tid_n = db.crear_tienda("Sin dueño", "dir", 9.9, -84.0, "", "8888-2222", "2222-0000")
pid7 = db.crear_pedido(cli["id"], tid_n, oferta=3900, **a2)
assert db.admin_confirmar_pedido(pid7) is True
# catálogo de la tienda: aislamiento
pr = db.listar_productos(1, solo_activos=False)[0]
db.actualizar_producto_tienda(tu["id"], pr["id"], "Nuevo nombre", 1000, 1.0, "Alimento", True)
assert "no pertenece" in esperar_error(db.actualizar_producto_tienda, tu2["id"], pr["id"], "x", 1000, 1.0, "Alimento", True)
db.crear_producto_tienda(tu["id"], "Otro", 500, 0.5, "Juguetes")
db.actualizar_mi_tienda(tu["id"], "PetZone", "Nueva dir", "desc", "8800-9999", "2288-0000")
assert db.obtener_tienda_de_usuario(tu["id"])["sinpe"] == "8800-9999"
# registro de tienda: queda oculta hasta aprobación
nt = db.crear_usuario("Dueña", "dueña@x.cr", "7000-1111", "secreto1", rol="tienda",
    tienda={"nombre": "Pet Nueva", "direccion": "Av 1", "lat": 9.93, "lon": -84.09, "sinpe": "70001111", "descripcion": ""})
assert nt["tienda_id"] and db.obtener_tienda(nt["tienda_id"])["activa"] == 0
assert "Pet Nueva" not in [t["nombre"] for t in db.listar_tiendas()]
assert esperar_error(db.crear_pedido, cli["id"], nt["tienda_id"], oferta=3900, **a2) == "Esa tienda no está disponible."
assert "SINPE" in esperar_error(db.crear_usuario, "X", "x@y.cr", "1", "secreto1", rol="tienda",
    tienda={"nombre": "a", "direccion": "b", "lat": 1, "lon": 1, "sinpe": "12"})
db.actualizar_tienda(nt["tienda_id"], "Pet Nueva", "Av 1", "", True)
assert "Pet Nueva" in [t["nombre"] for t in db.listar_tiendas()]
assert db.autenticar("dueña@x.cr", "secreto1")["tienda_id"] == nt["tienda_id"]
print("3 OK flujo demo")
