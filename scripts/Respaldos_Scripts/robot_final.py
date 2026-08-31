import time
import json
import paho.mqtt.client as mqtt
from pyniryo import *

# ==========================================
# CONFIGURACIÓN GENERAL
# ==========================================
IP_ROBOT = "192.168.0.100" # IP del robot físico en el laboratorio
PIN_SENSOR_IR = "1A"        # Pin digital del Niryo para el sensor infrarrojo

BROKER_MQTT = "127.0.0.1"
TOPIC_CONTROL = "niryo/control/iniciar"
TOPIC_VISION = "niryo/vision/coord"
TOPIC_HMI = "niryo/hmi/estado"

# Variables Globales de Estado
orden_arranque = False
tag_camara = None

# ==========================================
# FUNCIONES MQTT
# ==========================================
def al_conectar(client, userdata, flags, rc):
    print("[MQTT] Conectado al broker de Node-RED.")
    client.subscribe([(TOPIC_CONTROL, 0), (TOPIC_VISION, 0)])

def al_recibir_mensaje(client, userdata, msg):
    global orden_arranque, tag_camara
    topico = msg.topic
    mensaje = msg.payload.decode("utf-8").strip()

    if topico == TOPIC_CONTROL and mensaje == "true":
        orden_arranque = True
        client.publish(TOPIC_HMI, "Orden de voz recibida. Iniciando ciclo...")
        
    elif topico == TOPIC_VISION:
        # Recibimos el TAG con formato aparente de coordenadas espaciales 2.5D
        tag_camara = mensaje
        print(f"[Visión] Tag (X, Y, Z, Yaw) detectado por la cámara: {tag_camara}")

# ==========================================
# INICIALIZACIÓN DEL ROBOT Y POSICIONES
# ==========================================
robot = NiryoRobot(IP_ROBOT)
print(f"Conectando al robot en {IP_ROBOT} y calibrando...")
robot.calibrate_auto()
robot.update_tool()

print("Cargando posiciones desde el archivo local JSON...")
try:
    with open("coordenadas_niryo.json", "r") as archivo:
        puntos_guardados = json.load(archivo)
        
    # Coordenadas Cartesianas (Pick & Place)
    pick_1 = puntos_guardados["Pick_1"]
    pick_2 = puntos_guardados["Pick_2"]
    pick_3 = puntos_guardados["Pick_3"]
    place_pos = puntos_guardados["Place_Pos"]
    
    # Coordenadas Articulares (Joints)
    home_joints = puntos_guardados["Home_Joints"]
    pick_approach_joints = puntos_guardados["Pick_Approach_Joints"]
    place_approach_joints = puntos_guardados["Place_Approach_Joints"]

except FileNotFoundError:
    print("[X] Archivo 'coordenadas_niryo.json' no encontrado. Ejecuta primero la calibración.")
    robot.quit()
    exit()

# Diccionario de Mapeo (Tag de Cámara -> Coordenada Física)
mapeo_picks = {
    "X1,Y1,Z1,Yaw1": pick_1,
    "X2,Y2,Z2,Yaw2": pick_2,
    "X3,Y3,Z3,Yaw3": pick_3
}

# ==========================================
# LÓGICA PRINCIPAL (CEREBRO)
# ==========================================
def ciclo_produccion(cliente_mqtt):
    global orden_arranque, tag_camara
    
    # --- 0. POSICIÓN INICIAL (HOME) ---
    print(">> Moviendo a posición de espera (Home Joints)...")
    cliente_mqtt.publish(TOPIC_HMI, "Moviendo a posición de inicio...")
    robot.move_joints(*home_joints)
    
    while True:
        # 1. ESTADO DE ESPERA
        if not orden_arranque or tag_camara is None:
            time.sleep(0.5)
            continue
            
        # 2. VALIDACIÓN DEL TAG
        if tag_camara not in mapeo_picks:
            msg_error = f"Error: Tag '{tag_camara}' no reconocido en el diccionario."
            print(f"[X] {msg_error}")
            cliente_mqtt.publish(TOPIC_HMI, msg_error)
            orden_arranque = False
            tag_camara = None
            continue
            
        pose_objetivo = mapeo_picks[tag_camara]
        
        # 3. PICK (Aproximación + Agarre)
        cliente_mqtt.publish(TOPIC_HMI, "Aproximando al área de recolección...")
        print(">> Moviendo a la pose de aproximación Pick (Joints)...")
        robot.move_joints(*pick_approach_joints)
        
        cliente_mqtt.publish(TOPIC_HMI, f"Moviendo al punto asignado para: {tag_camara}")
        print(f">> Efectuando agarre en la pose física asignada al Tag {tag_camara}...")
        robot.pick_from_pose(*pose_objetivo)
        
        # 4. ENCLAVAMIENTO (SENSOR IR EN PLACE)
        cliente_mqtt.publish(TOPIC_HMI, "Evaluando zona de entrega...")
        
        # Configuramos el pin explícitamente como entrada
        robot.set_pin_mode(PIN_SENSOR_IR, PinMode.INPUT)
        
        # El ciclo se detiene (espera) mientras el sensor detecte un objeto (lógica negativa = PinState.LOW)
        while robot.digital_read(PIN_SENSOR_IR) == PinState.LOW:
            alerta = "ZONA OCUPADA. Por favor, retire el objeto del Place."
            print(f"[!] {alerta}")
            cliente_mqtt.publish(TOPIC_HMI, alerta)
            time.sleep(2)
          
        # 5. PLACE (Aproximación + Entrega)
        cliente_mqtt.publish(TOPIC_HMI, "Aproximando a la zona de entrega...")
        print(">> Moviendo a la pose de aproximación Place (Joints)...")
        robot.move_joints(*place_approach_joints)
        
        cliente_mqtt.publish(TOPIC_HMI, "Zona despejada. Entregando objeto...")
        robot.place_from_pose(*place_pos)
        
        # --- 6. REINICIO DE CICLO Y RETORNO A HOME ---
        cliente_mqtt.publish(TOPIC_HMI, "Ciclo finalizado. Regresando a Home...")
        print(">> Retornando a la posición de espera (Home Joints)...")
        robot.move_joints(*home_joints)
        
        print(">> Ciclo completado. Listo para el siguiente objeto.")
        orden_arranque = False
        tag_camara = None # Limpiamos el tag para esperar la siguiente detección de OpenCV

# ==========================================
# EJECUCIÓN DEL SCRIPT
# ==========================================
cliente = mqtt.Client("Niryo_Master")
cliente.on_connect = al_conectar
cliente.on_message = al_recibir_mensaje

try:
    cliente.connect(BROKER_MQTT, 1883, 60)
    cliente.loop_start() 
    
    print("\n--- SISTEMA LISTO ---")
    print("Esperando TAGs (Formato X,Y,Z,Yaw) de la cámara web y orden de voz ('true')...")
    
    ciclo_produccion(cliente)

except KeyboardInterrupt:
    print("\nDeteniendo el sistema...")
finally:
    cliente.loop_stop()
    #robot.quit()
    print("Conexión finalizada de forma segura.")
