def generar_retroalimentacion(calificacion, contenido=None, titulo=None, objetivo=None):
    """
    Genera retroalimentación detallada basada en la calificación y el contenido.
    
    Args:
        calificacion: Puntuación numérica (0-10)
        contenido: Texto del contenido entregado (opcional)
        titulo: Título de la actividad (opcional)
        objetivo: Objetivo de la actividad (opcional)
        
    Returns:
        Diccionario con retroalimentación positiva y áreas de mejora
    """
    # Base feedback based on score
    if calificacion >= 9:
        positivo = "La entrega es de excelente calidad. Demuestra dominio completo del tema."
        mejoras = "Para futuras entregas, considera profundizar en aspectos avanzados del tema."
    elif calificacion >= 8:
        positivo = "La entrega es de muy buena calidad. Cumple con todos los requisitos."
        mejoras = "Considera agregar más ejemplos o casos prácticos para enriquecer tu trabajo."
    elif calificacion >= 7:
        positivo = "La entrega es de buena calidad. Cumple con la mayoría de los requisitos."
        mejoras = "Revisa la estructura y organización para mejorar la claridad de tus ideas."
    elif calificacion >= 6:
        positivo = "La entrega es aceptable. Cumple con los requisitos básicos."
        mejoras = "Profundiza más en los conceptos clave y revisa la redacción."
    elif calificacion >= 5:
        positivo = "La entrega cumple con los requisitos mínimos."
        mejoras = "Revisa los conceptos fundamentales y desarrolla más tus argumentos."
    else:
        positivo = "La entrega muestra esfuerzo, pero necesita mejoras significativas."
        mejoras = "Revisa cuidadosamente los requisitos del objetivo y asegúrate de cumplirlos."
    
    # Enhanced feedback if content is provided
    if contenido:
        # Check content length
        palabras = len(contenido.split())
        if palabras < 100:
            mejoras += " El contenido es muy breve, desarrolla más tus ideas."
        elif palabras > 1000:
            positivo += " Has desarrollado un trabajo extenso y detallado."
            
    # Add relevance feedback if title and objective are provided
    if titulo and objetivo and contenido:
        # Simple relevance check (in a real system, use NLP techniques)
        palabras_clave = set((titulo + " " + objetivo).lower().split())
        palabras_contenido = set(contenido.lower().split())
        palabras_comunes = palabras_clave.intersection(palabras_contenido)
        
        if len(palabras_clave) > 0:
            relevancia = len(palabras_comunes) / len(palabras_clave)
            if relevancia < 0.3:
                mejoras += " Tu trabajo podría estar más enfocado en el tema solicitado."
            elif relevancia > 0.7:
                positivo += " Has abordado el tema de manera muy pertinente."
    
    # Add specific suggestions based on score ranges
    if calificacion < 7:
        mejoras += " Considera revisar los materiales de clase y consultar fuentes adicionales."
        
    if calificacion < 5:
        mejoras += " Te recomiendo solicitar asesoría para aclarar los conceptos fundamentales."
    
    return {
        "positivo": positivo,
        "mejoras": mejoras,
        "calificacion": calificacion
    }

