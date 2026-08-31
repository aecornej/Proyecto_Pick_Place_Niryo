import cv2
import numpy as np

def nothing(x):
    pass

# Reemplaza con la IP de tu app IP Webcam
URL = 'http://192.168.0.108:8080/video'
cap = cv2.VideoCapture(URL)

# Crear una ventana para los controles
cv2.namedWindow('Calibrador HSV')
cv2.resizeWindow('Calibrador HSV', 400, 250)

# Crear barras deslizantes para los límites inferior y superior (H, S, V)
cv2.createTrackbar('H Min', 'Calibrador HSV', 90, 179, nothing)
cv2.createTrackbar('S Min', 'Calibrador HSV', 100, 255, nothing)
cv2.createTrackbar('V Min', 'Calibrador HSV', 100, 255, nothing)
cv2.createTrackbar('H Max', 'Calibrador HSV', 140, 179, nothing)
cv2.createTrackbar('S Max', 'Calibrador HSV', 255, 255, nothing)
cv2.createTrackbar('V Max', 'Calibrador HSV', 255, 255, nothing)

print("Ajusta los valores hasta que el cubo sea blanco sólido y el fondo negro.")
print("Presiona 'q' para salir e imprimir tus valores finales.")

while True:
    ret, frame = cap.read()
    if not ret:
        break
        
    frame = cv2.resize(frame, (640, 480))
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    
    # Leer la posición actual de las barras deslizantes
    h_min = cv2.getTrackbarPos('H Min', 'Calibrador HSV')
    s_min = cv2.getTrackbarPos('S Min', 'Calibrador HSV')
    v_min = cv2.getTrackbarPos('V Min', 'Calibrador HSV')
    h_max = cv2.getTrackbarPos('H Max', 'Calibrador HSV')
    s_max = cv2.getTrackbarPos('S Max', 'Calibrador HSV')
    v_max = cv2.getTrackbarPos('V Max', 'Calibrador HSV')
    
    # Crear los arrays con los límites actuales
    lower = np.array([h_min, s_min, v_min])
    upper = np.array([h_max, s_max, v_max])
    
    # Aplicar la máscara
    mask = cv2.inRange(hsv, lower, upper)
    resultado = cv2.bitwise_and(frame, frame, mask=mask)
    
    # --- PARCHE PARA VER LOS VALORES EN PANTALLA ---
    texto_min = f"MIN -> H: {h_min} | S: {s_min} | V: {v_min}"
    texto_max = f"MAX -> H: {h_max} | S: {s_max} | V: {v_max}"
    
    # Dibuja texto negro con fondo para que resalte
    cv2.putText(frame, texto_min, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    cv2.putText(frame, texto_max, (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    
    # Mostrar ventanas
    cv2.imshow('Original', frame)
    cv2.imshow('Mascara (Blanco y Negro)', mask)
    cv2.imshow('Resultado Filtrado', resultado)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        print("\n--- VALORES FINALES PARA TU SCRIPT DE VISIÓN ---")
        print(f"lower_blue = np.array([{h_min}, {s_min}, {v_min}])")
        print(f"upper_blue = np.array([{h_max}, {s_max}, {v_max}])")
        break

cap.release()
cv2.destroyAllWindows()
