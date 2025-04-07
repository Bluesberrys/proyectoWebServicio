import mysql.connector

# Prueba de conexión
try:
    conn = mysql.connector.connect(
        host="localhost",
        user="root",  
        password="",  
        database="generador_practicas"
    )
    print("Conexión exitosa a la BD")
    conn.close()
except Exception as e:
    print(f"Error de conexión: {str(e)}")