from datetime import datetime, timedelta
import json
import logging
from typing import Optional, List, Dict, Any, Tuple
import mysql.connector
from mysql.connector import Error
from dataclasses import dataclass
import hashlib
import secrets
from enum import Enum
from collections import defaultdict
import asyncio
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from cachetools import TTLCache

# Declaración de enums y dataclasses
class EstadoPractica(Enum):
    PENDIENTE = "pendiente"
    COMPLETADO = "completado"
    CANCELADO = "cancelado"

@dataclass
class Practica:
    id: Optional[int]
    titulo: str
    materia_id: int
    nombre_materia: Optional[str]
    nivel_id: int
    autor_id: int
    objetivo: str
    fecha_entrega: datetime
    estado: str
    concepto_id: Optional[int]
    herramienta_id: Optional[int]
    tiempo_estimado: int

@dataclass
class Materia:
    id: int
    nombre: str
    descripcion: Optional[str]

@dataclass
class Nivel:
    id: int
    nombre: str
    descripcion: Optional[str]

@dataclass
class Notificacion:
    usuario_id: int
    tipo: str
    mensaje: str
    fecha_creacion: datetime

@dataclass
class Plantilla:
    nombre: str
    descripcion: str
    contenido: dict
    autor_id: int
    fecha_creacion: datetime
    categoria: str

@dataclass
class Version:
    id: int
    practica_id: int
    contenido: dict
    autor_id: int
    fecha_creacion: datetime
    numero_version: int
    cambios: str

@dataclass
class Grupo:
    id: Optional[int]
    nombre: str
    practica_id: int
    fecha_creacion: datetime
    activo: bool

@dataclass
class Entrega:
    id: Optional[int]
    practica_id: int
    estudiante_id: int
    grupo_id: Optional[int]
    contenido: str
    fecha_entrega: datetime
    estado: str
    calificacion: Optional[float]
    comentarios: Optional[str]

@dataclass
class Usuario:
    id: Optional[int]
    nombre: str
    email: str
    rol: str
    passwd: Optional[str] = None

@dataclass
class Concepto:
    id: int
    nombre: str
    descripcion: Optional[str]

@dataclass
class Herramienta:
    id: int
    nombre: str
    descripcion: Optional[str]
    url: Optional[str]

class GeneradorPracticasExtendido:
    def __init__(self, config: Dict[str, str]):
        self.conn = mysql.connector.connect(**config)
        self.connection = mysql.connector.connect(**config)
        self.cursor = self.connection.cursor(dictionary=True)
        self.cache = TTLCache(maxsize=100, ttl=300)  # Caché con TTL
        self.executor = ThreadPoolExecutor()
        
        # Configuración de logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            filename='generador_practicas.log'
        )
        self.logger = logging.getLogger('GeneradorPracticas')

    def _calcular_similitud(self, texto1: str, texto2: str) -> float:
        """Calcula la similitud entre dos textos usando SequenceMatcher"""
        return SequenceMatcher(None, texto1, texto2).ratio()

    def crear_notificacion(self, notificacion: Notificacion) -> int:
        """Crea una nueva notificación en la base de datos"""
        try:
            query = """
                INSERT INTO notificaciones (usuario_id, tipo, mensaje, fecha_creacion)
                VALUES (%s, %s, %s, %s)
            """
            self.cursor.execute(query, (
                notificacion.usuario_id,
                notificacion.tipo,
                notificacion.mensaje,
                notificacion.fecha_creacion
            ))
            self.connection.commit()
            return self.cursor.lastrowid
        except Error as e:
            self.connection.rollback()
            self.logger.error(f"Error al crear notificación: {str(e)}")
            raise

    # MÉTODOS PARA EL DASHBOARD
    def obtener_conceptos(self) -> List[Concepto]:
        """Obtiene todos los conceptos"""
        try:
            query = "SELECT * FROM conceptos ORDER BY nombre ASC"
            self.cursor.execute(query)
            results = self.cursor.fetchall()
            
            conceptos = []
            for result in results:
                concepto = Concepto(
                    id=result['id'],
                    nombre=result['nombre'],
                    descripcion=result['descripcion']
                )
                conceptos.append(concepto)
            return conceptos
        except Error as e:
            self.logger.error(f"Error al obtener conceptos: {str(e)}")
            return []

    def eliminar_practica(self, practica_id: int) -> bool:
        """Elimina una práctica de la base de datos"""
        try:
            query = "DELETE FROM practicas WHERE id = %s"
            self.cursor.execute(query, (practica_id,))
            self.connection.commit()
            return self.cursor.rowcount > 0
        except Error as e:
            self.connection.rollback()
            self.logger.error(f"Error al eliminar práctica: {str(e)}")
            return False

    def obtener_herramientas(self) -> List[Herramienta]:
        """Obtiene todas las herramientas"""
        try:
            query = "SELECT * FROM herramientas ORDER BY nombre ASC"
            self.cursor.execute(query)
            results = self.cursor.fetchall()

            herramientas = []
            for result in results:
                herramienta = Herramienta(
                    id=result['id'],
                    nombre=result['nombre'],
                    descripcion=result.get('descripcion'),
                    url=result.get('url')
                )
                herramientas.append(herramienta)
            return herramientas
        except Error as e:
            self.logger.error(f"Error al obtener herramientas: {str(e)}")
            return []
        
    def crear_evaluaciones_para_practica(self, practica_id: int) -> bool:
        """Crea evaluaciones para una práctica"""
        try:
            # Suponiendo que tienes una tabla de estudiantes y una tabla de evaluaciones
            query_estudiantes = "SELECT id FROM estudiantes"
            self.cursor.execute(query_estudiantes)
            estudiantes = self.cursor.fetchall()

            for estudiante in estudiantes:
                query_evaluacion = """
                    INSERT INTO evaluaciones (practica_id, estudiante_id, fecha_evaluacion, estado)
                    VALUES (%s, %s, %s, %s)
                """
                self.cursor.execute(query_evaluacion, (
                    practica_id,
                    estudiante['id'],
                    datetime.now(),
                    'pendiente'
                ))

            self.connection.commit()
            return True
        except Error as e:
            self.connection.rollback()
            self.logger.error(f"Error al crear evaluaciones para la práctica: {str(e)}")
            return False

    def guardar_contenido_generado(self, practica_id: int, contenido: dict) -> bool:
        """Guarda el contenido generado por IA para una práctica"""
        try:
            query = """
                INSERT INTO contenido_generado (practica_id, contenido, fecha_creacion)
                VALUES (%s, %s, %s)
            """
            self.cursor.execute(query, (
                practica_id,
                json.dumps(contenido),
                datetime.now()
            ))
            self.connection.commit()
            return True
        except Error as e:
            self.connection.rollback()
            self.logger.error(f"Error al guardar contenido generado: {str(e)}")
            return False
    
    def obtener_contenido_generado(self, practica_id: int) -> Optional[dict]:
        """Obtiene el contenido generado por IA para una práctica"""
        try:
            query = "SELECT contenido FROM contenido_generado WHERE practica_id = %s"
            self.cursor.execute(query, (practica_id,))
            result = self.cursor.fetchone()
            if result:
                return json.loads(result['contenido'])
            return None
        except Error as e:
            self.logger.error(f"Error al obtener contenido generado: {str(e)}")
            return None

    def obtener_actividades_recientes(self) -> List[Dict[str, Any]]:
        """Obtiene las actividades recientes para el dashboard"""
        try:
            query = """
                SELECT descripcion, fecha, usuario_id, tipo, recurso_id
                FROM actividades
                ORDER BY fecha DESC
                LIMIT 10
            """
            self.cursor.execute(query)
            actividades = self.cursor.fetchall()
            return actividades
        except Error as e:
            self.logger.error(f"Error al obtener actividades recientes: {str(e)}")
            return []
    
    def obtener_niveles(self) -> List[Nivel]:
        """Obtiene todos los niveles"""
        try:
            query = "SELECT * FROM niveles ORDER BY nombre ASC"
            self.cursor.execute(query)
            results = self.cursor.fetchall()
            
            niveles = []
            for result in results:
                nivel = Nivel(
                    id=result['id'],
                    nombre=result['nombre'],
                    descripcion=result['descripcion']
                )
                niveles.append(nivel)
            return niveles
        except Error as e:
            self.logger.error(f"Error al obtener niveles: {str(e)}")
            return []
        
    def obtener_usuarios(self) -> List[Usuario]:
        """Obtiene todos los usuarios"""
        try:
            query = "SELECT * FROM usuarios ORDER BY rol DESC"
            self.cursor.execute(query)
            results = self.cursor.fetchall()
            
            usuarios = []
            for result in results:
                usuario = Usuario(
                    id=result['id'],
                    nombre=result['nombre'],
                    email=result['email'],
                    rol=result['rol']
                )
                usuarios.append(usuario)
            return usuarios
        except Error as e:
            self.logger.error(f"Error al obtener usuarios: {str(e)}")
            return []
        
    def obtetener_usuarios_autorizados(self) -> List[Usuario]:
        """Obtiene todos los usuarios autorizados"""
        try:
            query = "SELECT * FROM usuarios WHERE NOT rol = 'estudiante' ORDER BY nombre ASC"
            self.cursor.execute(query)
            results = self.cursor.fetchall()
            
            usuarios_autorizados = []
            for result in results:
                usuario = Usuario(
                    id=result['id'],
                    nombre=result['nombre'],
                    email=result['email'],
                    rol=result['rol']
                )
                usuarios_autorizados.append(usuario)
            return usuarios_autorizados
        except Error as e:
            self.logger.error(f"Error al obtener usuarios autorizados: {str(e)}")
            return []

    def obtener_evaluaciones(self) -> List[Dict[str, Any]]:
        """Obtiene todas las evaluaciones"""
        try:
            query = """
                SELECT e.id, e.practica_id, e.estudiante_id, e.evaluador_id, e.fecha_evaluacion, 
                       e.estado, e.calificacion, e.comentarios, p.titulo AS practica_titulo, 
                       u.nombre AS estudiante_nombre, ev.nombre AS evaluador_nombre
                FROM evaluaciones e
                JOIN practicas p ON e.practica_id = p.id
                JOIN usuarios u ON e.estudiante_id = u.id
                LEFT JOIN usuarios ev ON e.evaluador_id = ev.id
                ORDER BY e.fecha_evaluacion DESC
            """
            self.cursor.execute(query)
            evaluaciones = self.cursor.fetchall()
            return evaluaciones
        except Error as e:
            self.logger.error(f"Error al obtener evaluaciones: {str(e)}")
            return []

    def obtener_materias(self) -> List[Materia]:
        """Obtiene todas las materias"""
        try:
            query = "SELECT * FROM materias ORDER BY nombre ASC"
            self.cursor.execute(query)
            results = self.cursor.fetchall()
            
            materias = []
            for result in results:
                materia = Materia(
                    id=result['id'],
                    nombre=result['nombre'],
                    descripcion=result['descripcion']
                )
                materias.append(materia)
            return materias
        except Error as e:
            self.logger.error(f"Error al obtener materias: {str(e)}")
            return []

    def obtener_practicas(self) -> List[Practica]:
        """Obtiene todas las prácticas"""
        try:
            query = """
                SELECT practicas.*, materias.nombre 
                FROM practicas 
                JOIN materias ON practicas.materia_id = materias.id 
                ORDER BY fecha_entrega DESC"""
            self.cursor.execute(query)
            results = self.cursor.fetchall()
            
            practicas = []
            for result in results:
                practica = Practica(
                    id=result['id'],
                    titulo=result['titulo'],
                    materia_id=result['materia_id'],
                    nombre_materia=result['nombre'],
                    nivel_id=result['nivel_id'],
                    autor_id=result['autor_id'],
                    objetivo=result['objetivo'],
                    fecha_entrega=result['fecha_entrega'],
                    estado=result['estado'],
                    concepto_id=result['concepto_id'],
                    herramienta_id=result['herramienta_id'],
                    tiempo_estimado=result['tiempo_estimado']
                )
                practicas.append(practica)
            return practicas
        except Error as e:
            self.logger.error(f"Error al obtener prácticas: {str(e)}")
            return []
        
    def obtener_practicas_activas(self) -> int:
        try:
            self.cursor.execute("SELECT COUNT(*) AS count FROM practicas WHERE estado = 'pendiente'")
            result = self.cursor.fetchone()
            return result['count']
        except Error as e:
            self.logger.error(f"Error al obtener prácticas activas: {str(e)}")
            return 0

    def obtener_entregas_pendientes(self) -> int:
        try:
            self.cursor.execute("SELECT COUNT(*) AS count FROM entregas WHERE estado = 'pendiente'")
            result = self.cursor.fetchone()
            return result['count']
        except Error as e:
            self.logger.error(f"Error al obtener entregas pendientes: {str(e)}")
            return 0

    def obtener_usuarios_registrados(self) -> int:
        try:
            self.cursor.execute("SELECT COUNT(*) AS count FROM usuarios")
            result = self.cursor.fetchone()
            return result['count']
        except Error as e:
            self.logger.error(f"Error al obtener usuarios registrados: {str(e)}")
            return 0

    def obtener_estadisticas_dashboard(self) -> Dict[str, Any]:
        """Obtiene todas las estadísticas necesarias para el dashboard"""
        try:
            cache_key = 'dashboard_stats'
            if cache_key in self.cache:
                return self.cache[cache_key]
                
            stats = {
                'practicas_activas': self.obtener_practicas_activas(),
                'entregas_pendientes': self.obtener_entregas_pendientes(),
                'usuarios_registrados': self.obtener_usuarios_registrados(),
                'materias_populares': self.obtener_materias_populares(),
                'entrega_por_estado': self.obtener_distribucion_entregas_por_estado()
            }
            
            self.cache[cache_key] = stats
            return stats
        except Error as e:
            self.logger.error(f"Error al obtener estadísticas del dashboard: {str(e)}")
            return {}
    
    def obtener_materias_populares(self, limite: int = 5) -> List[Dict[str, Any]]:
        """Obtiene las materias con más prácticas creadas"""
        try:
            query = """
                SELECT m.id, m.nombre, COUNT(p.id) AS total_practicas
                FROM materias m
                JOIN practicas p ON m.id = p.materia_id
                GROUP BY m.id, m.nombre
                ORDER BY total_practicas DESC
                LIMIT %s
            """
            self.cursor.execute(query, (limite,))
            return self.cursor.fetchall()
        except Error as e:
            self.logger.error(f"Error al obtener materias populares: {str(e)}")
            return []
    
    def obtener_distribucion_entregas_por_estado(self) -> Dict[str, int]:
        """Obtiene la distribución de entregas por estado"""
        try:
            query = """
                SELECT estado, COUNT(*) as cantidad
                FROM entregas
                GROUP BY estado
            """
            self.cursor.execute(query)
            result = self.cursor.fetchall()
            return {row['estado']: row['cantidad'] for row in result}
        except Error as e:
            self.logger.error(f"Error al obtener distribución de entregas: {str(e)}")
            return {}
    
    # MÉTODOS PARA PRÁCTICAS
    async def crear_practica_async(self, practica: Practica) -> Optional[int]:
        """Crea una nueva práctica de forma asíncrona"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.crear_practica, practica)
    
    def crear_practica(self, practica: Practica) -> Optional[int]:
        """Crea una nueva práctica en la base de datos"""
        try:
            query = """
                INSERT INTO practicas 
                (titulo, materia_id, nivel_id, autor_id, objetivo, fecha_entrega, 
                estado, concepto_id, herramienta_id, tiempo_estimado)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            self.cursor.execute(query, (
                practica.titulo,
                practica.materia_id,
                practica.nivel_id,
                practica.autor_id,
                practica.objetivo,
                practica.fecha_entrega,
                practica.estado,
                practica.concepto_id,
                practica.herramienta_id,
                practica.tiempo_estimado
            ))
            self.connection.commit()
            
            practica_id = self.cursor.lastrowid
            
            # Crear una notificación para el profesor
            notificacion = Notificacion(
                usuario_id=practica.autor_id,
                tipo="nueva_practica",
                mensaje=f"Nueva práctica '{practica.titulo}' creada con éxito",
                fecha_creacion=datetime.now()
            )
            self.crear_notificacion(notificacion)
            
            return practica_id
        except Error as e:
            self.connection.rollback()
            self.logger.error(f"Error al crear práctica: {str(e)}")
            return None
    
    def actualizar_practica(self, practica: Practica) -> bool:
        """Actualiza una práctica existente"""
        try:
            query = """
                UPDATE practicas 
                SET titulo = %s, materia_id = %s, nivel_id = %s, objetivo = %s,
                fecha_entrega = %s, estado = %s, concepto_id = %s, 
                herramienta_id = %s, tiempo_estimado = %s
                WHERE id = %s
            """
            self.cursor.execute(query, (
                practica.titulo,
                practica.materia_id,
                practica.nivel_id,
                practica.objetivo,
                practica.fecha_entrega,
                practica.estado,
                practica.concepto_id,
                practica.herramienta_id,
                practica.tiempo_estimado,
                practica.id
            ))
            self.connection.commit()
            return self.cursor.rowcount > 0
        except Error as e:
            self.connection.rollback()
            self.logger.error(f"Error al actualizar práctica: {str(e)}")
            return False
    
    def obtener_practica_por_id(self, practica_id: int) -> Optional[Practica]:
        """Obtiene una práctica por su ID"""
        try:
            cache_key = f'practica_{practica_id}'
            if cache_key in self.cache:
                return self.cache[cache_key]
                
            query = f"""
                SELECT practicas.*, materias.nombre 
                FROM practicas 
                JOIN materias ON practicas.materia_id = materias.id 
                WHERE practicas.id = {practica_id}"""
            self.cursor.execute(query)
            result = self.cursor.fetchone()
            
            if result:
                practica = Practica(
                    id=result['id'],
                    titulo=result['titulo'],
                    materia_id=result['materia_id'],
                    nombre_materia=result['nombre'],
                    nivel_id=result['nivel_id'],
                    autor_id=result['autor_id'],
                    objetivo=result['objetivo'],
                    fecha_entrega=result['fecha_entrega'],
                    estado=result['estado'],
                    concepto_id=result['concepto_id'],
                    herramienta_id=result['herramienta_id'],
                    tiempo_estimado=result['tiempo_estimado']
                )
                self.cache[cache_key] = practica
                return practica
            return None
        except Error as e:
            self.logger.error(f"Error al obtener práctica: {str(e)}")
            return None
    
    def obtener_practicas_por_autor(self, autor_id: int) -> List[Practica]:
        """Obtiene todas las prácticas creadas por un autor"""
        try:
            query = "SELECT * FROM practicas WHERE autor_id = %s ORDER BY fecha_entrega DESC"
            self.cursor.execute(query, (autor_id,))
            results = self.cursor.fetchall()
            
            practicas = []
            for result in results:
                practica = Practica(
                    id=result['id'],
                    titulo=result['titulo'],
                    materia_id=result['materia_id'],
                    nivel_id=result['nivel_id'],
                    autor_id=result['autor_id'],
                    objetivo=result['objetivo'],
                    fecha_entrega=result['fecha_entrega'],
                    estado=result['estado'],
                    concepto_id=result['concepto_id'],
                    herramienta_id=result['herramienta_id'],
                    tiempo_estimado=result['tiempo_estimado']
                )
                practicas.append(practica)
            return practicas
        except Error as e:
            self.logger.error(f"Error al obtener prácticas por autor: {str(e)}")
            return []
    
    # MÉTODOS PARA GRUPOS Y ENTREGAS
    def crear_grupo(self, grupo: Grupo) -> Optional[int]:
        """Crea un nuevo grupo para una práctica"""
        try:
            query = """
                INSERT INTO grupos (nombre, practica_id, fecha_creacion, activo)
                VALUES (%s, %s, %s, %s)
            """
            self.cursor.execute(query, (
                grupo.nombre,
                grupo.practica_id,
                grupo.fecha_creacion,
                grupo.activo
            ))
            self.connection.commit()
            return self.cursor.lastrowid
        except Error as e:
            self.connection.rollback()
            self.logger.error(f"Error al crear grupo: {str(e)}")
            return None
    
    def registrar_entrega(self, entrega: Entrega) -> Optional[int]:
        """Registra una nueva entrega de práctica"""
        try:
            query = """
                INSERT INTO entregas 
                (practica_id, estudiante_id, grupo_id, contenido, fecha_entrega, estado)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            self.cursor.execute(query, (
                entrega.practica_id,
                entrega.estudiante_id,
                entrega.grupo_id,
                entrega.contenido,
                entrega.fecha_entrega,
                entrega.estado
            ))
            self.connection.commit()
            
            entrega_id = self.cursor.lastrowid
            
            # Obtener información de la práctica para la notificación
            practica = self.obtener_practica_por_id(entrega.practica_id)
            if practica:
                # Notificar al profesor
                notificacion = Notificacion(
                    usuario_id=practica.autor_id,
                    tipo="nueva_entrega",
                    mensaje=f"Nueva entrega para la práctica '{practica.titulo}'",
                    fecha_creacion=datetime.now()
                )
                self.crear_notificacion(notificacion)
            
            return entrega_id
        except Error as e:
            self.connection.rollback()
            self.logger.error(f"Error al registrar entrega: {str(e)}")
            return None
    
    def calificar_entrega(self, entrega_id: int, calificacion: float, comentarios: str) -> bool:
        """Califica una entrega de práctica"""
        try:
            query = """
                UPDATE entregas 
                SET calificacion = %s, comentarios = %s, estado = 'calificado'
                WHERE id = %s
            """
            self.cursor.execute(query, (calificacion, comentarios, entrega_id))
            self.connection.commit()
            
            # Obtener información de la entrega para la notificación
            self.cursor.execute("SELECT estudiante_id, practica_id FROM entregas WHERE id = %s", (entrega_id,))
            entrega_info = self.cursor.fetchone()
            
            if entrega_info:
                # Obtener título de la práctica
                practica = self.obtener_practica_por_id(entrega_info['practica_id'])
                if practica:
                    # Notificar al estudiante
                    notificacion = Notificacion(
                        usuario_id=entrega_info['estudiante_id'],
                        tipo="entrega_calificada",
                        mensaje=f"Tu entrega para '{practica.titulo}' ha sido calificada",
                        fecha_creacion=datetime.now()
                    )
                    self.crear_notificacion(notificacion)
            
            return self.cursor.rowcount > 0
        except Error as e:
            self.connection.rollback()
            self.logger.error(f"Error al calificar entrega: {str(e)}")
            return False
    
    # MÉTODOS PARA PLANTILLAS Y VERSIONES
    def guardar_plantilla(self, plantilla: Plantilla) -> Optional[int]:
        """Guarda una nueva plantilla de práctica"""
        try:
            query = """
                INSERT INTO plantillas 
                (nombre, descripcion, contenido, autor_id, fecha_creacion, categoria)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            self.cursor.execute(query, (
                plantilla.nombre,
                plantilla.descripcion,
                json.dumps(plantilla.contenido),
                plantilla.autor_id,
                plantilla.fecha_creacion,
                plantilla.categoria
            ))
            self.connection.commit()
            return self.cursor.lastrowid
        except Error as e:
            self.connection.rollback()
            self.logger.error(f"Error al guardar plantilla: {str(e)}")
            return None
    
    def crear_version(self, version: Version) -> Optional[int]:
        """Crea una nueva versión de una práctica"""
        try:
            query = """
                INSERT INTO versiones 
                (practica_id, contenido, autor_id, fecha_creacion, numero_version, cambios)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            self.cursor.execute(query, (
                version.practica_id,
                json.dumps(version.contenido),
                version.autor_id,
                version.fecha_creacion,
                version.numero_version,
                version.cambios
            ))
            self.connection.commit()
            return self.cursor.lastrowid
        except Error as e:
            self.connection.rollback()
            self.logger.error(f"Error al crear versión: {str(e)}")
            return None
    
    def obtener_versiones_practica(self, practica_id: int) -> List[Version]:
        """Obtiene todas las versiones de una práctica"""
        try:
            query = """
                SELECT * FROM versiones 
                WHERE practica_id = %s
                ORDER BY numero_version DESC
            """
            self.cursor.execute(query, (practica_id,))
            results = self.cursor.fetchall()
            
            versiones = []
            for result in results:
                version = Version(
                    id=result['id'],
                    practica_id=result['practica_id'],
                    contenido=json.loads(result['contenido']),
                    autor_id=result['autor_id'],
                    fecha_creacion=result['fecha_creacion'],
                    numero_version=result['numero_version'],
                    cambios=result['cambios']
                )
                versiones.append(version)
            return versiones
        except Error as e:
            self.logger.error(f"Error al obtener versiones: {str(e)}")
            return []
    
    # Métodos de limpieza y cierre
    def limpiar_cache(self):
        """Limpia la caché de objetos"""
        self.cache.clear()
    
    def cerrar_conexion(self):
        if self.cursor:
            try:
                self.cursor.close()
            except ReferenceError:
                pass
        if self.conn:
            try:
                self.conn.close()
            except ReferenceError:
                pass

    def __del__(self):
        self.cerrar_conexion()
    
    def autenticar_usuario(self, email, password): 
        """Authenticate a user in the database"""
        try:
            query = """
                SELECT id FROM usuarios
                WHERE email = %s AND passwd = %s
            """
            self.cursor.execute(query, (email, hashlib.sha256(password.encode()).hexdigest()))
            result = self.cursor.fetchone()
            if result:
                return result['id']  # Return user ID
            else:
                return None
        except Error as e:
            self.logger.error(f"Error al autenticar usuario: {str(e)}")
            return None
        

    def agregar_usuario(self, usuario: Usuario):
        """Agrega un nuevo usuario a la base de datos"""
        try:
            query = """
                INSERT INTO usuarios (nombre, email, passwd, rol)
                VALUES (%s, %s, %s, %s)
            """
            self.cursor.execute(query, (
                usuario.nombre,
                usuario.email,
                hashlib.sha256(usuario.passwd.encode()).hexdigest(),
                usuario.rol
            ))
            self.connection.commit()
            return self.cursor.lastrowid
        except Error as e:
            self.connection.rollback()
            self.logger.error(f"Error al agregar usuario: {str(e)}")
            return None