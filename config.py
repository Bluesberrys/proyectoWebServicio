import os

# Configuración de la base de datos
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "generador_practicas")
}

# Configuración de la aplicación
APP_CONFIG = {
    "SECRET_KEY": os.environ.get("SECRET_KEY", "clave_secreta_desarrollo"),
    "JWT_SECRET_KEY": os.environ.get("JWT_SECRET_KEY", "clave_secreta_desarollo"),
    "DEBUG": os.environ.get("DEBUG", "True") == "True",
    "UPLOAD_FOLDER": os.environ.get("UPLOAD_FOLDER", "uploads"),
    "ALLOWED_EXTENSIONS": {'pdf', 'doc', 'docx', 'txt'},
    "MAX_CONTENT_LENGTH": 16 * 1024 * 1024  # 16 MB
}

# Configuración del modelo de ML
ML_CONFIG = {
    "MODEL_PATH": os.environ.get("MODEL_PATH", "modelo_practicas.h5"),
    "TOKENIZER_PATH": os.environ.get("TOKENIZER_PATH", "tokenizer.json"),
    "MIN_CONFIDENCE": float(os.environ.get("MIN_CONFIDENCE", "0.7"))
}

# Creación de la estructura SQL (script básico para referencia)
SQL_INIT_SCRIPT = """
CREATE TABLE IF NOT EXISTS usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    rol ENUM('administrador', 'profesor', 'estudiante') NOT NULL,
    password_hash VARCHAR(255),
    fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS materias (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    descripcion TEXT,
    activa BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS niveles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL,
    descripcion TEXT
);

CREATE TABLE IF NOT EXISTS conceptos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    descripcion TEXT,
    materia_id INT,
    FOREIGN KEY (materia_id) REFERENCES materias(id)
);

CREATE TABLE IF NOT EXISTS herramientas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    descripcion TEXT,
    url VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS practicas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    titulo VARCHAR(200) NOT NULL,
    materia_id INT,
    nivel_id INT,
    autor_id INT,
    objetivo TEXT NOT NULL,
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    fecha_entrega DATETIME NOT NULL,
    estado ENUM('pendiente', 'completado', 'cancelado') DEFAULT 'pendiente',
    contenido_generado JSON,
    concepto_id INT,
    herramienta_id INT,
    tiempo_estimado INT,
    FOREIGN KEY (materia_id) REFERENCES materias(id),
    FOREIGN KEY (nivel_id) REFERENCES niveles(id),
    FOREIGN KEY (autor_id) REFERENCES usuarios(id),
    FOREIGN KEY (concepto_id) REFERENCES conceptos(id),
    FOREIGN KEY (herramienta_id) REFERENCES herramientas(id)
);

CREATE TABLE IF NOT EXISTS versiones_practica (
    id INT AUTO_INCREMENT PRIMARY KEY,
    practica_id INT NOT NULL,
    contenido JSON NOT NULL,
    autor_id INT,
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    numero_version INT NOT NULL,
    cambios TEXT,
    FOREIGN KEY (practica_id) REFERENCES practicas(id),
    FOREIGN KEY (autor_id) REFERENCES usuarios(id)
);

CREATE TABLE IF NOT EXISTS grupos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    practica_id INT,
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    activo BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (practica_id) REFERENCES practicas(id)
);

CREATE TABLE IF NOT EXISTS grupo_miembros (
    id INT AUTO_INCREMENT PRIMARY KEY,
    grupo_id INT NOT NULL,
    usuario_id INT NOT NULL,
    rol ENUM('coordinador', 'miembro') DEFAULT 'miembro',
    FOREIGN KEY (grupo_id) REFERENCES grupos(id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);

CREATE TABLE IF NOT EXISTS entregas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    practica_id INT NOT NULL,
    estudiante_id INT NOT NULL,
    grupo_id INT,
    contenido TEXT,
    fecha_entrega DATETIME NOT NULL,
    estado ENUM('pendiente', 'revisada', 'reenviada') DEFAULT 'pendiente',
    calificacion FLOAT,
    comentarios TEXT,
    FOREIGN KEY (practica_id) REFERENCES practicas(id),
    FOREIGN KEY (estudiante_id) REFERENCES usuarios(id),
    FOREIGN KEY (grupo_id) REFERENCES grupos(id)
);

CREATE TABLE IF NOT EXISTS evaluaciones (
    id INT AUTO_INCREMENT PRIMARY KEY,
    practica_id INT NOT NULL,
    estudiante_id INT NOT NULL,
    evaluador_id INT,
    fecha_evaluacion DATETIME,
    estado ENUM('pendiente', 'completada') DEFAULT 'pendiente',
    calificacion FLOAT,
    comentarios TEXT,
    FOREIGN KEY (practica_id) REFERENCES practicas(id),
    FOREIGN KEY (estudiante_id) REFERENCES usuarios(id),
    FOREIGN KEY (evaluador_id) REFERENCES usuarios(id)
);

CREATE TABLE IF NOT EXISTS notificaciones (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    tipo VARCHAR(50) NOT NULL,
    mensaje TEXT NOT NULL,
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    leida BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);

CREATE TABLE IF NOT EXISTS actividades (
    id INT AUTO_INCREMENT PRIMARY KEY,
    descripcion TEXT NOT NULL,
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    usuario_id INT,
    tipo VARCHAR(50),
    recurso_id INT,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);

CREATE TABLE IF NOT EXISTS plantillas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    descripcion TEXT,
    contenido JSON NOT NULL,
    autor_id INT,
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    categoria VARCHAR(50),
    FOREIGN KEY (autor_id) REFERENCES usuarios(id)
);
"""
