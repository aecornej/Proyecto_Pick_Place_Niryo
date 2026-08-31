# Estación Pick & Place por Voz con Niryo One, OpenCV y Node-RED

Este repositorio contiene el código fuente y las configuraciones para operar una estación robótica automatizada utilizando un brazo **Niryo One**. El sistema integra visión artificial para la detección dinámica de piezas, comunicación MQTT para el control asíncrono, y un panel HMI basado en Node-RED que, ejecutándose en un entorno Windows y/o Ubuntu, facilita la integración con comandos de voz de Amazon Alexa.

## 📁 Estructura del Repositorio

*   **`/scripts`**: Contiene la lógica central en Python.
    *   `Robotcito.py`: Script principal del robot. Maneja la máquina de estados (Automático/Manual), la conexión MQTT y la ejecución de trayectorias (mediante interpolación de joints para evitar conflictos de cinemática inversa local).
    *   `vision.py`: Servidor de visión usando OpenCV y Flask. Detecta objetos por color (HSV), valida zonas de trabajo y emite coordenadas al robot vía MQTT.
    *   `calibrar_color.py` / `calibracion_puntos.py`: Herramientas auxiliares para sintonizar los rangos HSV y guardar los puntos físicos en el espacio de trabajo.
    *   `coordenadas_niryo.json`: Archivo de configuración generado dinámicamente que almacena los ángulos articulares (Joints) y poses cartesianas de los puntos de recolección y entrega.
*   **`/FlujosNodeRed`**: Archivos `.json` exportados desde Node-RED. Contienen el diseño del HMI (Dashboard oscuro) y los nodos de interconexión para emular dispositivos Alexa.
*   **`/resources`**: Documentación de apoyo, incluyendo la guía de configuración de Node-RED para entornos Windows y respaldos de calibración.

## 🛠️ Requisitos y Dependencias

Para la ejecución del control robótico y la visión en el equipo principal (Linux/Ubuntu), se requiere un entorno de Python con:

"ini_bash"
pip install pyniryo paho-mqtt opencv-python flask numpy
"end_bash"

**Nota sobre Node-RED e integración con Alexa:**
Debido a las restricciones de los portales cautivos en redes educativas, el módulo de Node-RED encargado de emular el dispositivo para Amazon Alexa (nodos `amazon-echo-device`) está diseñado para ejecutarse en una **laptop con Windows** conectada a un punto de acceso sin restricciones, comunicándose remotamente con el broker MQTT.

## 🚀 Puesta en Marcha

1.  **Iniciar Broker MQTT:**
    Asegúrate de tener Mosquitto ejecutándose en la máquina host que actuará como servidor.
2.  **Lanzar el Servidor de Visión:**
    Abre una terminal, activa tu entorno virtual y ejecuta:
    "ini_bash"
    cd scripts
    python vision.py
    "end_bash"
    *El stream de video estará disponible en el puerto 5000 para ser consumido por el HMI.*
3.  **Iniciar el Control del Niryo One:**
    Con el robot encendido e IP configurada (`192.168.0.100`), ejecuta:
    "ini_bash"
    python Robotcito.py
    "end_bash"
    *El brazo realizará su calibración inicial y pasará a estado de espera (Home).*
4.  **Desplegar HMI:**
    En la instancia de Node-RED (Windows), importa el archivo `FlujoActual.json` ubicado en la carpeta `/FlujosNodeRed`, ajusta la IP del broker MQTT si es necesario, y haz clic en *Deploy*.

## ⚙️ Modos de Operación

*   **Automático:** El brazo se mantiene a la espera de un evento de visión. Si `vision.py` detecta un objeto válido dentro del radio de tolerancia de una zona de *Pick*, el robot interrumpe la espera y ejecuta la trayectoria.
*   **Manual:** El operador puede forzar rutinas de recolección hacia los puntos predefinidos usando los botones del Dashboard de Node-RED, e incluye un sensor infrarrojo analógico (Pin 1A) para enclavamiento de seguridad si la zona de *Place* se encuentra ocupada.
