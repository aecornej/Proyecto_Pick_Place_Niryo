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

```bash
pip install pyniryo paho-mqtt opencv-python flask numpy
```

**Nota sobre Node-RED e integración con Alexa:**
Debido a las restricciones de los portales cautivos en redes educativas, el módulo de Node-RED encargado de emular el dispositivo para Amazon Alexa (nodos `amazon-echo-device`) está diseñado para ejecutarse en una **laptop con Windows** conectada a un punto de acceso sin restricciones, comunicándose remotamente con el broker MQTT.

## 🚀 Puesta en Marcha

El proyecto es de naturaleza multiplataforma. Siempre que se cuente con las dependencias instaladas (Python, Mosquitto MQTT y Node-RED), los nodos de visión, el control del robot y el HMI pueden ejecutarse indistintamente en Linux o Windows.

A continuación, los pasos para inicializar el sistema en cada entorno:

### 🐧 Opción A: Despliegue en Ubuntu / Linux

1. **Iniciar Broker MQTT:**
   Asegúrate de que el servicio de Mosquitto esté corriendo en segundo plano:
```bash
   sudo systemctl start mosquitto
```
2. **Lanzar el Servidor de Visión:**
   Abre una terminal, ubícate en la carpeta del proyecto y ejecuta el script de visión (si usas un entorno virtual, actívalo primero):
```bash
   cd scripts
   python3 vision.py
```
   *El stream de video estará disponible en `http://localhost:5000/video_feed`.*
3. **Iniciar el Control del Niryo One:**
   Abre otra terminal y ejecuta la máquina de estados del robot:
```bash
   cd scripts
   python3 Robotcito.py
```
4. **Desplegar HMI en Node-RED:**
   En una nueva terminal, inicia el servidor de Node-RED ejecutando el comando `node-red`. Abre el navegador en `http://localhost:1880`, importa el archivo `FlujoActual.json` ubicado en `/FlujosNodeRed` y haz clic en *Deploy*.

---

### 🪟 Opción B: Despliegue en Windows
*(Recomendado si se desea habilitar la integración nativa con Amazon Alexa evadiendo restricciones de red mediante un hotspot local)*

1. **Iniciar Broker MQTT:**
   Abre el menú de inicio, busca "Servicios" (Services), localiza `Mosquitto Broker` y asegúrate de que su estado sea "En ejecución". (Alternativamente, ejecútalo desde su carpeta de instalación en CMD).
2. **Lanzar Scripts de Python (Visión y Robot):**
   Abre la consola Símbolo del Sistema (CMD) o PowerShell. Navega hasta la carpeta del proyecto e inicia los scripts en ventanas separadas:
```bash
   cd ruta\hacia\Proyecto_Niryo\scripts
   python vision.py
```
   
   En otra ventana de CMD:
```bash
   cd ruta\hacia\Proyecto_Niryo\scripts
   python Robotcito.py
```
3. **Desplegar HMI y Nodos de Alexa:**
   Abre CMD y ejecuta el comando `node-red`. Luego, ingresa a `http://localhost:1880` desde tu navegador. Importa el archivo `FlujoActual.json` (o cualquier archivo de respaldo en `/FlujosNodeRed`), configura la IP del broker MQTT y presiona *Deploy*. El nodo `amazon-echo-device` quedará visible en la red local para ser descubierto por tu dispositivo Echo Show.

## ⚙️ Modos de Operación

*   **Automático:** El brazo se mantiene a la espera de un evento de visión. Si `vision.py` detecta un objeto válido dentro del radio de tolerancia de una zona de *Pick*, el robot interrumpe la espera y ejecuta la trayectoria.
*   **Manual:** El operador puede forzar rutinas de recolección hacia los puntos predefinidos usando los botones del Dashboard de Node-RED, e incluye un sensor infrarrojo analógico (Pin 1A) para enclavamiento de seguridad si la zona de *Place* se encuentra ocupada.
