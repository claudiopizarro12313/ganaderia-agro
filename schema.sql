-- ============================================================
-- Sistema de gestión de ganado y siembras (Oracle)
-- Ejecutar con el usuario del proyecto (ver README).
-- Para borrar todo y empezar de cero, usa reset.sql.
-- ============================================================

CREATE TABLE roles (
    id_rol NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre VARCHAR2(50) NOT NULL UNIQUE
);

CREATE TABLE usuarios (
    id_usuario NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre VARCHAR2(100) NOT NULL,
    email VARCHAR2(100) NOT NULL UNIQUE,
    password_hash VARCHAR2(255) NOT NULL,
    id_rol NUMBER NOT NULL,
    CONSTRAINT fk_usuario_rol FOREIGN KEY (id_rol) REFERENCES roles(id_rol)
);

CREATE TABLE animales (
    id_animal NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    arete VARCHAR2(30) NOT NULL UNIQUE,
    nombre VARCHAR2(60),
    especie VARCHAR2(20) NOT NULL
        CONSTRAINT chk_especie CHECK (especie IN ('Bovino', 'Equino', 'Ovino', 'Caprino', 'Porcino', 'Otro')),
    raza VARCHAR2(60),
    sexo VARCHAR2(1) NOT NULL CONSTRAINT chk_sexo CHECK (sexo IN ('M', 'H')),
    fecha_nacimiento DATE,
    potrero VARCHAR2(60),
    origen VARCHAR2(100),
    estado VARCHAR2(10) DEFAULT 'Activo' NOT NULL
        CONSTRAINT chk_estado_animal CHECK (estado IN ('Activo', 'Vendido', 'Fallecido')),
    notas VARCHAR2(300),
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE pesajes (
    id_pesaje NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_animal NUMBER NOT NULL,
    fecha DATE NOT NULL,
    peso_kg NUMBER(7, 2) NOT NULL CONSTRAINT chk_peso_pos CHECK (peso_kg > 0),
    CONSTRAINT fk_pesaje_animal FOREIGN KEY (id_animal) REFERENCES animales(id_animal) ON DELETE CASCADE,
    CONSTRAINT uq_pesaje_fecha UNIQUE (id_animal, fecha)
);

CREATE TABLE sanidad (
    id_sanidad NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_animal NUMBER NOT NULL,
    tipo VARCHAR2(20) NOT NULL
        CONSTRAINT chk_tipo_sanidad CHECK (tipo IN ('Vacuna', 'Tratamiento', 'Desparasitación')),
    producto VARCHAR2(100) NOT NULL,
    fecha DATE NOT NULL,
    proxima_fecha DATE,
    observacion VARCHAR2(200),
    CONSTRAINT fk_sanidad_animal FOREIGN KEY (id_animal) REFERENCES animales(id_animal) ON DELETE CASCADE
);

CREATE TABLE siembras (
    id_siembra NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cultivo VARCHAR2(80) NOT NULL,
    parcela VARCHAR2(80) NOT NULL,
    superficie_ha NUMBER(8, 2) NOT NULL CONSTRAINT chk_superficie_pos CHECK (superficie_ha > 0),
    fecha_siembra DATE NOT NULL,
    estado VARCHAR2(12) DEFAULT 'En curso' NOT NULL
        CONSTRAINT chk_estado_siembra CHECK (estado IN ('En curso', 'Cosechada')),
    notas VARCHAR2(200)
);

CREATE TABLE cosechas (
    id_cosecha NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_siembra NUMBER NOT NULL,
    fecha DATE NOT NULL,
    cantidad_kg NUMBER(10, 2) NOT NULL CONSTRAINT chk_cosecha_pos CHECK (cantidad_kg > 0),
    CONSTRAINT fk_cosecha_siembra FOREIGN KEY (id_siembra) REFERENCES siembras(id_siembra) ON DELETE CASCADE
);

CREATE TABLE movimientos (
    id_movimiento NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fecha DATE NOT NULL,
    tipo VARCHAR2(7) NOT NULL CONSTRAINT chk_tipo_mov CHECK (tipo IN ('Ingreso', 'Gasto')),
    categoria VARCHAR2(40) NOT NULL,
    descripcion VARCHAR2(200),
    monto NUMBER(12, 2) NOT NULL CONSTRAINT chk_monto_pos CHECK (monto > 0),
    id_usuario NUMBER,
    CONSTRAINT fk_mov_usuario FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario)
);

-- Índices para las consultas más frecuentes
CREATE INDEX idx_sanidad_animal ON sanidad(id_animal);
CREATE INDEX idx_sanidad_proxima ON sanidad(proxima_fecha);
CREATE INDEX idx_cosechas_siembra ON cosechas(id_siembra);
CREATE INDEX idx_movimientos_fecha ON movimientos(fecha);

-- Datos iniciales. Las claves reales se crean con: python seed.py
INSERT INTO roles (nombre) VALUES ('Administrador');
INSERT INTO roles (nombre) VALUES ('Operario');

INSERT INTO usuarios (nombre, email, password_hash, id_rol)
VALUES ('Administrador Finca', 'admin@finca.cl', 'pendiente', 1);
INSERT INTO usuarios (nombre, email, password_hash, id_rol)
VALUES ('Operario Finca', 'operario@finca.cl', 'pendiente', 2);

COMMIT;
