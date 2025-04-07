-- Crear base de datos
CREATE DATABASE IF NOT EXISTS generador_practicas;

USE generador_practicas;

-- Tabla de usuarios
CREATE TABLE IF NOT EXISTS usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    rol ENUM('estudiante', 'profesor', 'admin') NOT NULL,
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    numero_cuenta INT(9) UNIQUE
);

-- Tabla de materias
CREATE TABLE IF NOT EXISTS materias (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    descripcion TEXT
);

-- Tabla de niveles
CREATE TABLE IF NOT EXISTS niveles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL,
    descripcion TEXT
);

-- Tabla de competencias
CREATE TABLE IF NOT EXISTS competencias (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    descripcion TEXT
);

-- Tabla de herramientas
CREATE TABLE IF NOT EXISTS herramientas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    descripcion TEXT,
    tipo VARCHAR(50)
);

-- Tabla de conceptos
CREATE TABLE IF NOT EXISTS conceptos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    descripcion TEXT,
    materia_id INT,
    FOREIGN KEY (materia_id) REFERENCES materias(id) ON DELETE CASCADE
);

-- Tabla de prácticas
CREATE TABLE IF NOT EXISTS practicas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    titulo VARCHAR(200) NOT NULL,
    materia_id INT NOT NULL,
    nivel_id INT NOT NULL,
    autor_id INT NOT NULL,
    concepto_id INT,
    herramienta_id INT,
    objetivo TEXT NOT NULL,
    introduccion TEXT,
    descripcion TEXT,
    fecha_entrega DATETIME NOT NULL,
    tiempo_estimado INT NOT NULL,
    estado ENUM('Pendiente','Completado','Cancelado') NOT NULL DEFAULT 'Pendiente',
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    uso_ia BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (materia_id) REFERENCES materias(id) ON DELETE CASCADE,
    FOREIGN KEY (nivel_id) REFERENCES niveles(id) ON DELETE CASCADE,
    FOREIGN KEY (autor_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    FOREIGN KEY (concepto_id) REFERENCES conceptos(id) ON DELETE SET NULL,
    FOREIGN KEY (herramienta_id) REFERENCES herramientas(id) ON DELETE SET NULL
);

-- Tabla de relación práctica-competencia
CREATE TABLE IF NOT EXISTS practica_competencia (
    id INT AUTO_INCREMENT PRIMARY KEY,
    practica_id INT NOT NULL,
    competencia_id INT NOT NULL,
    nivel INT NOT NULL,
    FOREIGN KEY (practica_id) REFERENCES practicas(id) ON DELETE CASCADE,
    FOREIGN KEY (competencia_id) REFERENCES competencias(id) ON DELETE CASCADE
);

-- Tabla de prerequisitos de práctica
CREATE TABLE IF NOT EXISTS practica_prerequisitos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    practica_id INT NOT NULL,
    competencia_id INT NOT NULL,
    nivel_requerido INT NOT NULL,
    FOREIGN KEY (practica_id) REFERENCES practicas(id) ON DELETE CASCADE,
    FOREIGN KEY (competencia_id) REFERENCES competencias(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS semestres (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE  -- Ejemplo: 'Semestre 1', 'Semestre 2', etc.
);

-- Tabla de grupos
CREATE TABLE IF NOT EXISTS grupos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,          -- Nombre del grupo (ej. A-1101)
    descripcion TEXT,                      -- Descripción del grupo
    materia_id INT NOT NULL,               -- ID de la materia (clave foránea)
    semestre_id INT NOT NULL,              -- ID del semestre (clave foránea)
    profesor_id INT NOT NULL,              -- ID del profesor (clave foránea)
    fecha_creacion DATETIME DEFAULT NOW(), -- Fecha de creación del grupo
    activo BOOLEAN DEFAULT TRUE,            -- Estado del grupo (activo/inactivo)
    FOREIGN KEY (materia_id) REFERENCES materias(id) ON DELETE CASCADE,
    FOREIGN KEY (semestre_id) REFERENCES semestres(id) ON DELETE CASCADE,
    FOREIGN KEY (profesor_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

-- Tabla de miembros de grupo
CREATE TABLE IF NOT EXISTS grupo_miembros (
    id INT AUTO_INCREMENT PRIMARY KEY,
    grupo_id INT NOT NULL,
    usuario_id INT NOT NULL,
    rol VARCHAR(50) NOT NULL,
    FOREIGN KEY (grupo_id) REFERENCES grupos(id) ON DELETE CASCADE,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

-- Tabla de evaluaciones
CREATE TABLE IF NOT EXISTS evaluaciones (
    id INT AUTO_INCREMENT PRIMARY KEY,
    practica_id INT NOT NULL,
    estudiante_id INT NOT NULL,
    evaluador_id INT NOT NULL,
    fecha_evaluacion DATETIME NOT NULL,
    estado ENUM('pendiente', 'en_proceso', 'completada', 'revisada', 'calificado') NOT NULL,
    calificacion DECIMAL(5,2),
    comentarios TEXT,
    uso_ia INT DEFAULT 0,
    FOREIGN KEY (practica_id) REFERENCES practicas(id) ON DELETE CASCADE,
    FOREIGN KEY (estudiante_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    FOREIGN KEY (evaluador_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

-- Tabla de entregas
CREATE TABLE IF NOT EXISTS entregas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    practica_id INT NOT NULL,
    estudiante_id INT NOT NULL,
    fecha_entrega DATETIME NOT NULL,
    estado ENUM('pendiente', 'revisada', 'retroalimentada', 'calificado') NOT NULL,
    archivos_url TEXT,
    contenido TEXT,
    calificacion DECIMAL(5,2),
    evaluacion_id INT,
    FOREIGN KEY (practica_id) REFERENCES practicas(id) ON DELETE CASCADE,
    FOREIGN KEY (estudiante_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    FOREIGN KEY (evaluacion_id) REFERENCES evaluaciones(id) ON DELETE SET NULL
);

-- Tabla de retroalimentación
CREATE TABLE IF NOT EXISTS retroalimentacion (
    id INT AUTO_INCREMENT PRIMARY KEY,
    entrega_id INT NOT NULL,
    profesor_id INT NOT NULL,
    comentario TEXT NOT NULL,
    aspecto VARCHAR(100) NOT NULL,
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (entrega_id) REFERENCES entregas(id) ON DELETE CASCADE,
    FOREIGN KEY (profesor_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

-- Tabla de rúbricas
CREATE TABLE IF NOT EXISTS rubricas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    practica_id INT NOT NULL,
    criterio VARCHAR(200) NOT NULL,
    descripcion TEXT NOT NULL,
    puntaje_maximo INT NOT NULL,
    FOREIGN KEY (practica_id) REFERENCES practicas(id) ON DELETE CASCADE
);

-- Tabla de niveles de rúbrica
CREATE TABLE IF NOT EXISTS rubrica_niveles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    rubrica_id INT NOT NULL,
    nivel INT NOT NULL,
    descripcion TEXT NOT NULL,
    puntaje INT NOT NULL,
    FOREIGN KEY (rubrica_id) REFERENCES rubricas(id) ON DELETE CASCADE
);

-- Tabla de recursos de práctica
CREATE TABLE IF NOT EXISTS recursos_practica (
    id INT AUTO_INCREMENT PRIMARY KEY,
    practica_id INT NOT NULL,
    tipo VARCHAR(50) NOT NULL,
    nombre VARCHAR(200) NOT NULL,
    url TEXT NOT NULL,
    descripcion TEXT,
    FOREIGN KEY (practica_id) REFERENCES practicas(id) ON DELETE CASCADE
);

-- Tabla de notificaciones
CREATE TABLE IF NOT EXISTS notificaciones (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    tipo VARCHAR(50) NOT NULL,
    mensaje TEXT NOT NULL,
    leida BOOLEAN DEFAULT FALSE,
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

-- Tabla de resultados de aprendizaje
CREATE TABLE IF NOT EXISTS resultados_aprendizaje (
    id INT AUTO_INCREMENT PRIMARY KEY,
    practica_id INT NOT NULL,
    competencia_id INT NOT NULL,
    nivel_logrado INT NOT NULL,
    evidencias TEXT NOT NULL,
    fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (practica_id) REFERENCES practicas(id) ON DELETE CASCADE,
    FOREIGN KEY (competencia_id) REFERENCES competencias(id) ON DELETE CASCADE
);

-- Crear la tabla contenido_generado
CREATE TABLE IF NOT EXISTS contenido_generado (
    id INT AUTO_INCREMENT PRIMARY KEY,
    practica_id INT NOT NULL,
    contenido JSON NOT NULL,
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (practica_id) REFERENCES practicas(id) ON DELETE CASCADE
);

-- Crear la tabla versiones
CREATE TABLE IF NOT EXISTS versiones (
    id INT AUTO_INCREMENT PRIMARY KEY,
    practica_id INT NOT NULL,
    contenido JSON NOT NULL,
    autor_id INT NOT NULL,
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    numero_version INT NOT NULL,
    cambios TEXT,
    FOREIGN KEY (practica_id) REFERENCES practicas(id) ON DELETE CASCADE,
    FOREIGN KEY (autor_id) REFERENCES usuarios(id) ON DELETE CASCADE
);


-- Crear la tabla tiempo_registrado
CREATE TABLE IF NOT EXISTS tiempo_registrado (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    tiempo FLOAT NOT NULL,
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

CREATE TABLE solicitudes_registro (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    rol_solicitado ENUM('administrador', 'profesor', 'estudiante') NOT NULL,
    estado ENUM('pendiente', 'aprobada', 'rechazada') DEFAULT 'pendiente',
    fecha_solicitud DATETIME DEFAULT CURRENT_TIMESTAMP
);
