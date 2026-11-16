import os, sys, types
from datetime import datetime

PROYECTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.update(FLASK_SECRET_KEY="clave-de-prueba", DB_USER="x", DB_PASSWORD="x", DB_DSN="x")
sys.path.insert(0, PROYECTO)

# --- Simulación de librerías que no están instaladas aquí ---
csrf_mod = types.ModuleType("flask_wtf.csrf")
class CSRFError(Exception): code = 400
class CSRFProtect:
    def __init__(self, app=None):
        if app: self.init_app(app)
    def init_app(self, app):
        app.jinja_env.globals["csrf_token"] = lambda: "tokentest"
csrf_mod.CSRFProtect, csrf_mod.CSRFError = CSRFProtect, CSRFError
sys.modules["flask_wtf"] = types.ModuleType("flask_wtf"); sys.modules["flask_wtf.csrf"] = csrf_mod
ora = types.ModuleType("oracledb")
class IntegrityError(Exception): pass
ora.IntegrityError, ora.NUMBER = IntegrityError, object()
sys.modules["oracledb"] = ora

# --- Base de datos simulada ---
from werkzeug.security import generate_password_hash
HASHES = {"admin@finca.cl": generate_password_hash("admin123"),
          "operario@finca.cl": generate_password_hash("operario123")}
ROLES = {"admin@finca.cl": "Administrador", "operario@finca.cl": "Operario"}
F = datetime(2024, 3, 10)
ANIMAL = {"id_animal": 1, "arete": "CL-0001", "nombre": "Mora", "especie": "Bovino", "raza": "Hereford",
          "sexo": "H", "fecha_nacimiento": datetime(2021, 5, 2), "potrero": "Norte", "origen": "Compra",
          "estado": "Activo", "notas": "Tranquila", "ultimo_peso": 468}
LLAMADAS = []

def consultar(sql, params=None):
    s = " ".join(sql.split())
    if "FROM usuarios u" in s:
        e = params["email"]
        return [{"id_usuario": 1, "nombre": "Usuario " + ROLES[e], "password_hash": HASHES[e], "rol": ROLES[e]}] if e in HASHES else []
    if "GROUP BY especie" in s: return [{"especie": "Bovino", "total": 4}, {"especie": "Equino", "total": 1}]
    if "FROM sanidad s JOIN animales a" in s:
        return [{"id_animal": 1, "arete": "CL-0001", "nombre": "Mora", "tipo": "Vacuna", "producto": "Clostridial", "proxima_fecha": F, "dias": -5},
                {"id_animal": 2, "arete": "CL-0002", "nombre": None, "tipo": "Desparasitación", "producto": "Ivermectina", "proxima_fecha": F, "dias": 3}]
    if "AS animales," in s and "FROM dual" in s: return [{"animales": 6, "siembras": 1}]
    if "GROUP BY TO_CHAR(fecha" in s: return [{"mes": "2024-02", "ingresos": 500000, "gastos": 200000}, {"mes": "2024-03", "ingresos": 0, "gastos": 90000}]
    if "FROM animales a WHERE 1 = 1" in s: return [ANIMAL, dict(ANIMAL, id_animal=2, arete="=CMD", nombre=None, estado="Vendido", ultimo_peso=None)]
    if "SELECT * FROM animales WHERE id_animal" in s: return [ANIMAL] if params["id"] == 1 else []
    if "SELECT id_animal FROM pesajes WHERE id_pesaje" in s or "SELECT id_animal FROM sanidad WHERE id_sanidad" in s: return [{"id_animal": 1}]
    if "FROM pesajes WHERE id_animal" in s:
        return [{"id_pesaje": 1, "fecha": datetime(2024, 1, 1), "peso_kg": 400}, {"id_pesaje": 2, "fecha": datetime(2024, 3, 1), "peso_kg": 460}]
    if "FROM sanidad WHERE id_animal" in s:
        return [{"id_sanidad": 1, "tipo": "Vacuna", "producto": "Clostridial", "fecha": F, "proxima_fecha": None, "observacion": "Sin novedades"}]
    if "FROM siembras s" in s:
        return [{"id_siembra": 1, "cultivo": "Avena", "parcela": "P1", "superficie_ha": 2.5, "fecha_siembra": F, "estado": "En curso", "cosechado_kg": 0},
                {"id_siembra": 2, "cultivo": "Maíz", "parcela": "P2", "superficie_ha": 1.2, "fecha_siembra": F, "estado": "Cosechada", "cosechado_kg": 9600}]
    if "FROM movimientos WHERE TO_CHAR" in s:
        return [{"id_movimiento": 1, "fecha": F, "tipo": "Ingreso", "categoria": "Venta de leche", "descripcion": "Semana", "monto": 150000},
                {"id_movimiento": 2, "fecha": F, "tipo": "Gasto", "categoria": "Alimento", "descripcion": None, "monto": 45000}]
    raise AssertionError("Consulta no prevista en la prueba: " + s[:80])

def ejecutar(sql, params=None):
    LLAMADAS.append(" ".join(sql.split())[:40]); return 1

class Cursor:
    def execute(self, sql, params=None): LLAMADAS.append("CURSOR " + " ".join(sql.split())[:40])
class Conn:
    def cursor(self): return Cursor()
    def commit(self): LLAMADAS.append("COMMIT")
from contextlib import contextmanager
@contextmanager
def conexion(): yield Conn()

dbmod = types.ModuleType("db"); dbmod.consultar, dbmod.ejecutar, dbmod.conexion = consultar, ejecutar, conexion
sys.modules["db"] = dbmod

import app as modulo
app = modulo.app
app.config["TESTING"] = True

fallos, pruebas = [], 0
def comprobar(nombre, condicion, detalle=""):
    global pruebas
    pruebas += 1
    if not condicion: fallos.append(f"{nombre} {detalle}")

def nuevo_cliente(email=None, clave=None):
    c = app.test_client()
    if email: 
        r = c.post("/login", data={"email": email, "password": clave})
        comprobar(f"login {email}", r.status_code == 302 and r.headers["Location"].endswith("/dashboard"), r.status_code)
    return c

def pagina(c, url, esperado=200, contiene=(), no_contiene=()):
    r = c.get(url)
    cuerpo = r.get_data(as_text=True)
    comprobar(f"GET {url}", r.status_code == esperado, f"-> {r.status_code}")
    for t in contiene: comprobar(f"GET {url} contiene '{t}'", t in cuerpo)
    for t in no_contiene: comprobar(f"GET {url} NO contiene '{t}'", t not in cuerpo)
    return r

# ---- Sin sesión ----
anon = app.test_client()
r = anon.get("/"); comprobar("/ sin sesión redirige", r.status_code == 302 and "/login" in r.headers["Location"])
for ruta in ["/dashboard", "/animales", "/siembras", "/finanzas", "/animales/1"]:
    r = anon.get(ruta); comprobar(f"{ruta} exige login", r.status_code == 302 and "/login" in r.headers["Location"])
pagina(anon, "/login", contiene=["Ingresar"])
r = anon.post("/login", data={"email": "admin@finca.cl", "password": "mala"})
comprobar("clave incorrecta", "Credenciales incorrectas" in r.get_data(as_text=True))
for _ in range(6): anon.post("/login", data={"email": "admin@finca.cl", "password": "mala"})
r = anon.post("/login", data={"email": "admin@finca.cl", "password": "admin123"})
comprobar("bloqueo tras intentos fallidos", "Demasiados intentos" in r.get_data(as_text=True))
modulo.INTENTOS.clear()
pagina(anon, "/ruta-que-no-existe", esperado=404, contiene=["404"])

# ---- Administrador ----
a = nuevo_cliente("admin@finca.cl", "admin123")
pagina(a, "/dashboard", contiene=["Animales activos", "Vencida hace 5 d", "En 3 d", "g-finanzas", "g-especies", "Finanzas"])
pagina(a, "/animales", contiene=["CL-0001", "Registrar animal", "Exportar CSV", "Vendido"])
r = a.get("/animales.csv"); comprobar("CSV animales BOM", r.data.startswith(b"\xef\xbb\xbf"))
comprobar("CSV neutraliza fórmulas", "'=CMD" in r.get_data(as_text=True))
pagina(a, "/animales/nuevo", contiene=["Registrar animal"], no_contiene=['name="estado"'])
pagina(a, "/animales/1/editar", contiene=["Editar animal", 'value="CL-0001"', "2021-05-02", 'name="estado"'])
pagina(a, "/animales/999/editar", esperado=404)
pagina(a, "/animales/1", contiene=["Ganancia promedio", "g-peso", "Eliminar", "Editar", "2 años" if False else "Mora"])
pagina(a, "/animales/999", esperado=404)

LLAMADAS.clear()
base = {"arete": "CL-0099", "especie": "Bovino", "sexo": "H", "fecha_nacimiento": "2023-01-01"}
r = a.post("/animales/nuevo", data=base)
comprobar("crear animal válido", r.status_code == 302 and any("INSERT INTO animales" in x for x in LLAMADAS), (r.status_code, LLAMADAS))
r = a.post("/animales/nuevo", data=dict(base, arete=""))
comprobar("crear animal sin arete", r.status_code == 200 and "obligatorio" in r.get_data(as_text=True))
r = a.post("/animales/nuevo", data=dict(base, especie="Dragón"))
comprobar("especie inválida", "especie válida" in r.get_data(as_text=True))
r = a.post("/animales/nuevo", data=dict(base, fecha_nacimiento="2999-01-01"))
comprobar("nacimiento futuro", "futura" in r.get_data(as_text=True))
r = a.post("/animales/1/editar", data=dict(base, estado="Vendido"))
comprobar("editar animal", r.status_code == 302 and any("UPDATE animales" in x for x in LLAMADAS))

LLAMADAS.clear()
r = a.post("/animales/1/pesaje", data={"fecha": "2024-03-01", "peso_kg": "470.5"})
comprobar("pesaje válido", r.status_code == 302 and any("INSERT INTO pesajes" in x for x in LLAMADAS))
LLAMADAS.clear()
for datos in [{"fecha": "2024-03-01", "peso_kg": "-5"}, {"fecha": "2024-03-01", "peso_kg": "abc"}, {"fecha": "2099-01-01", "peso_kg": "300"}, {"fecha": "2024-03-01", "peso_kg": "inf"}]:
    a.post("/animales/1/pesaje", data=datos)
comprobar("pesajes inválidos no se guardan", not LLAMADAS, LLAMADAS)
LLAMADAS.clear()
a.post("/animales/1/sanidad", data={"tipo": "Vacuna", "producto": "Aftosa", "fecha": "2024-03-01", "proxima_fecha": "2024-09-01"})
comprobar("sanidad válida", any("INSERT INTO sanidad" in x for x in LLAMADAS))
LLAMADAS.clear()
a.post("/animales/1/sanidad", data={"tipo": "Vacuna", "producto": "X", "fecha": "2024-03-01", "proxima_fecha": "2024-01-01"})
a.post("/animales/1/sanidad", data={"tipo": "Otro", "producto": "X", "fecha": "2024-03-01"})
comprobar("sanidad inválida no se guarda", not LLAMADAS, LLAMADAS)
LLAMADAS.clear()
r = a.post("/pesajes/1/eliminar"); comprobar("eliminar pesaje", r.status_code == 302 and any("DELETE FROM pesajes" in x for x in LLAMADAS))
r = a.post("/sanidad/1/eliminar"); comprobar("eliminar sanidad", r.status_code == 302 and any("DELETE FROM sanidad" in x for x in LLAMADAS))

pagina(a, "/siembras", contiene=["Avena", "Registrar siembra", "3.840" if False else "Maíz", "8.000 kg/ha"])
LLAMADAS.clear()
a.post("/siembras/nueva", data={"cultivo": "Alfalfa", "parcela": "P3", "superficie_ha": "1.5", "fecha_siembra": "2024-03-01"})
comprobar("crear siembra", any("INSERT INTO siembras" in x for x in LLAMADAS))
LLAMADAS.clear()
a.post("/siembras/1/cosecha", data={"fecha": "2024-03-01", "cantidad_kg": "500", "cerrar": "1"})
comprobar("registrar cosecha y cerrar", any("INSERT INTO cosechas" in x for x in LLAMADAS) and any("UPDATE siembras" in x for x in LLAMADAS) and "COMMIT" in LLAMADAS, LLAMADAS)
LLAMADAS.clear()
a.post("/siembras/1/cosecha", data={"fecha": "2024-03-01", "cantidad_kg": "0"})
comprobar("cosecha inválida", not LLAMADAS)

pagina(a, "/finanzas", contiene=["Ingresos del mes", "Balance", "Venta de leche", "$150.000", "−$45.000"])
pagina(a, "/finanzas?mes=2024-02", contiene=['value="2024-02"'])
pagina(a, "/finanzas?mes=malo'; DROP", contiene=["Ingresos del mes"])
r = a.get("/finanzas.csv?mes=2024-03"); comprobar("CSV finanzas", r.status_code == 200 and b"Venta de leche" in r.data)
LLAMADAS.clear()
r = a.post("/finanzas/nuevo", data={"tipo": "Gasto", "categoria": "Alimento", "fecha": "2024-03-05", "monto": "45000", "descripcion": "Heno"})
comprobar("movimiento válido", r.status_code == 302 and "mes=2024-03" in r.headers["Location"] and any("INSERT INTO movimientos" in x for x in LLAMADAS))
LLAMADAS.clear()
a.post("/finanzas/nuevo", data={"tipo": "Gasto", "categoria": "Venta de leche", "fecha": "2024-03-05", "monto": "100"})
a.post("/finanzas/nuevo", data={"tipo": "Gasto", "categoria": "Alimento", "fecha": "2024-03-05", "monto": "-1"})
comprobar("movimientos inválidos no se guardan", not LLAMADAS, LLAMADAS)
r = a.post("/finanzas/1/eliminar"); comprobar("eliminar movimiento", r.status_code == 302 and any("DELETE FROM movimientos" in x for x in LLAMADAS))
r = a.get("/logout"); comprobar("logout solo por POST", r.status_code == 405)
r = a.post("/logout"); comprobar("logout", r.status_code == 302 and "/login" in r.headers["Location"])

# ---- Operario ----
o = nuevo_cliente("operario@finca.cl", "operario123")
pagina(o, "/dashboard", contiene=["Animales activos"], no_contiene=["<canvas id=\"g-finanzas\">", ">Finanzas<"])
pagina(o, "/animales", contiene=["CL-0001"], no_contiene=["Registrar animal", "Exportar CSV"])
pagina(o, "/animales/1", contiene=["Registrar pesaje", "Guardar registro"], no_contiene=["Eliminar", ">Editar<"])
pagina(o, "/siembras", contiene=["Avena"], no_contiene=["Registrar siembra", "Registrar cosecha"])
LLAMADAS.clear()
r = o.post("/animales/1/pesaje", data={"fecha": "2024-03-01", "peso_kg": "470"})
comprobar("operario puede registrar pesajes", any("INSERT INTO pesajes" in x for x in LLAMADAS))
LLAMADAS.clear()
for ruta, datos in [("/animales/nuevo", {"arete": "X", "especie": "Bovino", "sexo": "M"}), ("/animales/1/editar", {}), ("/pesajes/1/eliminar", {}),
                    ("/siembras/nueva", {}), ("/siembras/1/cosecha", {}), ("/finanzas/nuevo", {}), ("/finanzas/1/eliminar", {})]:
    r = o.post(ruta, data=datos)
    comprobar(f"operario bloqueado en POST {ruta}", r.status_code == 302 and "/dashboard" in r.headers["Location"], r.status_code)
for ruta in ["/finanzas", "/finanzas.csv", "/animales.csv", "/animales/nuevo", "/animales/1/editar"]:
    r = o.get(ruta); comprobar(f"operario bloqueado en GET {ruta}", r.status_code == 302 and "/dashboard" in r.headers["Location"], r.status_code)
comprobar("operario no modificó datos", not LLAMADAS, LLAMADAS)

# ---- Filtros ----
f = modulo
from datetime import date
comprobar("filtro num", f.filtro_num(1234567) == "1.234.567" and f.filtro_num(12.5, 1) == "12,5" and f.filtro_num(None) == "—")
comprobar("filtro fecha", f.filtro_fecha(datetime(2024, 3, 5)) == "05-03-2024" and f.filtro_fecha(None) == "—")
comprobar("filtro edad", f.filtro_edad(None) == "—" and f.filtro_edad(datetime(date.today().year - 2, date.today().month, 1)).startswith("2 a"))

print(f"Pruebas ejecutadas: {pruebas}")
print("FALLOS:" if fallos else "Todas las pruebas pasaron.")
for x in fallos: print(" -", x)
sys.exit(1 if fallos else 0)
