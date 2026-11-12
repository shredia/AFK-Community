# cli.py
import argparse

def obtener_argumentos():
    parser = argparse.ArgumentParser(description='Esperian Archive: Exportador a Excel')
    parser.add_argument('--output', '-o', default='reporte_esperian.xlsx', help='Ruta del archivo de salida en Excel')
    parser.add_argument('--cuenta', action='store_true', help='Configurar cuenta de Esperian Archive')
    parser.add_argument('--limite', type=int, default=0, help='Máximo de runs a descargar (0 = todas)')
    parser.add_argument('--perfil', default='./perfil_esperian', help='Ruta de referencia: los datos se guardan en su carpeta padre')
    return parser.parse_args()