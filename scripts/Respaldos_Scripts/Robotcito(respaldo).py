import time
import json
import paho.mqtt.client as mqtt
from pyniryo import *

# ==========================================
# CONFIGURACIÓN GENERAL
# ==========================================
IP_ROBOT = "192.168.0.100" 
PIN_SENSOR_IR = "1A"  

BROKER_MQTT = "127.0.0.1"
TOPIC_CONTROL = "niryo/control/iniciar"import time
import json
import paho.mqtt.client as mqtt
from pyniryo import *

# ==========================================
# CONFIGURACIÓN GENERAL
# ==========================================
IP_ROBOT = "192.168.0.100" 
PIN_SENSOR_IR = "1A"  

BROKER_MQTT = "127.0.0.1"
TOPIC_CONTROL = "niryo/control/iniciar"
TOPIC_MODO = "niryo/control/modo"
TOPIC_PUNTO = "niryo/control/punto"
TOPIC_HMI = "niryo/hmi/estado"
TOPIC_TELEMETRIA = "niryo/robot/coordenadas" 
TOPIC_VISION = "niryo/vision/coord" # NUEVO: Tópico de la cámara

# Variables Globales de Estado
orden_arranque = False
modo_actual = "manual"
punto_manual = None
tag_camara = None # Memoria para lo que ve la cámara

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
    # Ahora nos suscribimos también a la visión
    client.subscribe([(TOPIC_CONTROL, 0), (TOPIC_MODO, 0), (TOPIC_PUNTO, 0), (TOPIC_VISION, 0)])

def al_recibir_mensaje(client, userdata, msg):
    global orden_arranque, modo_actual, punto_manual, tag_camara
    topico = msg.topic
    
    # IMPORTANTE: No usamos .lower() aquí para no dañar los "Pick_1"
    mensaje_crudo = msg.payload.decode("utf-8").strip()
    
    print(f"[DEBUG MQTT] Llegó -> Tópico: {topico} | Mensaje: {mensaje_crudo}")

    if topico == TOPIC_CONTROL:
        if mensaje_crudo.lower() in ["true", "start"]:
            orden_arranque = True
            client.publish(TOPIC_HMI, f"Orden recibida. Ciclo en modo: {modo_actual.upper()}")
        elif mensaje_crudo.lower() == "stop":
            orden_arranque = False
            client.publish(TOPIC_HMI, "¡ALERTA! Paro de Emergencia.")
            try: robot.stop_move()
            except: pass
            
    elif topico == TOPIC_MODO:
        modo_actual = mensaje_crudo.lower()
        client.publish(TOPIC_HMI, f"Modo cambiado a: {modo_actual.upper()}")
        
    elif topico == TOPIC_PUNTO:
        if mensaje_crudo.lower() != "manual":
            punto_manual = mensaje_crudo
            client.publish(TOPIC_HMI, f"Punto manual seleccionado: {punto_manual}")
            
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
    place_pos = puntos_guardados["Place_Pos"]
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
    
    # PICK 
    cliente_mqtt.publish(TOPIC_HMI, f"Efectuando agarre en: {id_punto}")
    print(f">> Moviendo a la pose física asignada para {id_punto}...")
    robot.pick_from_pose(*pose_objetivo)
    enviar_telemetria(cliente_mqtt, robot) # Actualiza dashboard tras el agarre
    
    # ENCLAVAMIENTO SENSOR IR
    cliente_mqtt.publish(TOPIC_HMI, "Evaluando zona de entrega...")
    robot.set_pin_mode(PIN_SENSOR_IR, PinMode.INPUT)
    
    while robot.digital_read(PIN_SENSOR_IR) == PinState.LOW:
        alerta = "ZONA OCUPADA. Por favor, retire el objeto del Place."
        print(f"[!] {alerta}")
        cliente_mqtt.publish(TOPIC_HMI, alerta)
        time.sleep(2)
      
    # PLACE 
    cliente_mqtt.publish(TOPIC_HMI, "Zona despejada. Entregando objeto...")
    print(">> Moviendo a la zona de entrega...")
    robot.place_from_pose(*place_pos)
    enviar_telemetria(cliente_mqtt, robot) # Actualiza dashboard tras la entrega
    
    # TRANSICIÓN A HOME
    cliente_mqtt.publish(TOPIC_HMI, "Objeto entregado. Retornando a posición segura...")
    print(">> Retornando a la posición de espera (Home)...")
    robot.move_joints(*home_joints)
    enviar_telemetria(cliente_mqtt, robot) # Actualiza dashboard al llegar a casa

# ==========================================
# LÓGICA PRINCIPAL (CEREBRO MÁQUINA DE ESTADOS)
# ==========================================
def ciclo_produccion(cliente_mqtt):
    global orden_arranque, modo_actual, punto_manual, tag_camara
    
    print(">> Moviendo a posición de espera (Home Joints)...")
    cliente_mqtt.publish(TOPIC_HMI, "Moviendo a posición de inicio...")
    robot.move_joints(*home_joints)
    
    while True:
        # --- ESTADO DE ESPERA & TELEMETRÍA CONTINUA ---
        if not orden_arranque:
            enviar_telemetria(cliente_mqtt, robot)
            time.sleep(0.5)
            continue
            
        # --- MODO AUTOMÁTICO ---
        if modo_actual == "auto":
            if tag_camara:
                print(f">> [AUTO] Iniciando recolección detectada por cámara en: {tag_camara}")
                ejecutar_movimiento(tag_camara, cliente_mqtt)
                tag_camara = None # Limpiamos la memoria para esperar el siguiente objeto
            else:
                cliente_mqtt.publish(TOPIC_HMI, "Modo Auto: Esperando detección de cámara...")
                time.sleep(0.5)
            
        # --- MODO MANUAL ---
        elif modo_actual == "manual":
            if punto_manual in ["Pick_1", "Pick_2", "Pick_3"]:
                print(f">> [MANUAL] Ejecutando orden del operador hacia: {punto_manual}")
                ejecutar_movimiento(punto_manual, cliente_mqtt)
                
                cliente_mqtt.publish(TOPIC_HMI, "Ciclo Manual finalizado. Esperando órdenes...")
                print(f">> Ciclo Manual completado.")
                
                punto_manual = None 
                orden_arranque = False # En manual, exigimos presionar START de nuevo
            else:
                cliente_mqtt.publish(TOPIC_HMI, "Modo manual: Esperando que elijas un punto...")
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
TOPIC_MODO = "niryo/control/modo"
TOPIC_PUNTO = "niryo/control/punto"
TOPIC_HMI = "niryo/hmi/estado"
TOPIC_TELEMETRIA = "niryo/robot/coordenadas" 

# Variables Globales de Estado
orden_arranque = False
modo_actual = "manual"
punto_manual = None

# ==========================================
# FUNCIONES MQTT
# ==========================================
def al_conectar(client, userdata, flags, rc):
    print("[MQTT] Conectado al broker de Node-RED.")
    client.subscribe([(TOPIC_CONTROL, 0), (TOPIC_MODO, 0), (TOPIC_PUNTO, 0)])

def al_recibir_mensaje(client, userdata, msg):
    global orden_arranque, modo_actual, punto_manual
    topico = msg.topic
    mensaje = msg.payload.decode("utf-8").strip().lower()

    if topico == TOPIC_CONTROL:
        if mensaje in ["true", "start"]:
            orden_arranque = True
            client.publish(TOPIC_HMI, f"Orden recibida. Ciclo en modo: {modo_actual.upper()}")
        elif mensaje == "stop":
            orden_arranque = False
            client.publish(TOPIC_HMI, "¡ALERTA! Paro de Emergencia.")
            try: robot.stop_move()
            except: pass
            
    elif topico == TOPIC_MODO:
        modo_actual = mensaje
        client.publish(TOPIC_HMI, f"Modo cambiado a: {modo_actual.upper()}")
        print(f">> Modo de operación: {modo_actual.upper()}")
        
    elif topico == TOPIC_PUNTO:
        punto_manual = mensaje
        if punto_manual == "manual": return # Filtro de seguridad
        client.publish(TOPIC_HMI, f"Punto manual seleccionado: {punto_manual}")
        print(f">> Punto objetivo manual: {punto_manual}")

# ==========================================
# INICIALIZACIÓN DEL ROBOT Y POSICIONES
# ==========================================
robot = NiryoRobot(IP_ROBOT)
print(f"Conectando al robot en {IP_ROBOT}...")

# 1. Limpiamos cualquier colisión residual por los crasheos anteriores
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
    place_pos = puntos_guardados["Place_Pos"]
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
    
    # 1. PICK (Directo al punto, pick_from_pose maneja su propia aproximación)
    cliente_mqtt.publish(TOPIC_HMI, f"Efectuando agarre en: {id_punto}")
    print(f">> Moviendo a la pose física asignada para {id_punto}...")
    robot.pick_from_pose(*pose_objetivo)
    
    # 2. ENCLAVAMIENTO SENSOR IR
    cliente_mqtt.publish(TOPIC_HMI, "Evaluando zona de entrega...")
    robot.set_pin_mode(PIN_SENSOR_IR, PinMode.INPUT)
    
    while robot.digital_read(PIN_SENSOR_IR) == PinState.LOW:
        alerta = "ZONA OCUPADA. Por favor, retire el objeto del Place."
        print(f"[!] {alerta}")
        cliente_mqtt.publish(TOPIC_HMI, alerta)
        time.sleep(2)
      
    # 3. PLACE (Directo, place_from_pose maneja su propia aproximación vertical)
    cliente_mqtt.publish(TOPIC_HMI, "Zona despejada. Entregando objeto...")
    print(">> Moviendo a la zona de entrega...")
    robot.place_from_pose(*place_pos)
    
    # --- 4. TRANSICIÓN SEGURA ---
    # Inmediatamente después de soltar, subimos a la postura segura libre de colisiones
    cliente_mqtt.publish(TOPIC_HMI, "Objeto entregado. Retornando a posición segura...")
    print(">> Retornando a la posición de espera (Home Joints)...")
    robot.move_joints(*home_joints)

# ==========================================
# LÓGICA PRINCIPAL (CEREBRO MÁQUINA DE ESTADOS)
# ==========================================
def ciclo_produccion(cliente_mqtt):
    global orden_arranque, modo_actual, punto_manual
    
    print(">> Moviendo a posición de espera (Home Joints)...")
    cliente_mqtt.publish(TOPIC_HMI, "Moviendo a posición de inicio...")
    robot.move_joints(*home_joints)
    
    while True:
        # --- ESTADO DE ESPERA & TELEMETRÍA OPTIMIZADA ---
        if not orden_arranque:
            # Solo consultamos la telemetría cuando el brazo no está ejecutando rutinas
            try:
                pose_actual = robot.get_pose()
                telemetria = f"X: {pose_actual.x:.3f} | Y: {pose_actual.y:.3f} | Z: {pose_actual.z:.3f} | Yaw: {pose_actual.yaw:.3f}"
                cliente_mqtt.publish(TOPIC_TELEMETRIA, telemetria)
            except Exception:
                pass 
            
            time.sleep(0.5)
            continue
            
        # --- MODO AUTOMÁTICO ---
        if modo_actual == "auto":
            for punto in ["Pick_1", "Pick_2", "Pick_3"]:
                if not orden_arranque: break 
                ejecutar_movimiento(punto, cliente_mqtt)
            
            cliente_mqtt.publish(TOPIC_HMI, "Ciclo Automático finalizado. Esperando órdenes...")
            print(">> Ciclo Automático completado.")
            orden_arranque = False
            
        # --- MODO MANUAL ---
        elif modo_actual == "manual":
            if punto_manual in ["Pick_1", "Pick_2", "Pick_3"]:
                ejecutar_movimiento(punto_manual, cliente_mqtt)
                
                cliente_mqtt.publish(TOPIC_HMI, "Ciclo Manual finalizado. Esperando órdenes...")
                print(f">> Ciclo Manual ({punto_manual}) completado.")
                
                punto_manual = None 
                orden_arranque = False
            else:
                cliente_mqtt.publish(TOPIC_HMI, "Modo manual: Esperando que elijas un punto...")
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
