import cv2
import numpy as np
import math
import paho.mqtt.client as mqtt
from flask import Flask, Response

# ------- Configuración MQTT -------
broker_address = "127.0.0.1"  
topic_coordenadas = "niryo/vision/coord"
cliente_mqtt = mqtt.Client("Vision_Node")
try:
    cliente_mqtt.connect(broker_address, 1883, 60)
    print("Conectado exitosamente al broker MQTT local.")
    
    cliente_mqtt.loop_start()
except:
    print("Error: No se pudo conectar al broker MQTT. ¿Está corriendo Mosquitto?")

# ------- Configuración Flask ------
app = Flask(__name__)

# ==========================================
# 1. SELECCIÓN DE CÁMARA 
# ==========================================
FUENTE_CAMARA = "USB"  # "IP" o "USB"
URL_IP = 'http://192.168.0.124:8080/video'	# IP de la cámara
PUERTO_USB = 1	# 0 si no se tiene cámara integrada (monitor), 1  si la tiene

if FUENTE_CAMARA == "IP":
    origen = URL_IP
elif FUENTE_CAMARA == "USB":
    origen = PUERTO_USB
else:
    print("Error: FUENTE_CAMARA no válida.")
    exit()

cap = cv2.VideoCapture(origen)

# ==========================================
# 2. CONFIGURACIÓN DE ZONAS (CALIBRACIÓN)
# ==========================================
# Anota aquí las coordenadas (X, Y) centrales de tus 3 cajas. 
# (He puesto valores de ejemplo basados en tu imagen)
ZONAS_RECOGIDA = {
    "Pick_1": (234, 234),	#"Pick_1": (260, 198), 
    "Pick_2": (370, 134),	#"Pick_2": (342, 326), 
    "Pick_3": (70, 166)		#"Pick_3": (370, 124)  
}
# Rango de seguridad en píxeles (tamaño del círculo de tolerancia)
RADIO_TOLERANCIA = 40

# Rangos de color (Rojo)
lower_red1 = np.array([0, 100, 100])
upper_red1 = np.array([6, 255, 255]) 
lower_red2 = np.array([170, 110, 45])
upper_red2 = np.array([179, 255, 255])

def generar_frames():
    while True:
        ret, frame = cap.read()
        if not ret: break
        
        frame = cv2.resize(frame, (640, 480))
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Dibujar gráficamente las 3 zonas de tolerancia en la cámara
        for nombre_zona, (zx, zy) in ZONAS_RECOGIDA.items():
            cv2.circle(frame, (zx, zy), RADIO_TOLERANCIA, (255, 0, 0), 2)
            cv2.putText(frame, nombre_zona, (zx - 25, zy - RADIO_TOLERANCIA - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        mask = cv2.bitwise_or(mask1, mask2)
        
        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            c = max(contours, key=cv2.contourArea)
            if cv2.contourArea(c) > 500:
                M = cv2.moments(c)
                if M["m00"] != 0:
                    cX = int(M["m10"] / M["m00"])
                    cY = int(M["m01"] / M["m00"])
                    
                    # Dibujar rastro del objeto detectado
                    cv2.drawContours(frame, [c], -1, (0, 255, 0), 2)
                    cv2.circle(frame, (cX, cY), 5, (255, 255, 255), -1)
                    
		    # --- REQUERIMIENTO 1: Mostrar solo X e Y ---
                    texto_pantalla = f"X:{cX} Y:{cY}"
                    cv2.putText(frame, texto_pantalla, (cX - 40, cY - 20), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 245, 255), 2)

                    # --- REQUERIMIENTOS 2 y 3: Evaluar zonas y enviar TAG ---
                    tag_detectado = None
                    for nombre_zona, (zx, zy) in ZONAS_RECOGIDA.items():
                        # Calcular distancia matemática entre el objeto y el centro de la zona
                        distancia = math.hypot(cX - zx, cY - zy)
                        if distancia <= RADIO_TOLERANCIA:
                            tag_detectado = nombre_zona
                            break
                    
                    if tag_detectado:
                        # Alerta visual en pantalla
                        cv2.putText(frame, f"OBJETO EN: {tag_detectado}", (20, 40), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                        # Enviar el TAG exacto por MQTT al robot
                        cliente_mqtt.publish(topic_coordenadas, tag_detectado)
                    else:
                        cv2.putText(frame, "Objeto fuera de rango", (20, 40), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generar_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    print("Iniciando servidor de video. Las zonas de recolección están activas.")
    app.run(host='0.0.0.0', port=5000, debug=False)
