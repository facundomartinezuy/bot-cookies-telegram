import os
import sqlite3
import zipfile
import io
import telebot
from flask import Flask, request

# Configuración del bot mediante variable de entorno
TOKEN = os.environ.get('BOT_TOKEN')
if not TOKEN:
    raise ValueError("Falta la variable de entorno BOT_TOKEN")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Base de datos SQLite temporal compatible con entornos cloud
DB_PATH = '/tmp/cookies.db'

def inicializar_db():
    conexion = sqlite3.connect(DB_PATH)
    cursor = conexion.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cookies (
            user_id TEXT,
            nombre TEXT,
            contenido TEXT
        )
    ''')
    conexion.commit()
    conexion.close()

inicializar_db()

# --- COMANDOS DEL BOT ---

@bot.message_handler(commands=['start'])
def enviar_bienvenida(message):
    bot.reply_to(
        message,
        "🤖 *Bot de Almacenamiento de Cookies*\n\n"
        "Comandos disponibles:\n"
        "• `/guardar Sitio | contenido` — Guarda una cookie.\n"
        "• `/listar` — Muestra los sitios registrados.\n"
        "• `/obtener Sitio` — Muestra una cookie específica.\n"
        "• `/exportar txt` — Descarga tus cookies en archivos de texto.\n"
        "• `/exportar zip` — Descarga todas tus cookies comprimidas en un ZIP.",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['guardar'])
def guardar_cookie(message):
    texto = message.text.replace('/guardar', '').strip()
    partes = texto.split('|')

    if len(partes) < 2:
        bot.reply_to(message, "⚠️ Formato incorrecto. Usa: `/guardar Netflix | sessionid=123`", parse_mode="Markdown")
        return

    nombre = partes[0].strip()
    contenido = partes[1].strip()
    user_id = str(message.from_user.id)

    conexion = sqlite3.connect(DB_PATH)
    cursor = conexion.cursor()
    cursor.execute("INSERT INTO cookies (user_id, nombre, contenido) VALUES (?, ?, ?)", (user_id, nombre, contenido))
    conexion.commit()
    conexion.close()

    bot.reply_to(message, f"✅ Cookie guardada exitosamente para *{nombre}*.", parse_mode="Markdown")

@bot.message_handler(commands=['listar'])
def listar_cookies(message):
    user_id = str(message.from_user.id)

    conexion = sqlite3.connect(DB_PATH)
    cursor = conexion.cursor()
    cursor.execute("SELECT nombre FROM cookies WHERE user_id = ?", (user_id,))
    resultados = cursor.fetchall()
    conexion.close()

    if not resultados:
        bot.reply_to(message, "📭 No hay cookies almacenadas.")
        return

    respuesta = "📋 *Plataformas registradas:*\n\n"
    for idx, (nombre,) in enumerate(resultados, 1):
        respuesta += f"{idx}. *{nombre}*\n"
    
    respuesta += "\nUsa `/obtener [nombre]` para consultar el contenido."
    bot.reply_to(message, respuesta, parse_mode="Markdown")

@bot.message_handler(commands=['obtener'])
def obtener_cookie(message):
    user_id = str(message.from_user.id)
    busqueda = message.text.replace('/obtener', '').strip().lower()

    if not busqueda:
        bot.reply_to(message, "⚠️ Indica el nombre. Ejemplo: `/obtener Netflix`", parse_mode="Markdown")
        return

    conexion = sqlite3.connect(DB_PATH)
    cursor = conexion.cursor()
    cursor.execute("SELECT nombre, contenido FROM cookies WHERE user_id = ? AND LOWER(nombre) LIKE ?", (user_id, f"%{busqueda}%"))
    resultado = cursor.fetchone()
    conexion.close()

    if not resultado:
        bot.reply_to(message, f"❌ No se encontró ninguna cookie para '{busqueda}'.")
        return

    nombre, contenido = resultado
    bot.reply_to(message, f"🍪 *Cookie de {nombre}:*\n\n`{contenido}`", parse_mode="Markdown")

@bot.message_handler(commands=['exportar'])
def exportar_cookies(message):
    user_id = str(message.from_user.id)
    formato = message.text.replace('/exportar', '').strip().lower()

    conexion = sqlite3.connect(DB_PATH)
    cursor = conexion.cursor()
    cursor.execute("SELECT nombre, contenido FROM cookies WHERE user_id = ?", (user_id,))
    resultados = cursor.fetchall()
    conexion.close()

    if not resultados:
        bot.reply_to(message, "📭 No tienes cookies para exportar.")
        return

    if formato == 'zip':
        # Crear un archivo ZIP en memoria RAM
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for idx, (nombre, contenido) in enumerate(resultados, 1):
                # Limpiar nombre para evitar caracteres inválidos en archivos
                nombre_archivo = f"{idx}_{nombre.replace(' ', '_')}.txt"
                zf.writestr(nombre_archivo, contenido)
        
        memory_file.seek(0)
        bot.send_document(
            message.chat.id, 
            document=(f"cookies_{user_id}.zip", memory_file.read()),
            caption="📦 Archivo ZIP generado con todas tus cookies separadas en archivos .txt"
        )

    elif formato == 'txt':
        # Unir todas las cookies en un único archivo de texto plano
        texto_acumulado = ""
        for nombre, contenido in resultados:
            texto_acumulado += f"--- {nombre} ---\n{contenido}\n\n"
        
        documento_bytes = io.BytesIO(texto_acumulado.encode('utf-8'))
        bot.send_document(
            message.chat.id,
            document=(f"cookies_{user_id}.txt", documento_bytes.read()),
            caption="📄 Archivo de texto plano con tus cookies."
        )
    else:
        bot.reply_to(message, "⚠️ Elige un formato válido. Usa:\n• `/exportar zip`\n• `/exportar txt`", parse_mode="Markdown")

# --- WEBHOOK PARA RENDER ---

@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    else:
        return 'Invalid content type', 403

@app.route('/', methods=['GET'])
def index():
    return 'Bot activo y operando 24/7.', 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
