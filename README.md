# Gestión de Ganado y Siembras

Aplicación web para administrar una finca: animales, pesajes, sanidad, siembras, cosechas y finanzas, con roles de usuario y alertas sanitarias. Proyecto de portafolio hecho con Flask y Oracle Database.

![Resumen de la finca](docs/resumen.png)

## Funciones

- **Animales:** registro con arete (identificador único), especie, raza, sexo, nacimiento, potrero, origen y estado (Activo, Vendido o Fallecido). Búsqueda y filtros, y exportación a CSV.
- **Pesajes:** historial de peso por animal con gráfico y ganancia diaria promedio.
- **Sanidad:** vacunas, tratamientos y desparasitaciones, con fecha de la próxima aplicación. El resumen muestra las vencidas y las de los próximos 15 días (se considera solo el registro más reciente de cada producto, para no repetir avisos).
- **Siembras y cosechas:** cultivos por parcela y superficie, cosechas en kilos y rendimiento por hectárea.
- **Finanzas:** ingresos y gastos por categoría, resumen y balance mensual, gráfico de los últimos 6 meses y exportación a CSV.
- **Seguridad:** contraseñas cifradas (`werkzeug.security`), protección CSRF, consultas parametrizadas, secretos en variables de entorno, límite de intentos de inicio de sesión, mensajes de error genéricos y protección contra fórmulas maliciosas en el CSV.

## Roles

| Acción | Administrador | Operario |
| --- | :---: | :---: |
| Ver animales, siembras y alertas | Sí | Sí |
| Registrar pesajes y sanidad | Sí | Sí |
| Crear y editar animales | Sí | No |
| Eliminar pesajes y registros sanitarios | Sí | No |
| Registrar siembras y cosechas | Sí | No |
| Finanzas y exportar CSV | Sí | No |

## Tecnologías

- Python 3 y Flask
- Oracle Database con `python-oracledb` (modo Thin: no requiere instalar Oracle Client)
- Flask-WTF (CSRF) y Werkzeug (hash de contraseñas)
- Chart.js para los gráficos
- HTML5, CSS3 y JavaScript

## Estructura del proyecto

```
ganaderia-agro/
├── app.py              # rutas y lógica de negocio
├── db.py               # conexión a Oracle y funciones de consulta
├── seed.py             # claves de demostración y datos de ejemplo
├── schema.sql          # tablas, índices y datos iniciales
├── reset.sql           # borra todas las tablas (¡cuidado!)
├── requirements.txt
├── .env.example        # plantilla de variables de entorno
├── templates/          # páginas HTML (Jinja2)
├── static/             # styles.css y main.js
└── tests/              # pruebas de rutas y permisos
```

**Modelo de datos:** `roles`, `usuarios`, `animales`, `pesajes`, `sanidad`, `siembras`, `cosechas` y `movimientos`, con llaves foráneas, restricciones `CHECK` (por ejemplo, pesos y montos positivos) e índices en las consultas más usadas.

## Instalación local

1. Clona el repositorio y crea un entorno virtual:

   ```bash
   git clone https://github.com/claudiopizarro12313/ganaderia-agro.git
   cd ganaderia-agro
   python -m venv venv
   venv\Scripts\activate
   ```

   En Mac o Linux, el último comando es `source venv/bin/activate`.

2. Instala las dependencias:

   ```bash
   pip install -r requirements.txt
   ```

3. Prepara la base de datos. Conéctate como administrador a tu base (en Oracle XE, a la base pluggable `XEPDB1`) y crea un usuario para el proyecto:

   ```sql
   CREATE USER ganaderia IDENTIFIED BY "tu_clave" QUOTA UNLIMITED ON USERS;
   GRANT CREATE SESSION, CREATE TABLE, CREATE SEQUENCE, CREATE VIEW TO ganaderia;
   ```

   Luego, conectado con ese usuario, ejecuta `schema.sql`.

4. Configura las variables de entorno. Copia `.env.example` a `.env` y completa los valores:

   ```
   FLASK_SECRET_KEY=una_clave_larga_y_aleatoria
   DB_USER=ganaderia
   DB_PASSWORD=tu_clave
   DB_DSN=localhost:1521/XEPDB1
   ```

   Para generar una clave secreta:

   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

5. Crea las claves de demostración y los datos de ejemplo:

   ```bash
   python seed.py
   ```

6. Inicia la aplicación y abre http://127.0.0.1:5000 en el navegador:

   ```bash
   python app.py
   ```

## Usuarios de demostración

Solo para pruebas en un entorno local:

| Rol | Correo | Contraseña |
| --- | --- | --- |
| Administrador | `admin@finca.cl` | `admin123` |
| Operario | `operario@finca.cl` | `operario123` |

## Pruebas

Las pruebas revisan las rutas, los permisos por rol y las validaciones de los formularios con una base de datos simulada, por lo que no necesitan Oracle:

```bash
python tests/test_rutas.py
```

## Limitaciones y próximos pasos

- El límite de intentos de inicio de sesión se guarda en memoria: sirve para un solo proceso.
- Faltan la gestión de usuarios desde la interfaz y un registro de potreros con su capacidad.
- Ideas: alertas por correo o WhatsApp, fotos de los animales y reporte de rentabilidad por animal o cultivo.

## Autor

Claudio Pizarro, analista programador. [Portafolio y GitHub](https://github.com/claudiopizarro12313)
