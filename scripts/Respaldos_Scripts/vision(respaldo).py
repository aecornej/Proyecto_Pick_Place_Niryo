import cv2
import numpy as np
import paho.mqtt.client as mqtt

# ------- Configuración MQTT -------
broker_address = "127.0.0.1"  # IP de tu Ubuntu (localhost)
topic_coordenadas = "niryo/vision/coord"
cliente_mqtt = mqtt.Client("Vision_Node")
try:
    cliente_mqtt.connect(broker_address, 1883, 60)
    print("Conectado exitosamente al broker MQTT local.")
except:
    print("Error: No se pudo conectar al broker MQTT. ¿Está corriendo Mosquitto?")
# ----------------------------------

# Dirección IP de la cámara
URL = 'http://172.20.157.84:8080/video' #'http://192.168.100.37:8080/video'
cap = cv2.VideoCapture(URL)

print("Iniciando conexión con la cámara...")

# Rango 1: Rojos bajos (0 a 10)
lower_red1 = np.array([0, 100, 100])
upper_red1 = np.array([6, 255, 255]) 
# Rango 2: Rojos altos (170 a 179)
lower_red2 = np.array([170, 110, 45])
upper_red2 = np.array([179, 255, 255])

while True:
    ret, frame = cap.read()
    if not ret:
        print("Error: No se pudo leer el flujo de video. Revisa la IP o tu conexión WiFi.")
        break
        
    # Redimensionar el cuadro para procesar más rápido
    frame = cv2.resize(frame, (640, 480))
    # Convertir el espacio de color de BGR a HSV
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    

    
    # Crear las dos máscaras
    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    
    # Juntar ambas máscaras para capturar todos los tonos de rojo
    mask = cv2.bitwise_or(mask1, mask2)
    
    # Encontrar los contornos usando la máscara combinada
    contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    if contours:
        # Tomar el contorno más grande (el objeto principal, ignorando ruidos)
        c = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(c)
        
        # Filtrar por tamaño para asegurar que no es una mancha o ruido de luz
        if area > 500:
            # Calcular el centroide (X, Y) matemáticamente
            M = cv2.moments(c)
            if M["m00"] != 0:
                cX = int(M["m10"] / M["m00"])
                cY = int(M["m01"] / M["m00"])
                
                # Dibujar un borde verde alrededor del objeto y un punto en el centro
                cv2.drawContours(frame, [c], -1, (0, 255, 0), 2)
                cv2.circle(frame, (cX, cY), 5, (255, 255, 255), -1)
                
                # Publicar las coordenadas por MQTT
                mensaje = f"{cX},{cY}"
                cliente_mqtt.publish(topic_coordenadas, mensaje)
                
                # Mostrar las coordenadas en la pantalla
                cv2.putText(frame, f"X: {cX} Y: {cY}", (cX - 30, cY - 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
                # Imprimir en terminal (esto es lo que se enviaría luego al robot)
                #print(f"Objeto objetivo detectado en --> X: {cX}, Y: {cY}")

    # Mostrar la ventana con la cámara original procesada
    cv2.imshow('Vision Niryo', frame)
    # Mostrar la máscara en blanco y negro (útil para calibrar colores)
    #cv2.imshow('Mascara de Color', mask)

    # Salir del programa presionando la tecla 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Limpiar y cerrar todo al salir
cap.release()
cv2.destroyAllWindows()
