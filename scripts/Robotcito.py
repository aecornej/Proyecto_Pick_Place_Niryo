import time
import json
import paho.mqtt.client as mqtt
from pyniryo import *

# ==========================================
# CONFIGURACIÓN GENERAL
# ==========================================
IP_ROBOT = "192.168.0.100" #"192.168.0.128" #"192.168.0.100" #"10.10.10.10" #"200.126.13.185" # IP del robot físico en el laboratorio
PIN_SENSOR_IR = "1A"        # Pin digital del Niryo para el sensor infrarrojo  

BROKER_MQTT = "127.0.0.1"
TOPIC_CONTROL = "niryo/control/iniciar"
TOPIC_MODO = "niryo/control/modo"
TOPIC_PUNTO = "niryo/control/punto"
TOPIC_HMI = "niryo/hmi/estado"
TOPIC_TELEMETRIA = "niryo/robot/coordenadas" 
TOPIC_VISION = "niryo/vision/coord"

# Variables Globales de Estado
orden_arranque = False
modo_actual = "manual"
punto_manual = None
tag_camara = None 

# ==========================================
# FUNCIONES DE TELEMETRÍA Y MQTT
# ==========================================
def enviar_telemetria(cliente_mqtt, robot_instance):
    """Fuerza la actualización de coordenadas en el HMI en cualquier momento."""
    try:
        pose = robot_instance.get_pose()
        telemetria = f"{pose.x:.3f},{pose.y:.3f},{pose.z:.3f},{pose.roll:.3f},{pose.pitch:.3f},{pose.yaw:.3f}"
        cliente_mqtt.publish(TOPIC_TELEMETRIA, telemetria)
    except Exception:
        pass

def al_conectar(client, userdata, flags, rc):
    print("[MQTT] Conectado al broker de Node-RED.")
    client.subscribe([(TOPIC_CONTROL, 0), (TOPIC_MODO, 0), (TOPIC_PUNTO, 0), (TOPIC_VISION, 0)])

def al_recibir_mensaje(client, userdata, msg):
    global orden_arranque, modo_actual, punto_manual, tag_camara
    topico = msg.topic
    mensaje_crudo = msg.payload.decode("utf-8").strip()
    
    print(f"[DEBUG MQTT] Llegó -> Tópico: {topico} | Mensaje: {mensaje_crudo}")

    if topico == TOPIC_CONTROL:
        if mensaje_crudo.lower() in ["true", "start"]:
            orden_arranque = True
            client.publish(TOPIC_HMI, f">> Orden [START]. Ciclo armado en modo: {modo_actual.upper()}")
        elif mensaje_crudo.lower() == "stop":
            orden_arranque = False
            client.publish(TOPIC_HMI, "[!] ALERTA: Paro de Emergencia activado.")
            try: robot.stop_move()
            except: pass
            
    elif topico == TOPIC_MODO:
        modo_actual = mensaje_crudo.lower()
        client.publish(TOPIC_HMI, f">> Configuración: Modo cambiado a {modo_actual.upper()}")
        
    elif topico == TOPIC_PUNTO:
        if mensaje_crudo.lower() != "manual":
            punto_manual = mensaje_crudo
            client.publish(TOPIC_HMI, f">> Selección manual fijada en: {punto_manual}")
            
    elif topico == TOPIC_VISION:
        if mensaje_crudo in ["Pick_1", "Pick_2", "Pick_3"]:
            tag_camara = mensaje_crudo
            print(f"[DEBUG VISIÓN] Objeto fijado en: {tag_camara}")

# ==========================================
# INICIALIZACIÓN DEL ROBOT Y POSICIONES
# ==========================================
robot = NiryoRobot(IP_ROBOT)
print(f"Conectando al robot en {IP_ROBOT}...")

try:
    robot.clear_collision_detected()
except Exception:
    pass

print("Calibrando y preparando hardware...")
robot.calibrate_auto()
robot.update_tool()

print("Cargando posiciones desde el archivo local JSON...")
try:
    with open("coordenadas_niryo.json", "r") as archivo:
        puntos_guardados = json.load(archivo)
        
    diccionario_picks = {
        "Pick_1": puntos_guardados["Pick_1"],
        "Pick_2": puntos_guardados["Pick_2"],
        "Pick_3": puntos_guardados["Pick_3"]
    }
    
    diccionario_approach = {
        "Pick_1": puntos_guardados["Pick_1_Approach_Joints"],
        "Pick_2": puntos_guardados["Pick_2_Approach_Joints"],
        "Pick_3": puntos_guardados["Pick_3_Approach_Joints"]
    }
    
    place_pos = puntos_guardados["Place_Pos"]
    place_approach_joints = puntos_guardados["Place_Approach_Joints"]
    home_joints = puntos_guardados["Home_Joints"]

except FileNotFoundError:
    print("[X] Archivo 'coordenadas_niryo.json' no encontrado.")
    robot.close_connection()
    exit()

# ==========================================
# SUBRUTINA: EJECUTAR MOVIMIENTO 
# ==========================================
def ejecutar_movimiento(id_punto, cliente_mqtt):
    pose_objetivo = diccionario_picks[id_punto]
    pick_approach_joints = diccionario_approach[id_punto]
    
    # 1. APROXIMACIÓN AÉREA AL PICK
    cliente_mqtt.publish(TOPIC_HMI, f">> [1/6] Moviendo a pose de aproximación Pick (Joints) para {id_punto}...")
    print(f">> Moviendo a la pose de aproximación Pick (Joints) para {id_punto}...")
    robot.move_joints(*pick_approach_joints)
    enviar_telemetria(cliente_mqtt, robot)
    
    # 2. PICK 
    cliente_mqtt.publish(TOPIC_HMI, f">> [2/6] Efectuando agarre en pose física: {id_punto}...")
    print(f">> Moviendo a la pose física asignada para {id_punto}...")
    robot.pick_from_pose(*pose_objetivo)
    enviar_telemetria(cliente_mqtt, robot) 
    
    # 3. ENCLAVAMIENTO SENSOR IR
    cliente_mqtt.publish(TOPIC_HMI, ">> [3/6] Evaluando enclavamiento en zona de entrega...")
    robot.set_pin_mode(PIN_SENSOR_IR, PinMode.INPUT)
    
    while robot.digital_read(PIN_SENSOR_IR) == PinState.LOW:
        alerta = "[!] ZONA OCUPADA: Por favor, retire el objeto del Place."
        print(f"[!] {alerta}")
        cliente_mqtt.publish(TOPIC_HMI, alerta)
        time.sleep(2)
      
    # 4. APROXIMACIÓN AÉREA AL PLACE
    cliente_mqtt.publish(TOPIC_HMI, ">> [4/6] Zona libre. Moviendo a pose de aproximación Place (Joints)...")
    print(">> Moviendo a la pose de aproximación Place (Joints)...")
    robot.move_joints(*place_approach_joints)
    enviar_telemetria(cliente_mqtt, robot)
      
    # 5. PLACE 
    cliente_mqtt.publish(TOPIC_HMI, ">> [5/6] Moviendo a zona de entrega y soltando objeto...")
    print(">> Moviendo a la zona de entrega...")
    robot.place_from_pose(*place_pos)
    enviar_telemetria(cliente_mqtt, robot) 
    
    # 6. TRANSICIÓN A HOME
    cliente_mqtt.publish(TOPIC_HMI, ">> [6/6] Ciclo completo. Retornando a posición de espera (Home Joints)...")
    print(">> Retornando a la posición de espera (Home)...")
    robot.move_joints(*home_joints)
    enviar_telemetria(cliente_mqtt, robot) 

# ==========================================
# LÓGICA PRINCIPAL (CEREBRO MÁQUINA DE ESTADOS)
# ==========================================
def ciclo_produccion(cliente_mqtt):
    global orden_arranque, modo_actual, punto_manual, tag_camara
    
    print(">> Moviendo a posición de espera (Home Joints)...")
    cliente_mqtt.publish(TOPIC_HMI, ">> Inicializando: Moviendo a posición de espera (Home Joints)...")
    robot.move_joints(*home_joints)
    enviar_telemetria(cliente_mqtt, robot)
    
    while True:
        # --- ESTADO DE ESPERA & TELEMETRÍA CONTINUA ---
        if not orden_arranque:
            enviar_telemetria(cliente_mqtt, robot)
            time.sleep(0.5)
            continue
            
        # --- MODO AUTOMÁTICO ---
        if modo_actual == "auto":
            if tag_camara:
                msg_auto = f">> [AUTO] Iniciando recolección detectada por cámara en: {tag_camara}"
                cliente_mqtt.publish(TOPIC_HMI, msg_auto)
                print(msg_auto)
                ejecutar_movimiento(tag_camara, cliente_mqtt)
                tag_camara = None 
            else:
                cliente_mqtt.publish(TOPIC_HMI, ">> [AUTO] En espera: Buscando piezas mediante cámara...")
                time.sleep(0.5)
            
        # --- MODO MANUAL ---
        elif modo_actual == "manual":
            if punto_manual in ["Pick_1", "Pick_2", "Pick_3"]:
                msg_manual = f">> [MANUAL] Ejecutando orden del operador hacia: {punto_manual}"
                cliente_mqtt.publish(TOPIC_HMI, msg_manual)
                print(msg_manual)
                ejecutar_movimiento(punto_manual, cliente_mqtt)
                
                cliente_mqtt.publish(TOPIC_HMI, ">> [MANUAL] Ciclo completado. Esperando nuevas órdenes...")
                print(f">> Ciclo Manual completado.")
                
                punto_manual = None 
                orden_arranque = False 
            else:
                cliente_mqtt.publish(TOPIC_HMI, ">> [MANUAL] En espera: Seleccione un punto objetivo...")
                time.sleep(0.5)

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
    print("Manejando Máquina de Estados (Auto/Manual) y Telemetría del Robot...")
    
    ciclo_produccion(cliente)

except KeyboardInterrupt:
    print("\nDeteniendo el sistema...")
finally:
    cliente.loop_stop()
    robot.close_connection()
    print("Conexión finalizada de forma segura.")
