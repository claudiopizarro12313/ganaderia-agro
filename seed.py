from datetime import date, timedelta

from werkzeug.security import generate_password_hash

from db import conexion

USUARIOS = [
    ("admin@finca.cl", "admin123"),
    ("operario@finca.cl", "operario123"),
]


def hace(dias):
    return date.today() - timedelta(days=dias)


def cargar_ejemplos(cur):
    animales = [
        ("CL-0001", "Mora", "Bovino", "Hereford", "H", hace(1200), "Potrero Norte", "Compra a vecino"),
        ("CL-0002", "Bravo", "Bovino", "Angus", "M", hace(1500), "Potrero Norte", "Compra a vecino"),
        ("CL-0003", "Pintada", "Bovino", "Holstein", "H", hace(800), "Potrero Sur", "Nacida en el predio"),
        ("CL-0004", None, "Bovino", "Angus", "M", hace(300), "Potrero Sur", "Nacido en el predio"),
        ("CL-0005", "Canelo", "Equino", "Criollo", "M", hace(2200), "Caballeriza", "Compra"),
        ("CL-0006", "Lola", "Ovino", "Corriedale", "H", hace(700), "Potrero Este", "Compra"),
    ]
    for fila in animales:
        cur.execute(
            """INSERT INTO animales (arete, nombre, especie, raza, sexo, fecha_nacimiento, potrero, origen)
               VALUES (:1, :2, :3, :4, :5, :6, :7, :8)""", fila)
    cur.execute("SELECT arete, id_animal FROM animales")
    ids = dict(cur.fetchall())

    pesajes = [
        ("CL-0004", 150, 142), ("CL-0004", 120, 168), ("CL-0004", 90, 192),
        ("CL-0004", 60, 219), ("CL-0004", 30, 243), ("CL-0004", 2, 262),
        ("CL-0003", 90, 540), ("CL-0003", 30, 562),
        ("CL-0001", 60, 455), ("CL-0001", 5, 468),
        ("CL-0002", 45, 640),
    ]
    for arete, dias, peso in pesajes:
        cur.execute("INSERT INTO pesajes (id_animal, fecha, peso_kg) VALUES (:1, :2, :3)",
                    (ids[arete], hace(dias), peso))

    sanidad = [
        ("CL-0001", "Vacuna", "Vacuna clostridial", hace(170), hace(-10), None),
        ("CL-0001", "Desparasitación", "Ivermectina", hace(95), hace(5), None),
        ("CL-0003", "Vacuna", "Vacuna clostridial", hace(160), hace(-5), None),
        ("CL-0004", "Vacuna", "Vacuna clostridial", hace(20), hace(-160), None),
        ("CL-0002", "Tratamiento", "Antibiótico", hace(40), None, "Herida en la pata, evolución normal"),
    ]
    for arete, tipo, producto, fecha, proxima, obs in sanidad:
        cur.execute(
            """INSERT INTO sanidad (id_animal, tipo, producto, fecha, proxima_fecha, observacion)
               VALUES (:1, :2, :3, :4, :5, :6)""",
            (ids[arete], tipo, producto, fecha, proxima, obs))

    cur.execute("INSERT INTO siembras (cultivo, parcela, superficie_ha, fecha_siembra, estado) "
                "VALUES ('Avena', 'Parcela 1', 2.5, :1, 'En curso')", (hace(120),))
    cur.execute("INSERT INTO siembras (cultivo, parcela, superficie_ha, fecha_siembra, estado) "
                "VALUES ('Maíz', 'Parcela 2', 1.2, :1, 'Cosechada')", (hace(220),))
    cur.execute("INSERT INTO cosechas (id_siembra, fecha, cantidad_kg) "
                "SELECT id_siembra, :1, 9600 FROM siembras WHERE cultivo = 'Maíz'", (hace(40),))

    movimientos = [
        (110, "Gasto", "Alimento", "Fardos de heno", 180000),
        (100, "Gasto", "Veterinario", "Vacunas", 65000),
        (85, "Ingreso", "Venta de animales", "Venta de 2 terneros", 1250000),
        (70, "Gasto", "Semillas e insumos", "Semilla de avena", 90000),
        (55, "Gasto", "Mano de obra", "Jornal de trabajo", 120000),
        (40, "Ingreso", "Venta de cosecha", "Venta de maíz", 480000),
        (25, "Gasto", "Combustible", "Diésel del tractor", 70000),
        (12, "Gasto", "Alimento", "Sales minerales", 45000),
        (4, "Ingreso", "Venta de leche", "Venta semanal", 150000),
    ]
    for dias, tipo, categoria, desc, monto in movimientos:
        cur.execute("INSERT INTO movimientos (fecha, tipo, categoria, descripcion, monto) "
                    "VALUES (:1, :2, :3, :4, :5)", (hace(dias), tipo, categoria, desc, monto))


def poblar():
    try:
        with conexion() as conn:
            cur = conn.cursor()
            for email, clave in USUARIOS:
                cur.execute("UPDATE usuarios SET password_hash = :1 WHERE email = :2",
                            (generate_password_hash(clave), email))
            cur.execute("SELECT COUNT(*) FROM animales")
            if cur.fetchone()[0] == 0:
                cargar_ejemplos(cur)
                print("Datos de ejemplo cargados.")
            else:
                print("Ya hay animales registrados: no se cargaron datos de ejemplo.")
            conn.commit()
            print("Claves de demostración actualizadas correctamente.")
    except Exception as e:
        print(f"Error al preparar los datos: {e}")


if __name__ == "__main__":
    poblar()
