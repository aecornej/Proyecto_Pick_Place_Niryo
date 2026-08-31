import paho.mqtt.client as mqtt

# --- Configuración MQTT ---
BROKER = "127.0.0.1"
TOPIC_CONTROL = "niryo/control/iniciar"

# Esta función se ejecuta automáticamente cuando llega un mensaje
def al_recibir_mensaje(client, userdata, msg):
    mensaje = msg.payload.decode("utf-8")
    if mensaje == "true":
        print("\n[!] ORDEN RECIBIDA: 'Alexa, inicia el ensamblaje'")
        print("--> Iniciando cámara...")
        print("--> Buscando coordenadas del cubo rojo...")
        # Aquí insertaremos la lógica de OpenCV y PyNiryo más adelante

# Configurar el cliente MQTT
cliente = mqtt.Client("Cerebro_Niryo")
cliente.on_message = al_recibir_mensaje

try:
    cliente.connect(BROKER, 1883, 60)
    cliente.subscribe(TOPIC_CONTROL)
    print("Cerebro Maestro iniciado. Esperando orden de voz (o botón de Node-RED)...")
    
    # Mantener el script corriendo y escuchando para siempre
    cliente.loop_forever()
    
except Exception as e:
    print(f"Error de conexión: {e}")
