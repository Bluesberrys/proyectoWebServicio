# Documentation for Proyecto Web Servicio

## File Structure

```
proyectoWebServicio/
│
├── static/
│   ├── img/
│   │   ├── ayuda.jpg
│   │   ├── Escudo-UNAM-white.svg
│   │   ├── Escudo-UNAM.svg
│   │   ├── evaluacion.webp
│   │   ├── fondo_improvisado5.jpeg
│   │   ├── practicas.jpeg
│   │   └── programador.avif
│   ├── js/
│   │   └── functions.js
│   └── styles.css
│
├── templates/
│   ├── 404.html
│   ├── admin_dashboard.html
│   ├── admin_usuarios.html
│   ├── estudiante_evaluacion.html
│   ├── estudiante.html
│   ├── inicio.html
│   ├── profesor_dashboard.html
│   ├── profesor_usuarios.html
│   ├── registro.html
│   ├── usuario_dashboard.html
│   ├── evaluacion.html
│   ├── index.html
│   ├── practicas.html
│   ├── usuarios.html
│   └── ver_practicas.html
│
├── .gitignore
├── app.py
├── bd_prueba.py
├── config.py
├── crear_base_datos.sql
├── documentation.md
├── generador_practicas.log
├── generador_practicas.py
├── generador-practicas-pytorch.py
├── modelo_ml_scikit.py
├── README.md
└── requirements.txt
```

## Homepage

The homepage (`index.html`) serves as the entry point for the application. It provides navigation to key sections such as practices, evaluations, and user management.

## How to Run the Project

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set Up the Database**:
   - Use the `crear_base_datos.sql` script to create the necessary tables in your database.

3. **Run the Application**:
   ```bash
   python app.py
   ```

4. **Access the Application**:
   Open your browser and navigate to `http://localhost:5000`.

## Additional Notes

- Ensure that the database credentials in `config.py` are correctly configured.
- Static files (CSS, JavaScript, and images) are located in the `static/` directory.
- Templates for rendering HTML pages are located in the `templates/` directory.
- The `user-registration-system/` directory contains the logic for handling user registration requests and administrator approvals.