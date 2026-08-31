import json
import os
from pyniryo import *

# ==========================================
# CONFIGURACIÓN
# ==========================================
IP_ROBOT = "192.168.0.100" 
robot = NiryoRobot(IP_ROBOT) 

print("Conectado al robot. Iniciando calibración...")
robot.calibrate_auto() 
robot.update_tool() 
robot.set_learning_mode(True) 

# ==========================================
# LECTURA DEL ARCHIVO EXISTENTE
# ==========================================
nombre_archivo = "coordenadas_niryo.json"
mis_puntos = {}

# Verificamos si el archivo ya existe para no sobreescribir tus poses cartesianas
if os.path.exists(nombre_archivo):
    with open(nombre_archivo, "r") as archivo:
        mis_puntos = json.load(archivo)
    print(f"\n[+] Se encontró '{nombre_archivo}'. Se conservarán los puntos Pick y Place actuales.")
else:
    print(f"\n[!] No se encontró '{nombre_archivo}', se creará uno nuevo.")

print("\n--- MODO APRENDIZAJE ACTIVADO ---")
print("El brazo está libre. Vamos a capturar solo los JOINTS (ángulos).")

# 1. CAPTURA DE HOME
input("\n>> 1. Mueve el brazo a la posición de HOME (Reposo/Espera) y presiona ENTER...")
mis_puntos["Home_Joints"] = list(robot.get_joints())
print("Punto 'Home_Joints' capturado exitosamente.")

# 2. CAPTURA DE APROXIMACIÓN A PICK (Z Superior)
input("\n>> 2. Mueve el brazo a la APROXIMACIÓN DE PICK (encima de los objetos) y presiona ENTER...")
mis_puntos["Pick_Approach_Joints"] = list(robot.get_joints())
print("Punto 'Pick_Approach_Joints' capturado exitosamente.")

# 3. CAPTURA DE APROXIMACIÓN A PLACE (Z Superior)
input("\n>> 3. Mueve el brazo a la APROXIMACIÓN DE PLACE (encima de la entrega) y presiona ENTER...")
mis_puntos["Place_Approach_Joints"] = list(robot.get_joints())
print("Punto 'Place_Approach_Joints' capturado exitosamente.")

robot.set_learning_mode(False) 
print("\n--- MODO APRENDIZAJE DESACTIVADO ---")

# ==========================================
# GUARDADO DE DATOS (ACTUALIZACIÓN)
# ==========================================
with open(nombre_archivo, "w") as archivo:
    json.dump(mis_puntos, archivo, indent=4)

print(f"\n¡Éxito! Los nuevos joints se han añadido a '{nombre_archivo}' de forma segura.")
