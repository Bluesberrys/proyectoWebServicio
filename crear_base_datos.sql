-- Crear base de datos
CREATE DATABASE IF NOT EXISTS generador_practicas;

USE generador_practicas;

-- Tabla de usuarios
CREATE TABLE IF NOT EXISTS usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    passwd VARCHAR(255) NOT NULL,
    rol ENUM('estudiante', 'profesor', 'admin') NOT NULL,
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP
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
    FOREIGN KEY (materia_id) REFERENCES materias(id)
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
    fecha_entrega DATETIME NOT NULL,
    tiempo_estimado INT NOT NULL,
    estado ENUM('Pendiente','Completado','Cancelado') NOT NULL DEFAULT 'Pendiente',
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (materia_id) REFERENCES materias(id),
    FOREIGN KEY (nivel_id) REFERENCES niveles(id),
    FOREIGN KEY (autor_id) REFERENCES usuarios(id),
    FOREIGN KEY (concepto_id) REFERENCES conceptos(id),
    FOREIGN KEY (herramienta_id) REFERENCES herramientas(id)
);

-- Tabla de relación práctica-competencia
CREATE TABLE IF NOT EXISTS practica_competencia (
    id INT AUTO_INCREMENT PRIMARY KEY,
    practica_id INT NOT NULL,
    competencia_id INT NOT NULL,
    nivel INT NOT NULL,
    FOREIGN KEY (practica_id) REFERENCES practicas(id),
    FOREIGN KEY (competencia_id) REFERENCES competencias(id)
);

-- Tabla de prerequisitos de práctica
CREATE TABLE IF NOT EXISTS practica_prerequisitos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    practica_id INT NOT NULL,
    competencia_id INT NOT NULL,
    nivel_requerido INT NOT NULL,
    FOREIGN KEY (practica_id) REFERENCES practicas(id),
    FOREIGN KEY (competencia_id) REFERENCES competencias(id)
);

-- Tabla de grupos
CREATE TABLE IF NOT EXISTS grupos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    descripcion TEXT,
    practica_id INT,
    FOREIGN KEY (practica_id) REFERENCES practicas(id)
);

-- Tabla de miembros de grupo
CREATE TABLE IF NOT EXISTS grupo_miembros (
    id INT AUTO_INCREMENT PRIMARY KEY,
    grupo_id INT NOT NULL,
    usuario_id INT NOT NULL,
    rol VARCHAR(50) NOT NULL,
    FOREIGN KEY (grupo_id) REFERENCES grupos(id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);

-- Tabla de entregas
CREATE TABLE IF NOT EXISTS entregas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    practica_id INT NOT NULL,
    estudiante_id INT NOT NULL,
    fecha_entrega DATETIME NOT NULL,
    estado ENUM('pendiente', 'revisada', 'retroalimentada') NOT NULL,
    archivos_url TEXT,
    calificacion DECIMAL(5,2),
    FOREIGN KEY (practica_id) REFERENCES practicas(id),
    FOREIGN KEY (estudiante_id) REFERENCES usuarios(id)
);

-- Tabla de retroalimentación
CREATE TABLE IF NOT EXISTS retroalimentacion (
    id INT AUTO_INCREMENT PRIMARY KEY,
    entrega_id INT NOT NULL,
    profesor_id INT NOT NULL,
    comentario TEXT NOT NULL,
    aspecto VARCHAR(100) NOT NULL,
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (entrega_id) REFERENCES entregas(id),
    FOREIGN KEY (profesor_id) REFERENCES usuarios(id)
);

-- Tabla de rúbricas
CREATE TABLE IF NOT EXISTS rubricas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    practica_id INT NOT NULL,
    criterio VARCHAR(200) NOT NULL,
    descripcion TEXT NOT NULL,
    puntaje_maximo INT NOT NULL,
    FOREIGN KEY (practica_id) REFERENCES practicas(id)
);

-- Tabla de niveles de rúbrica
CREATE TABLE IF NOT EXISTS rubrica_niveles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    rubrica_id INT NOT NULL,
    nivel INT NOT NULL,
    descripcion TEXT NOT NULL,
    puntaje INT NOT NULL,
    FOREIGN KEY (rubrica_id) REFERENCES rubricas(id)
);

-- Tabla de recursos de práctica
CREATE TABLE IF NOT EXISTS recursos_practica (
    id INT AUTO_INCREMENT PRIMARY KEY,
    practica_id INT NOT NULL,
    tipo VARCHAR(50) NOT NULL,
    nombre VARCHAR(200) NOT NULL,
    url TEXT NOT NULL,
    descripcion TEXT,
    FOREIGN KEY (practica_id) REFERENCES practicas(id)
);

-- Tabla de notificaciones
CREATE TABLE IF NOT EXISTS notificaciones (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    tipo VARCHAR(50) NOT NULL,
    mensaje TEXT NOT NULL,
    leida BOOLEAN DEFAULT FALSE,
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);

-- Tabla de resultados de aprendizaje
CREATE TABLE IF NOT EXISTS resultados_aprendizaje (
    id INT AUTO_INCREMENT PRIMARY KEY,
    practica_id INT NOT NULL,
    competencia_id INT NOT NULL,
    nivel_logrado INT NOT NULL,
    evidencias TEXT NOT NULL,
    fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (practica_id) REFERENCES practicas(id),
    FOREIGN KEY (competencia_id) REFERENCES competencias(id)
);

-- Tabla de evaluaciones
CREATE TABLE IF NOT EXISTS evaluaciones (
    id INT AUTO_INCREMENT PRIMARY KEY,
    practica_id INT NOT NULL,
    estudiante_id INT NOT NULL,
    evaluador_id INT NOT NULL,
    fecha_evaluacion DATETIME NOT NULL,
    estado ENUM('pendiente', 'en_proceso', 'completada', 'revisada') NOT NULL,
    calificacion DECIMAL(5,2),
    comentarios TEXT,
    FOREIGN KEY (practica_id) REFERENCES practicas(id),
    FOREIGN KEY (estudiante_id) REFERENCES usuarios(id),
    FOREIGN KEY (evaluador_id) REFERENCES usuarios(id)
);


-- Insertar usuarios de ejemplo
INSERT INTO usuarios (nombre, email, passwd, rol) VALUES
('Juan Pérez', 'juan@universidad.edu', 'hash123', 'profesor'),
('María García', 'maria@universidad.edu', 'hash456', 'estudiante'),
('Admin Sistema', 'admin@universidad.edu', 'hash789', 'admin'),
('Urban', 'udullaghan0@webeden.co.uk', 'zO4@V<fg\vrqZNq', 'estudiante'),
('Melantha', 'mpetrelli1@icq.com', 'hJ9={pfZq*>U9ir', 'estudiante'),
('Felicity', 'fmerrilees2@unicef.org', 'iV8=,ykM2O_I#z', 'estudiante'),
('Barbee', 'belfes3@wunderground.com', 'wZ8,fkGk', 'profesor'),
('Trstram', 'tdeavall4@irs.gov', 'qG3*q~{Qz=S7', 'profesor'),
('Calley', 'cherrema5@hubpages.com', 'xK6`CG#PW', 'estudiante'),
('Nani', 'nzeale6@epa.gov', 'dW6=Q2kZ0Xka', 'estudiante'),
('Launce', 'lkitchenman7@hugedomains.com', 'aB9_Zw5y!f"A)pV', 'estudiante'),
('Lebbie', 'lsolley8@oracle.com', 'iA7>%Sn&u?', 'profesor'),
('Tara', 'thalpeine9@theglobeandmail.com', 'hZ6)Q''Qi?bE*4Tp', 'profesor');


-- Insertar materias
INSERT INTO materias (nombre, descripcion) VALUES
('Base de datos', 'Fundamentos y aplicaciones de bases de datos'),
('Programación', 'Programación y desarrollo de software'),
('Machine Learning', 'Aprendizaje automático y análisis de datos'),
('Seguridad Informática', 'Seguridad de sistemas y redes');

-- Insertar niveles
INSERT INTO niveles (nombre, descripcion) VALUES
('Básico', 'Nivel fundamental de conocimientos'),
('Intermedio', 'Nivel medio de conocimientos'),
('Avanzado', 'Nivel experto de conocimientos');

-- Insertar competencias
INSERT INTO competencias (nombre, descripcion) VALUES
('Diseño de BD', 'Capacidad para diseñar bases de datos eficientes'),
('Optimización', 'Habilidad para optimizar consultas y estructuras'),
('Programación SQL', 'Dominio de SQL y procedimientos almacenados'),
('Seguridad', 'Implementación de medidas de seguridad en BD');

-- Insertar herramientas
INSERT INTO herramientas (nombre, descripcion, tipo) VALUES
('MySQL', 'Sistema de gestión de bases de datos relacionales', 'DBMS'),
('PostgreSQL', 'Sistema de BD relacional avanzado', 'DBMS'),
('MongoDB', 'Base de datos NoSQL', 'NoSQL'),
('DBeaver', 'Cliente universal de bases de datos', 'Cliente');

-- Completar conceptos para todas las materias
-- Base de datos (continuación)
INSERT INTO conceptos (materia_id, nombre, descripcion) VALUES
(1, 'Bases de datos NoSQL', 'Sistemas de bases de datos no relacionales'),
(1, 'Seguridad en BD', 'Implementación de medidas de seguridad'),
-- Programación
(2, 'Estructuras de datos', 'Organización y manipulación de datos'),
(2, 'Algoritmos', 'Diseño y análisis de algoritmos'),
(2, 'POO', 'Programación Orientada a Objetos'),
(2, 'Patrones de diseño', 'Soluciones comunes a problemas de diseño'),
-- Machine Learning
(3, 'Regresión', 'Modelos de regresión y predicción'),
(3, 'Clasificación', 'Algoritmos de clasificación'),
(3, 'Clustering', 'Agrupamiento de datos'),
(3, 'Redes neuronales', 'Deep learning y redes neuronales'),
-- Seguridad Informática
(4, 'Criptografía', 'Técnicas de cifrado y seguridad'),
(4, 'Seguridad en redes', 'Protección de redes y comunicaciones'),
(4, 'Ethical Hacking', 'Pruebas de penetración'),
(4, 'Forense digital', 'Análisis forense de sistemas');

-- Insertar una práctica de ejemplo
INSERT INTO practicas (titulo, materia_id, nivel_id, autor_id, concepto_id, herramienta_id, objetivo, fecha_entrega, tiempo_estimado, estado) VALUES
('Diseño de Base de Datos E-commerce', 1, 2, 1, 1, 1, 'Diseñar una base de datos normalizada para un sistema de comercio electrónico', 
 DATE_ADD(CURRENT_TIMESTAMP, INTERVAL 14 DAY), 10, 'Pendiente');

-- Insertar un grupo de ejemplo
INSERT INTO grupos (nombre, descripcion, practica_id) VALUES
('Grupo 1', 'Grupo de práctica de bases de datos', 1);


-- Insertar una rúbrica de ejemplo
INSERT INTO rubricas (practica_id, criterio, descripcion, puntaje_maximo) VALUES
(1, 'Normalización', 'Nivel de normalización de la base de datos', 20),
(1, 'Diagrama ER', 'Calidad del diagrama entidad-relación', 20),
(1, 'Implementación', 'Correcta implementación en SQL', 30),
(1, 'Documentación', 'Calidad de la documentación', 30);

-- Insertar recursos de ejemplo
INSERT INTO recursos_practica (practica_id, tipo, nombre, url, descripcion) VALUES
(1, 'documento', 'Guía de normalización', 'https://ejemplo.com/guia', 'Guía detallada del proceso de normalización'),
(1, 'video', 'Tutorial MySQL', 'https://ejemplo.com/video', 'Video tutorial de implementación en MySQL');