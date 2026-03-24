#!/usr/bin/env python3
"""
Test de extracción mejorada de datos de cédula ecuatoriana
Prueba con los textos OCR reales que proporciona el usuario
"""

import re

# Mocks de textos OCR extraídos (tal como aparecen en la realidad)
CEDULAS_TEST = [
    {
        "nombre": "ROSERO MONGE - DIANA ESTEFANIA",
        "ocr": """CÉDULA DE
REPÚBLICA DEL ECUADOR
IDENTIDAD 
DIRECCIÓN GENERAL DE REGISTRO CIVIL; IDENTIFICACION 
CEDULACION
APELLIDOS 
CONDICIÓN CIUDADANIA 
ROSERO 
MONGE
NOMBRES 
DIANA ESTEFANLA
NACIONALIDAD 
ECUATORIANA 
FECHA DE NACIMIENTO 
SEXO
29 OCT 1989
MUJER
LUGAR DE NACIMIENTO
DOCUMENTO
PICHINCHA Quito
074354027 
SAN BLAS""",
        "esperado": {
            "nui": "074354027",
            "apellidos": "ROSERO MONGE",
            "nombres": "DIANA ESTEFANIA"
        }
    },
    {
        "nombre": "PABLO FABRICIO - PICHINCHA",
        "ocr": """REPÚBLICA DEL ECUADOR 
DIRECCIÓN CENERAL DEREGISTRO CIVIL, 
IDENTIFICACION Y CEDULACION
CÉDULA 
DE
No 
171144385-1
PAELO FABRICIO
FICHINCHA
EFCHA D
ENACIMIENTO 
1978-07-3; 
1""",
        "esperado": {
            "nui": "1711443851",
            "apellidos": None,  # No está claramente identificado
            "nombres": "PAELO FABRICIO"
        }
    },
    {
        "nombre": "MARTINEZ MACANCELA",
        "ocr": """REPÚBLICA DEL ECUADOR 
DIRECCIÓN GENERAL DE REGISTRO CIVIL
IDENTIFICACION Y CEDULACION 
CÉDULA DE
172362215-3
CIUDADANIA
APELLIDOS 
NOMBRES 
MARTINEZ MACANCELA
LUGAR DE NACIMIENTO
PICHINCHA
Quito""",
        "esperado": {
            "nui": "1723622153",
            "apellidos": "MARTINEZ",
            "nombres": "MACANCELA"
        }
    },
    {
        "nombre": "MOSQUERA HIDALGO - MARGARITA LUCIA",
        "ocr": """CÉDULA DE
REPÚBLICA DEL ECUADOR
IDENTIDAD
APELLIDOS 
CONDICIÓN CIUDADANIA
MOSQUERA
HIDALGO 
NOMBRES 
MARGARITA LUCUA
NACIONALIDAD
ECUATORIANA
FECHA DE NACIMIENTO
SEXO
11 AGO 1975
HUJЕР
LUGAR DE NACIMIENTO
No DOCUMENTO
PICHINCHA Quito
062831179
BENALCAZAR
FIRMA DELTITULAR
MUI 1713341368""",
        "esperado": {
            "nui": "062831179",  # o 1713341368 del MUI
            "apellidos": "MOSQUERA HIDALGO",
            "nombres": "MARGARITA LUCIA"
        }
    },
    {
        "nombre": "GUAMINGA GUAMAN - FERNANDA ELIZABETH",
        "ocr": """CÉDULA DE
REPÚBLICA DEL ECUADOR
IDENTIDAD
DIRECCIÓN GENERAL DE REGISTRO CIVIL IDENTIFICACION Y CEDULACION 
APELWDOS 
CONDICIÓN CIUDADANIA
GUAMINGA
GUAMAN
NOMBRES 
FERNANDA ELLZABETH
NACIONALIDAD 
ECUATORIANA 
FECHA DE NACIMIENTO
SEXO
18 OCT 1991 
MUJER 
LUGAR DE NACIMIENTO 
AUTOIDENTICACION 
PICHINCHA QUITO 
HESTIZ
OIA 
FECHA DE VENCINIENTO
FIPRSA DEL TITULAR
30 DIC 2035
Natcan
NUI.1723648513
103086""",
        "esperado": {
            "nui": "1723648513",
            "apellidos": "GUAMINGA GUAMAN",
            "nombres": "FERNANDA ELIZABETH"
        }
    },
    {
        "nombre": "FLORES HURTADO - LUIS ALFONSO",
        "ocr": """CÉDULA DE
REPÚBLICA DEL ECUADOR
IDENTIDAD
APELLIDOS 
CONDICIÓN CIUDADANIA
FLORES 
HURTADO 
NOMBRES 
LUIS ALFONSO
NACIONALIDAD
ECUATORIANA
FECHA DE
NACIMIENTO
SEXO
31 OCT 1988
HOMBRE
LUGAR DE NACIMIENTO
No DOCUMENTO
STO. DOMINGO STO. DOHINGO
062526118
SANTO DOUINGO DE LOS COL
FECHADEVENCIMIENTO
FIRMA DEL
TITULAR
24 JUL 2033
NATICAN
NUI.1003085493
508052""",
        "esperado": {
            "nui": "062526118",
            "apellidos": "FLORES HURTADO",
            "nombres": "LUIS ALFONSO"
        }
    },
    {
        "nombre": "PABON PLAZA - FRANCISCO ANTONIO",
        "ocr": """CÉDULA DE
REPÚBLICA DEL ECUADOR 
IDENTIDAD 
APELLIDOS 
CONDICIÓN CIUDADANIA
PABON 
PLAZA 
NOMBRES 
FRANCISCO ANTONIO 
NACIONALIDAD 
ECUATORIANA 
FECHA
DE NACIMIENTO
SEXO
15 ENE 1992
HOMBRE
LUGAR DE NACIMIENTO
No
DOCUMENTO
PICHINCHA QuITO
040931023
SAN BLAS
FECHA DE VENCIMENTO
FIRMA DEL TITULAR
18 OCT 2032
NUL.17 21788931
926""",
        "esperado": {
            "nui": "040931023",
            "apellidos": "PABON PLAZA",
            "nombres": "FRANCISCO ANTONIO"
        }
    },
    {
        "nombre": "ANDRADE ROCHA - RICHARD SANTIAGO",
        "ocr": """CÉDULA DE
REPÚBLICA DEL ECUADOR
IDENTIDAD
ANDRADE 
ROCHA
NOMBRES 
RICHARD SANTIAGO 
NACIONALIDAD
ECUATORIANA 
FECHA DE NACIMIENTO
SEXO
24 JUL 198
9
HOMBRE 
LUGAR DE NACIMIENTO 
AUTOIDENTICACIÓN 
IMBABURA ANTONIO ANTE
MESTIZOIA
ATUNTAQUI 
FECHA DE VENCIMIENTO
FIRMA DEL TITULAR
14 JUN 2035
NATICAN
NUI.1723533913
718391""",
        "esperado": {
            "nui": "1723533913",
            "apellidos": "ANDRADE ROCHA",
            "nombres": "RICHARD SANTIAGO"
        }
    }
]

def extraer_nui(texto):
    """Extrae NUI con patrones robustos para cédulas ecuatorianas"""
    nui = None
    
    # Patrón 1: "No " o "No." seguido de dígitos (variante 1)
    patron_no1 = r'No\.?\s+(\d{9,13}(?:-\d)?)'
    match = re.search(patron_no1, texto)
    if match:
        nui = match.group(1).strip()
    
    # Patrón 2: "CÉDULA DE\n" seguido de dígitos
    if not nui:
        patron_cedula = r'CÉDULA\s+DE\s+(?:No\s+)?(\d{9,13}(?:-\d)?)'
        match = re.search(patron_cedula, texto, re.IGNORECASE | re.MULTILINE)
        if match:
            nui = match.group(1).strip()
    
    # Patrón 3: Números aislados de 10-13 dígitos (como fallback)
    if not nui:
        # Buscar el primero que no sea parte de otro contexto
        matches = re.findall(r'\b(\d{9,13})\b', texto)
        if matches:
            # Preferir números que tengan contexto de cédula
            for match in matches:
                if len(match) == 10 or len(match) == 11:  # Rango típico de cédulas
                    nui = match
                    break
            if not nui:
                nui = matches[0]  # Si no hay coincidencia exacta, toma el primero
    
    # Patrón 4: "NUI." (última opción, a menudo con errores de OCR)
    if not nui:
        patron_nui_label = r'NUI\.?\s*(\d{9,13}(?:-\d)?)'
        match = re.search(patron_nui_label, texto, re.IGNORECASE)
        if match:
            nui = match.group(1).strip()
    
    # Limpiar
    if nui:
        nui = nui.replace(' ', '').replace('-', '').strip()
        if not re.match(r'^\d{8,13}$', nui):
            nui = None
    
    return nui

def extraer_apellidos(texto):
    """Extrae apellidos - captura hasta 2 palabras después de APELLIDOS"""
    apellidos = None
    
    # Patrón flexible para "APELLIDOS" 
    # Captura 1-2 líneas de texto después
    patron = r'APELL?IDOS?\s+(?:CONDICIÓN\s+CIUDADANIA\s+)?\n?\s*([A-ZÁÉÍÓÚ][A-ZÁÉÍÓÚA-Z\s\n]{1,80}?)(?=\n\s*NOMBRES?|\nNOMBRES?)'
    match = re.search(patron, texto, re.IGNORECASE | re.MULTILINE)
    
    if match:
        apellidos = match.group(1).strip()
        # Limpiar saltos de línea y espacios extras
        apellidos = ' '.join(apellidos.split())
        # Limitar a máximo 4 palabras (dos apellidos)
        palabras = apellidos.split()
        if len(palabras) > 2:
            apellidos = ' '.join(palabras[:2])
    
    return apellidos

def extraer_nombres(texto):
    """Extrae nombres - captura hasta 3 palabras después de NOMBRES"""
    nombres = None
    
    # Patrón flexible para "NOMBRES"
    patron = r'NOMBRES?\s+\n?\s*([A-ZÁÉÍÓÚ][A-ZÁÉÍÓÚA-Z\s\n]{1,80}?)(?=\n\s*(?:NACIONALIDAD|FECHA|LUGAR|CONDICIÓN|AUTOIDENTICACION|$))'
    match = re.search(patron, texto, re.IGNORECASE | re.MULTILINE)
    
    if match:
        nombres = match.group(1).strip()
        # Limpiar saltos de línea y espacios extras
        nombres = ' '.join(nombres.split())
        # Limitar a máximo 3 palabras
        palabras = nombres.split()
        if len(palabras) > 3:
            nombres = ' '.join(palabras[:3])
    
    return nombres

def test_extraccion():
    """Test de extracción mejorada"""
    print("\n" + "=" * 80)
    print("TEST DE EXTRACCIÓN MEJORADA - CÉDULAS ECUATORIANAS")
    print("=" * 80)
    
    total = len(CEDULAS_TEST)
    aciertos = 0
    
    for i, cedula in enumerate(CEDULAS_TEST, 1):
        print(f"\n📋 Cedula #{i}: {cedula['nombre']}")
        print("-" * 80)
        
        ocr_text = cedula['ocr']
        esperado = cedula['esperado']
        
        # Extraer
        nui = extraer_nui(ocr_text)
        apellidos = extraer_apellidos(ocr_text)
        nombres = extraer_nombres(ocr_text)
        
        # Comparar
        nui_ok = str(nui) == str(esperado['nui']) if nui else False
        apellidos_ok = str(apellidos).strip() == str(esperado['apellidos']).strip() if apellidos and esperado['apellidos'] else (apellidos is None and esperado['apellidos'] is None)
        nombres_ok = str(nombres).strip() == str(esperado['nombres']).strip() if nombres and esperado['nombres'] else (nombres is None and esperado['nombres'] is None)
        
        total_ok = nui_ok and apellidos_ok and nombres_ok
        if total_ok:
            aciertos += 1
        
        # Mostrar resultado
        status_nui = "✅" if nui_ok else "❌"
        status_app = "✅" if apellidos_ok else "❌"
        status_nom = "✅" if nombres_ok else "❌"
        
        print(f"{status_nui} NUI:        {nui} (esperado: {esperado['nui']})")
        print(f"{status_app} Apellidos:  {apellidos} (esperado: {esperado['apellidos']})")
        print(f"{status_nom} Nombres:    {nombres} (esperado: {esperado['nombres']})")
    
    # Resumen
    print("\n" + "=" * 80)
    print(f"RESULTADO: {aciertos}/{total} cédulas extraídas correctamente ✅")
    print("=" * 80 + "\n")
    
    return aciertos == total

if __name__ == "__main__":
    success = test_extraccion()
    exit(0 if success else 1)
