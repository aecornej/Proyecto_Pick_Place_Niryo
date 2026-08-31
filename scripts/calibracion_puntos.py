import json
from pyniryo import *

IP_ROBOT = "192.168.0.100" #"10.10.10.10" #"200.126.13.185"
robot = NiryoRobot(IP_ROBOT) 

print("Conectado al robot. Iniciando secuencia de calibración...")
robot.calibrate_auto() 
print("¡Calibración exitosa!")

robot.update_tool() 
robot.set_learning_mode(True) 

print("\n--- MODO APRENDIZAJE ACTIVADO ---")
print("El brazo está libre. Muévelo físicamente al punto deseado y presiona ENTER.")

# Diccionario local para guardar las coordenadas
mis_puntos = {}

input("\n>> Mueve el brazo al punto de PICK 1 y presiona ENTER...")
# Usamos to_list() de inmediato para guardar un formato [x, y, z, roll, pitch, yaw] amigable
mis_puntos["Pick_1"] = robot.get_pose().to_list()
print(f"Punto Pick 1 capturado.")

input("\n>> Mueve el brazo al punto de PICK 2 y presiona ENTER...")
mis_puntos["Pick_2"] = robot.get_pose().to_list()
print(f"Punto Pick 2 capturado.")

input("\n>> Mueve el brazo al punto de PICK 3 y presiona ENTER...")
mis_puntos["Pick_3"] = robot.get_pose().to_list()
print(f"Punto Pick 3 capturado.")

input("\n>> Mueve el brazo al punto de PLACE y presiona ENTER...")
mis_puntos["Place_Pos"] = robot.get_pose().to_list()
print(f"Punto Place capturado.")

robot.set_learning_mode(False) 
print("\n--- MODO APRENDIZAJE DESACTIVADO ---")

# Guardar el diccionario en un archivo JSON local
with open("coordenadas_niryo.json", "w") as archivo:
    json.dump(mis_puntos, archivo, indent=4)

print("\n¡Éxito! Todas las coordenadas se guardaron en 'coordenadas_niryo.json' en tu laptop.")
#robot.quit()
