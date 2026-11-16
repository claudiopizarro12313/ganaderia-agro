import csv
import io
import math
import os
import re
import time
from datetime import date
from functools import wraps

import oracledb
from dotenv import load_dotenv
from flask import (Flask, Response, abort, flash, redirect, render_template,
                   request, session, url_for)
from flask_wtf.csrf import CSRFError, CSRFProtect
from werkzeug.security import check_password_hash

from db import conexion, consultar, ejecutar

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ["FLASK_SECRET_KEY"]
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
csrf = CSRFProtect(app)

ESPECIES = ["Bovino", "Equino", "Ovino", "Caprino", "Porcino", "Otro"]
ESTADOS = ["Activo", "Vendido", "Fallecido"]
TIPOS_SANIDAD = ["Vacuna", "Tratamiento", "Desparasitación"]
CATEGORIAS = {
    "Ingreso": ["Venta de animales", "Venta de leche", "Venta de cosecha", "Otros ingresos"],
    "Gasto": ["Alimento", "Veterinario", "Mano de obra", "Combustible",
              "Semillas e insumos", "Mantención", "Otros gastos"],
}
app.jinja_env.globals.update(ESPECIES=ESPECIES, ESTADOS=ESTADOS,
                             TIPOS_SANIDAD=TIPOS_SANIDAD, CATEGORIAS=CATEGORIAS)


# ---------- Filtros de plantilla ----------
@app.template_filter("fecha")
def filtro_fecha(valor):
    return valor.strftime("%d-%m-%Y") if valor else "—"


@app.template_filter("num")
def filtro_num(valor, decimales=0):
    if valor is None:
        return "—"
    texto = f"{valor:,.{decimales}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


@app.template_filter("edad")
def filtro_edad(nacimiento):
    if not nacimiento:
        return "—"
    hoy = date.today()
    meses = (hoy.year - nacimiento.year) * 12 + hoy.month - nacimiento.month
    if hoy.day < nacimiento.day:
        meses -= 1
    anios, resto = divmod(max(meses, 0), 12)
    if anios and resto:
        return f"{anios} a {resto} m"
    if anios:
        return f"{anios} a"
    return f"{resto} m"


# ---------- Acceso y permisos ----------
def es_admin():
    return session.get("rol") == "Administrador"


def login_requerido(f):
    @wraps(f)
    def interior(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return interior


def solo_admin(f):
    @wraps(f)
    @login_requerido
    def interior(*args, **kwargs):
        if not es_admin():
            flash("Acceso no autorizado.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return interior


def volver(defecto="dashboard"):
    """Vuelve a la página anterior, solo si es de este mismo sitio."""
    anterior = request.referrer or ""
    if anterior.startswith(request.host_url):
        return redirect(anterior)
    return redirect(url_for(defecto))


def seguro(f):
    """Captura errores de las acciones POST: registra el detalle y muestra un mensaje genérico."""
    @wraps(f)
    def interior(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except oracledb.IntegrityError:
            app.logger.exception("Error de integridad en %s", f.__name__)
            flash("No se pudo guardar: hay un dato repetido o relacionado con otro registro.", "danger")
        except Exception:
            app.logger.exception("Error en %s", f.__name__)
            flash("Ocurrió un error. Intenta nuevamente.", "danger")
        return volver()
    return interior


# ---------- Lectura de datos de formularios ----------
def a_fecha(valor):
    try:
        return date.fromisoformat(valor) if valor else None
    except (ValueError, TypeError):
        return None


def a_numero(valor):
    try:
        numero = float(valor)
    except (ValueError, TypeError):
        return None
    return numero if math.isfinite(numero) else None


def texto(nombre, largo, obligatorio=False):
    valor = request.form.get(nombre, "").strip()[:largo]
    return valor if (valor or obligatorio) else None


def celda_csv(valor):
    if isinstance(valor, date):
        return valor.strftime("%Y-%m-%d")
    if isinstance(valor, str) and valor[:1] in ("=", "+", "-", "@"):
        return "'" + valor
    return "" if valor is None else valor


def csv_respuesta(nombre, encabezados, filas):
    salida = io.StringIO()
    escritor = csv.writer(salida)
    escritor.writerow(encabezados)
    for fila in filas:
        escritor.writerow([celda_csv(v) for v in fila])
    respuesta = Response(salida.getvalue().encode("utf-8-sig"), mimetype="text/csv")
    respuesta.headers["Content-Disposition"] = f"attachment; filename={nombre}"
    return respuesta


# ---------- Sesión ----------
INTENTOS = {}
MAX_INTENTOS, VENTANA_SEG = 5, 300


def demasiados_intentos(ip):
    ahora = time.time()
    INTENTOS[ip] = [t for t in INTENTOS.get(ip, []) if ahora - t < VENTANA_SEG]
    return len(INTENTOS[ip]) >= MAX_INTENTOS


@app.route("/")
def index():
    return redirect(url_for("dashboard" if "usuario_id" in session else "login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        ip = request.remote_addr or "?"
        if demasiados_intentos(ip):
            flash("Demasiados intentos fallidos. Espera unos minutos.", "warning")
            return render_template("login.html")
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        try:
            filas = consultar(
                """SELECT u.id_usuario, u.nombre, u.password_hash, r.nombre AS rol
                   FROM usuarios u JOIN roles r ON u.id_rol = r.id_rol
                   WHERE u.email = :email""", {"email": email})
        except Exception:
            app.logger.exception("Error en el login")
            flash("Ocurrió un error al intentar iniciar sesión.", "danger")
            return render_template("login.html")
        if filas and check_password_hash(filas[0]["password_hash"], password):
            INTENTOS.pop(ip, None)
            session.clear()
            session["usuario_id"] = filas[0]["id_usuario"]
            session["usuario"] = filas[0]["nombre"]
            session["rol"] = filas[0]["rol"]
            return redirect(url_for("dashboard"))
        INTENTOS.setdefault(ip, []).append(time.time())
        flash("Credenciales incorrectas. Intenta de nuevo.", "danger")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Has cerrado sesión correctamente.", "info")
    return redirect(url_for("login"))


# ---------- Resumen ----------
@app.route("/dashboard")
@login_requerido
def dashboard():
    especies = consultar(
        """SELECT especie, COUNT(*) AS total FROM animales
           WHERE estado = 'Activo' GROUP BY especie ORDER BY total DESC""")
    alertas = consultar(
        """SELECT a.id_animal, a.arete, a.nombre, s.tipo, s.producto, s.proxima_fecha,
                  TRUNC(s.proxima_fecha) - TRUNC(SYSDATE) AS dias
           FROM sanidad s JOIN animales a ON a.id_animal = s.id_animal
           WHERE a.estado = 'Activo' AND s.proxima_fecha IS NOT NULL
             AND s.proxima_fecha <= TRUNC(SYSDATE) + 15
             AND s.fecha = (SELECT MAX(s2.fecha) FROM sanidad s2
                            WHERE s2.id_animal = s.id_animal AND s2.producto = s.producto)
           ORDER BY s.proxima_fecha""")
    resumen = consultar(
        """SELECT (SELECT COUNT(*) FROM animales WHERE estado = 'Activo') AS animales,
                  (SELECT COUNT(*) FROM siembras WHERE estado = 'En curso') AS siembras
           FROM dual""")[0]
    finanzas = []
    if es_admin():
        finanzas = consultar(
            """SELECT TO_CHAR(fecha, 'YYYY-MM') AS mes,
                      SUM(CASE WHEN tipo = 'Ingreso' THEN monto ELSE 0 END) AS ingresos,
                      SUM(CASE WHEN tipo = 'Gasto' THEN monto ELSE 0 END) AS gastos
               FROM movimientos
               WHERE fecha >= ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -5)
               GROUP BY TO_CHAR(fecha, 'YYYY-MM') ORDER BY mes""")
    return render_template("dashboard.html", especies=especies, alertas=alertas,
                           resumen=resumen, finanzas=finanzas)


# ---------- Animales ----------
SQL_ANIMALES = """
    SELECT a.id_animal, a.arete, a.nombre, a.especie, a.raza, a.sexo, a.fecha_nacimiento,
           a.potrero, a.estado,
           (SELECT p.peso_kg FROM pesajes p
             WHERE p.id_animal = a.id_animal
               AND p.fecha = (SELECT MAX(p2.fecha) FROM pesajes p2
                               WHERE p2.id_animal = a.id_animal)) AS ultimo_peso
    FROM animales a WHERE 1 = 1"""


def filtrar_animales():
    q = request.args.get("q", "").strip()
    estado = request.args.get("estado", "Activo")
    especie = request.args.get("especie", "")
    sql, params = SQL_ANIMALES, {}
    if estado in ESTADOS:
        sql += " AND a.estado = :estado"
        params["estado"] = estado
    if especie in ESPECIES:
        sql += " AND a.especie = :especie"
        params["especie"] = especie
    if q:
        sql += " AND (UPPER(a.arete) LIKE :q OR UPPER(a.nombre) LIKE :q)"
        params["q"] = f"%{q.upper()}%"
    sql += " ORDER BY a.id_animal DESC"
    return consultar(sql, params), {"q": q, "estado": estado, "especie": especie}


@app.route("/animales")
@login_requerido
def animales():
    filas, filtros = filtrar_animales()
    return render_template("animales.html", animales=filas, filtros=filtros)


@app.route("/animales.csv")
@solo_admin
def animales_csv():
    filas, _ = filtrar_animales()
    return csv_respuesta(
        "animales.csv",
        ["Arete", "Nombre", "Especie", "Raza", "Sexo", "Nacimiento", "Potrero", "Estado", "Último peso (kg)"],
        [(a["arete"], a["nombre"], a["especie"], a["raza"], a["sexo"], a["fecha_nacimiento"],
          a["potrero"], a["estado"], a["ultimo_peso"]) for a in filas])


def leer_animal():
    f = request.form
    animal = {
        "arete": texto("arete", 30, True),
        "nombre": texto("nombre", 60),
        "especie": f.get("especie"),
        "raza": texto("raza", 60),
        "sexo": f.get("sexo"),
        "fecha_nacimiento": a_fecha(f.get("fecha_nacimiento")),
        "potrero": texto("potrero", 60),
        "origen": texto("origen", 100),
        "estado": f.get("estado", "Activo"),
        "notas": texto("notas", 300),
    }
    error = None
    if not animal["arete"]:
        error = "El arete es obligatorio."
    elif animal["especie"] not in ESPECIES:
        error = "Elige una especie válida."
    elif animal["sexo"] not in ("M", "H"):
        error = "Elige el sexo del animal."
    elif animal["estado"] not in ESTADOS:
        error = "Elige un estado válido."
    elif f.get("fecha_nacimiento") and animal["fecha_nacimiento"] is None:
        error = "La fecha de nacimiento no es válida."
    elif animal["fecha_nacimiento"] and animal["fecha_nacimiento"] > date.today():
        error = "La fecha de nacimiento no puede ser futura."
    return animal, error


SQL_INSERTAR_ANIMAL = """
    INSERT INTO animales (arete, nombre, especie, raza, sexo, fecha_nacimiento, potrero, origen, estado, notas)
    VALUES (:arete, :nombre, :especie, :raza, :sexo, :fecha_nacimiento, :potrero, :origen, :estado, :notas)"""

SQL_ACTUALIZAR_ANIMAL = """
    UPDATE animales SET arete = :arete, nombre = :nombre, especie = :especie, raza = :raza, sexo = :sexo,
           fecha_nacimiento = :fecha_nacimiento, potrero = :potrero, origen = :origen,
           estado = :estado, notas = :notas
    WHERE id_animal = :id"""


@app.route("/animales/nuevo", methods=["GET", "POST"])
@solo_admin
def animal_nuevo():
    animal = None
    if request.method == "POST":
        animal, error = leer_animal()
        if not error:
            try:
                ejecutar(SQL_INSERTAR_ANIMAL, animal)
                flash("Animal registrado correctamente.", "success")
                return redirect(url_for("animales"))
            except oracledb.IntegrityError:
                error = "Ya existe un animal con ese arete."
            except Exception:
                app.logger.exception("Error al registrar animal")
                error = "No se pudo registrar el animal."
        flash(error, "warning")
    return render_template("animal_form.html", animal=animal, id_animal=None)


@app.route("/animales/<int:id_animal>/editar", methods=["GET", "POST"])
@solo_admin
def animal_editar(id_animal):
    if request.method == "POST":
        animal, error = leer_animal()
        if not error:
            animal["id"] = id_animal
            try:
                ejecutar(SQL_ACTUALIZAR_ANIMAL, animal)
                flash("Animal actualizado correctamente.", "success")
                return redirect(url_for("animal_detalle", id_animal=id_animal))
            except oracledb.IntegrityError:
                error = "Ya existe otro animal con ese arete."
            except Exception:
                app.logger.exception("Error al actualizar animal")
                error = "No se pudo actualizar el animal."
        flash(error, "warning")
    else:
        filas = consultar("SELECT * FROM animales WHERE id_animal = :id", {"id": id_animal})
        if not filas:
            abort(404)
        animal = filas[0]
    return render_template("animal_form.html", animal=animal, id_animal=id_animal)


@app.route("/animales/<int:id_animal>")
@login_requerido
def animal_detalle(id_animal):
    filas = consultar("SELECT * FROM animales WHERE id_animal = :id", {"id": id_animal})
    if not filas:
        abort(404)
    pesajes = consultar(
        "SELECT id_pesaje, fecha, peso_kg FROM pesajes WHERE id_animal = :id ORDER BY fecha",
        {"id": id_animal})
    sanidad = consultar(
        """SELECT id_sanidad, tipo, producto, fecha, proxima_fecha, observacion
           FROM sanidad WHERE id_animal = :id ORDER BY fecha DESC""", {"id": id_animal})
    ganancia = None
    if len(pesajes) >= 2:
        dias = (pesajes[-1]["fecha"] - pesajes[0]["fecha"]).days
        if dias > 0:
            ganancia = (pesajes[-1]["peso_kg"] - pesajes[0]["peso_kg"]) / dias
    grafico = {"etiquetas": [p["fecha"].strftime("%d-%m-%Y") for p in pesajes],
               "datos": [float(p["peso_kg"]) for p in pesajes]}
    return render_template("animal_detalle.html", animal=filas[0], pesajes=pesajes,
                           sanidad=sanidad, ganancia=ganancia, grafico=grafico, hoy=date.today())


@app.route("/animales/<int:id_animal>/pesaje", methods=["POST"])
@login_requerido
@seguro
def pesaje_nuevo(id_animal):
    fecha = a_fecha(request.form.get("fecha"))
    peso = a_numero(request.form.get("peso_kg"))
    if not fecha or fecha > date.today() or peso is None or not 0 < peso < 5000:
        flash("Revisa la fecha y el peso (en kg).", "warning")
    else:
        ejecutar("INSERT INTO pesajes (id_animal, fecha, peso_kg) VALUES (:a, :f, :p)",
                 {"a": id_animal, "f": fecha, "p": peso})
        flash("Pesaje registrado.", "success")
    return redirect(url_for("animal_detalle", id_animal=id_animal))


@app.route("/animales/<int:id_animal>/sanidad", methods=["POST"])
@login_requerido
@seguro
def sanidad_nueva(id_animal):
    tipo = request.form.get("tipo")
    producto = texto("producto", 100, True)
    fecha = a_fecha(request.form.get("fecha"))
    proxima = a_fecha(request.form.get("proxima_fecha"))
    if (tipo not in TIPOS_SANIDAD or not producto or not fecha
            or (request.form.get("proxima_fecha") and proxima is None)):
        flash("Revisa el tipo, el producto y las fechas.", "warning")
    elif proxima and proxima < fecha:
        flash("La próxima fecha no puede ser anterior a la fecha de aplicación.", "warning")
    else:
        ejecutar("""INSERT INTO sanidad (id_animal, tipo, producto, fecha, proxima_fecha, observacion)
                    VALUES (:a, :t, :pr, :f, :px, :o)""",
                 {"a": id_animal, "t": tipo, "pr": producto, "f": fecha,
                  "px": proxima, "o": texto("observacion", 200)})
        flash("Registro sanitario guardado.", "success")
    return redirect(url_for("animal_detalle", id_animal=id_animal))


def eliminar_hijo(tabla, columna_id, id_registro):
    filas = consultar(f"SELECT id_animal FROM {tabla} WHERE {columna_id} = :id", {"id": id_registro})
    if not filas:
        abort(404)
    ejecutar(f"DELETE FROM {tabla} WHERE {columna_id} = :id", {"id": id_registro})
    return filas[0]["id_animal"]


@app.route("/pesajes/<int:id_pesaje>/eliminar", methods=["POST"])
@solo_admin
@seguro
def pesaje_eliminar(id_pesaje):
    id_animal = eliminar_hijo("pesajes", "id_pesaje", id_pesaje)
    flash("Pesaje eliminado.", "info")
    return redirect(url_for("animal_detalle", id_animal=id_animal))


@app.route("/sanidad/<int:id_sanidad>/eliminar", methods=["POST"])
@solo_admin
@seguro
def sanidad_eliminar(id_sanidad):
    id_animal = eliminar_hijo("sanidad", "id_sanidad", id_sanidad)
    flash("Registro sanitario eliminado.", "info")
    return redirect(url_for("animal_detalle", id_animal=id_animal))


# ---------- Siembras y cosechas ----------
@app.route("/siembras")
@login_requerido
def siembras():
    filas = consultar(
        """SELECT s.id_siembra, s.cultivo, s.parcela, s.superficie_ha, s.fecha_siembra, s.estado,
                  NVL((SELECT SUM(c.cantidad_kg) FROM cosechas c
                        WHERE c.id_siembra = s.id_siembra), 0) AS cosechado_kg
           FROM siembras s ORDER BY s.fecha_siembra DESC""")
    return render_template("siembras.html", siembras=filas, hoy=date.today())


@app.route("/siembras/nueva", methods=["POST"])
@solo_admin
@seguro
def siembra_nueva():
    cultivo = texto("cultivo", 80, True)
    parcela = texto("parcela", 80, True)
    superficie = a_numero(request.form.get("superficie_ha"))
    fecha = a_fecha(request.form.get("fecha_siembra"))
    if not cultivo or not parcela or not fecha or superficie is None or not 0 < superficie < 100000:
        flash("Revisa el cultivo, la parcela, la superficie y la fecha.", "warning")
    else:
        ejecutar("""INSERT INTO siembras (cultivo, parcela, superficie_ha, fecha_siembra, notas)
                    VALUES (:c, :p, :s, :f, :n)""",
                 {"c": cultivo, "p": parcela, "s": superficie, "f": fecha, "n": texto("notas", 200)})
        flash("Siembra registrada.", "success")
    return redirect(url_for("siembras"))


@app.route("/siembras/<int:id_siembra>/cosecha", methods=["POST"])
@solo_admin
@seguro
def cosecha_nueva(id_siembra):
    fecha = a_fecha(request.form.get("fecha"))
    cantidad = a_numero(request.form.get("cantidad_kg"))
    if not fecha or fecha > date.today() or cantidad is None or not 0 < cantidad < 100000000:
        flash("Revisa la fecha y la cantidad cosechada (en kg).", "warning")
        return redirect(url_for("siembras"))
    with conexion() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO cosechas (id_siembra, fecha, cantidad_kg) VALUES (:s, :f, :c)",
                       {"s": id_siembra, "f": fecha, "c": cantidad})
        if request.form.get("cerrar"):
            cursor.execute("UPDATE siembras SET estado = 'Cosechada' WHERE id_siembra = :s",
                           {"s": id_siembra})
        conn.commit()
    flash("Cosecha registrada.", "success")
    return redirect(url_for("siembras"))


# ---------- Finanzas (solo administrador) ----------
def mes_elegido():
    mes = request.args.get("mes", "")
    return mes if re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", mes) else date.today().strftime("%Y-%m")


def movimientos_del_mes(mes):
    return consultar(
        """SELECT id_movimiento, fecha, tipo, categoria, descripcion, monto
           FROM movimientos WHERE TO_CHAR(fecha, 'YYYY-MM') = :mes
           ORDER BY fecha DESC, id_movimiento DESC""", {"mes": mes})


@app.route("/finanzas")
@solo_admin
def finanzas():
    mes = mes_elegido()
    movimientos = movimientos_del_mes(mes)
    ingresos = sum(m["monto"] for m in movimientos if m["tipo"] == "Ingreso")
    gastos = sum(m["monto"] for m in movimientos if m["tipo"] == "Gasto")
    return render_template("finanzas.html", mes=mes, movimientos=movimientos,
                           ingresos=ingresos, gastos=gastos, hoy=date.today())


@app.route("/finanzas.csv")
@solo_admin
def finanzas_csv():
    mes = mes_elegido()
    return csv_respuesta(
        f"finanzas_{mes}.csv", ["Fecha", "Tipo", "Categoría", "Descripción", "Monto ($)"],
        [(m["fecha"], m["tipo"], m["categoria"], m["descripcion"], m["monto"])
         for m in movimientos_del_mes(mes)])


@app.route("/finanzas/nuevo", methods=["POST"])
@solo_admin
@seguro
def movimiento_nuevo():
    tipo = request.form.get("tipo")
    categoria = request.form.get("categoria")
    fecha = a_fecha(request.form.get("fecha"))
    monto = a_numero(request.form.get("monto"))
    if (tipo not in CATEGORIAS or categoria not in CATEGORIAS.get(tipo, []) or not fecha
            or monto is None or not 0 < monto < 10000000000):
        flash("Revisa el tipo, la categoría, la fecha y el monto.", "warning")
        return redirect(url_for("finanzas"))
    ejecutar("""INSERT INTO movimientos (fecha, tipo, categoria, descripcion, monto, id_usuario)
                VALUES (:f, :t, :c, :d, :m, :u)""",
             {"f": fecha, "t": tipo, "c": categoria, "d": texto("descripcion", 200),
              "m": monto, "u": session["usuario_id"]})
    flash("Movimiento registrado.", "success")
    return redirect(url_for("finanzas", mes=fecha.strftime("%Y-%m")))


@app.route("/finanzas/<int:id_movimiento>/eliminar", methods=["POST"])
@solo_admin
@seguro
def movimiento_eliminar(id_movimiento):
    ejecutar("DELETE FROM movimientos WHERE id_movimiento = :id", {"id": id_movimiento})
    flash("Movimiento eliminado.", "info")
    return volver("finanzas")


# ---------- Errores ----------
@app.errorhandler(CSRFError)
def error_csrf(e):
    flash("El formulario expiró. Vuelve a intentarlo.", "warning")
    return volver()


@app.errorhandler(404)
def no_encontrado(e):
    return render_template("error.html", codigo=404, mensaje="No encontramos esa página."), 404


@app.errorhandler(500)
def error_interno(e):
    return render_template("error.html", codigo=500, mensaje="Ocurrió un error en el servidor."), 500


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1")
