"""
Bot de Telegram - Tienda de Pulseras
---------------------------------------------------------------------------
- /start: se borra el mensaje anterior del bot y el propio /start para que
  el chat quede limpio. Si la sesión está activa, entra directo al menú.
  Si no, ofrece "🆕 Crear cuenta" o "🔑 Iniciar sesión".
- Registro: nombre de usuario -> (admin: contraseña / normal: escribir el
  teléfono con prefijo de país, ej. +34612345678) -> el bot envía un código
  de verificación (3 letras mayúsculas + 3 números, aleatorio) que hay que
  escribir para confirmar -> se borra el código y se muestra el menú.
- 🚪 Cerrar sesión: disponible para cliente y admin. Al cerrar sesión hay
  que volver a iniciar sesión (usuario + teléfono, o contraseña si es admin).
- Admin: puede ver la lista de usuarios (SIN el teléfono) y añadir productos
  (nombre, precio, foto - se recorta automáticamente a cuadrado 1:1).
- Los clientes solo pueden usar el chat de texto / los botones: no se
  aceptan fotos ni archivos de su parte.
- Ubicación: validación silenciosa contra el radio de Vinaròs (1 km).
- Nota: Telegram no permite a un bot impedir que un usuario borre su propio
  chat; eso lo controla el cliente de Telegram de cada persona, no el bot.

Variables de entorno necesarias:
    BOT_TOKEN        -> token de @BotFather
    PROVIDER_TOKEN    -> token de pagos (Stripe u otra pasarela)
    ADMIN_USERNAME    -> nombre de usuario del admin (ej. cristiancocinero15)
    ADMIN_PASSWORD    -> contraseña del admin (NUNCA la subas al código/GitHub)
"""

import asyncio
import io
import logging
import math
import os
import random
import re
import string

from PIL import Image
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    LabeledPrice,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

import db

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
PROVIDER_TOKEN = os.environ.get("PROVIDER_TOKEN", "")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "cristiancocinero15")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
CONTACTO_TELEFONO = "+34 614378910"

# Segundo bot (solo para mandar el código de verificación)
SMS_BOT_TOKEN = os.environ.get("SMS_BOT_TOKEN", "")
SMS_BOT_USERNAME = os.environ.get("SMS_BOT_USERNAME", "SMSTienda_bot")

IMG_DIR = os.path.join(os.path.dirname(__file__), "imagenes")
os.makedirs(IMG_DIR, exist_ok=True)

VINAROS_LAT = 40.4676
VINAROS_LON = 0.4753
RADIO_MAXIMO_KM = 1.0

TELEFONO_REGEX = re.compile(r"^\+\d{8,15}$")

# Estados de conversación
(CHOOSE_ACCION, ASK_USERNAME, ASK_PASSWORD_ADMIN, CONFIRM_ALT_USERNAME,
 ASK_PHONE, CONFIRM_PHONE, ADMIN_NOMBRE, ADMIN_CATEGORIA, ADMIN_PRECIO, ADMIN_FOTO) = range(10)


# ---------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------

def distancia_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def recortar_cuadrada(datos: bytes) -> bytes:
    """Recorta la imagen al centro para que quede cuadrada (1:1)."""
    img = Image.open(io.BytesIO(datos)).convert("RGB")
    w, h = img.size
    lado = min(w, h)
    izq = (w - lado) // 2
    arriba = (h - lado) // 2
    recorte = img.crop((izq, arriba, izq + lado, arriba + lado))
    salida = io.BytesIO()
    recorte.save(salida, format="JPEG", quality=90)
    return salida.getvalue()


def generar_codigo_verificacion() -> str:
    """Código de verificación: 3 letras mayúsculas + 3 números, aleatorio."""
    letras = "".join(random.choices(string.ascii_uppercase, k=3))
    numeros = "".join(random.choices(string.digits, k=3))
    return letras + numeros


def get_cart(context: ContextTypes.DEFAULT_TYPE) -> dict:
    if "cart" not in context.user_data:
        context.user_data["cart"] = {}
    return context.user_data["cart"]


def cart_total(cart: dict) -> float:
    total = 0.0
    for pid, qty in cart.items():
        prod = db.get_product(int(pid))
        if prod:
            total += prod["precio"] * qty
    return total


def menu_principal_kb(es_admin: bool) -> InlineKeyboardMarkup:
    filas = [
        [InlineKeyboardButton("🎨 Ver catálogo", callback_data="ver_catalogo")],
        [InlineKeyboardButton("🛒 Carrito", callback_data="ver_carrito")],
        [InlineKeyboardButton("📞 Contacto", callback_data="ver_contacto")],
    ]
    if es_admin:
        filas.append([InlineKeyboardButton("➕ Añadir producto (admin)", callback_data="admin_add")])
        filas.append([InlineKeyboardButton("👥 Ver usuarios (admin)", callback_data="admin_usuarios")])
    filas.append([InlineKeyboardButton("🚪 Cerrar sesión", callback_data="cerrar_sesion")])
    return InlineKeyboardMarkup(filas)


async def enviar_menu(chat_id, context, es_admin, saludo=""):
    """Envía el menú como mensaje NUEVO (se usa cuando no hay un mensaje de callback que editar)."""
    texto = (saludo + "\n\n¿Qué quieres hacer?") if saludo else "¿Qué quieres hacer?"
    msg = await context.bot.send_message(chat_id, texto, reply_markup=menu_principal_kb(es_admin))
    context.user_data["last_menu_msg_id"] = msg.message_id


async def editar_a_menu(query, es_admin, saludo=""):
    """Convierte el mensaje del botón pulsado directamente en el menú (evita mandar mensajes de más)."""
    texto = (saludo + "\n\n¿Qué quieres hacer?") if saludo else "¿Qué quieres hacer?"
    try:
        await query.edit_message_text(texto, reply_markup=menu_principal_kb(es_admin))
    except Exception:
        await query.message.reply_text(texto, reply_markup=menu_principal_kb(es_admin))


# ---------------------------------------------------------------------
# Login / registro (/start)
# ---------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Limpieza: se borra el mensaje anterior del bot (menú/código, etc.) y el propio /start.
    ultimo_msg_id = context.user_data.get("last_menu_msg_id")
    if ultimo_msg_id:
        try:
            await context.bot.delete_message(chat_id, ultimo_msg_id)
        except Exception:
            pass
    try:
        await update.message.delete()
    except Exception:
        pass

    usuario = db.get_user(telegram_id)

    if usuario:
        await enviar_menu(
            chat_id, context, bool(usuario["is_admin"]),
            f"👋 ¡Hola de nuevo, {usuario['username']}!",
        )
        return ConversationHandler.END

    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🆕 Crear cuenta", callback_data="accion_crear")],
            [InlineKeyboardButton("🔑 Iniciar sesión", callback_data="accion_login")],
        ]
    )
    msg = await context.bot.send_message(
        chat_id,
        "👋 Bienvenido a *Tienda de Pulseras*.\n\n¿Ya tienes cuenta o eres nuevo?",
        parse_mode="Markdown",
        reply_markup=kb,
    )
    context.user_data["last_menu_msg_id"] = msg.message_id
    return CHOOSE_ACCION


async def elegir_accion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["auth_purpose"] = "signup" if query.data == "accion_crear" else "login"
    await query.edit_message_text("Escribe tu nombre de usuario:")
    return ASK_USERNAME


async def recibir_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip()
    purpose = context.user_data.get("auth_purpose", "signup")
    context.user_data["pending_username"] = username
    chat_id = update.effective_chat.id

    try:
        await update.message.delete()
    except Exception:
        pass

    if username == ADMIN_USERNAME:
        if not ADMIN_PASSWORD:
            await context.bot.send_message(
                chat_id, "⚠️ El admin todavía no ha configurado la contraseña (ADMIN_PASSWORD)."
            )
            return ConversationHandler.END
        await context.bot.send_message(chat_id, "🔒 Ese usuario es el admin. Escribe la contraseña:")
        return ASK_PASSWORD_ADMIN

    if purpose == "login":
        usuario = db.get_user_by_username(username)
        if not usuario:
            await context.bot.send_message(
                chat_id,
                "No existe ninguna cuenta con ese nombre. Si eres nuevo, escribe /start "
                "y elige '🆕 Crear cuenta'.",
            )
            return ConversationHandler.END
        await context.bot.send_message(
            chat_id, "Escribe tu número de teléfono con el prefijo de país (ej: +34612345678):"
        )
        return ASK_PHONE

    if db.username_exists(username):
        sugerido = db.sugerir_username_libre(username)
        context.user_data["pending_username"] = sugerido
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(f"✅ Usar {sugerido}", callback_data="alt_si")],
                [InlineKeyboardButton("❌ No, prefiero otro", callback_data="alt_no")],
            ]
        )
        await context.bot.send_message(
            chat_id,
            f"Ese nombre ya está en uso. ¿Te vale *{sugerido}*?",
            parse_mode="Markdown",
            reply_markup=kb,
        )
        return CONFIRM_ALT_USERNAME

    await context.bot.send_message(
        chat_id, "Escribe tu número de teléfono con el prefijo de país (ej: +34612345678):"
    )
    return ASK_PHONE


async def recibir_password_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text
    telegram_id = update.effective_user.id
    chat_id = update.effective_chat.id

    try:
        await update.message.delete()
    except Exception:
        pass

    if password != ADMIN_PASSWORD:
        await context.bot.send_message(chat_id, "❌ Contraseña incorrecta. Escribe /start para volver a intentarlo.")
        return ConversationHandler.END

    existente = db.get_user_by_username(ADMIN_USERNAME)
    if existente:
        db.update_telegram_id(ADMIN_USERNAME, telegram_id)
    else:
        db.create_user(telegram_id, ADMIN_USERNAME, phone_number=None, is_admin=True)

    await enviar_menu(chat_id, context, True, "✅ Acceso de admin concedido.")
    return ConversationHandler.END


async def confirmar_username_alternativo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "alt_si":
        await query.edit_message_text(
            "Escribe tu número de teléfono con el prefijo de país (ej: +34612345678):"
        )
        return ASK_PHONE

    await query.edit_message_text(
        "De acuerdo, no se ha creado el usuario. Contacta con el admin "
        f"(@{ADMIN_USERNAME} · ☎️ {CONTACTO_TELEFONO}) para que te asigne uno. "
        "Cuando lo tengas, escribe /start otra vez."
    )
    return ConversationHandler.END


async def enviar_solicitud_codigo(chat_id, context, telegram_id, purpose=None, username=None, telefono=None):
    """Genera un código nuevo, invalida el anterior, y manda el botón + instrucción clara."""
    codigo = generar_codigo_verificacion()
    db.set_pendiente(telegram_id, codigo, purpose=purpose, username=username, telefono=telefono)

    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("📲 Ir a verificar", url=f"https://t.me/{SMS_BOT_USERNAME}?start=verificar")]]
    )
    msg = await context.bot.send_message(
        chat_id,
        f"Pulsa el botón para hablar con @{SMS_BOT_USERNAME} y dale a *Iniciar* — te mandará tu código.\n\n"
        "✍️ Introduce aquí el código para verificar, o escribe `/sync CÓDIGO` en @"
        f"{SMS_BOT_USERNAME} para verificarlo allí mismo.",
        parse_mode="Markdown",
        reply_markup=kb,
    )
    context.user_data["code_msg_id"] = msg.message_id
    db.set_mensaje_tienda(telegram_id, msg.message_id)


async def recibir_telefono(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telefono = update.message.text.strip().replace(" ", "")
    chat_id = update.effective_chat.id
    telegram_id = update.effective_user.id

    if not TELEFONO_REGEX.match(telefono):
        await update.message.reply_text(
            "Formato no válido. Escríbelo con el prefijo de país, ej: +34612345678"
        )
        return ASK_PHONE

    try:
        await update.message.delete()
    except Exception:
        pass

    context.user_data["pending_phone"] = telefono
    purpose = context.user_data.get("auth_purpose", "signup")
    username = context.user_data.get("pending_username")
    await enviar_solicitud_codigo(chat_id, context, telegram_id, purpose, username, telefono)
    return CONFIRM_PHONE


async def completar_verificacion(telegram_id: int, pendiente: dict):
    """Crea la cuenta (signup) o mueve la sesión (login) usando los datos guardados
    en 'pendiente'. No depende de ningún bot en concreto, así la usan tanto el bot
    de la tienda como @SMSTienda_bot (comando /sync).
    Devuelve (ok, mensaje, es_admin)."""
    purpose = pendiente.get("purpose") or "signup"
    username = pendiente.get("username")
    telefono = pendiente.get("telefono")

    if purpose == "login":
        usuario = db.get_user_by_username(username)
        if usuario and usuario["phone_number"] == telefono:
            db.update_telegram_id(username, telegram_id)
            return True, "✅ Número verificado. Sesión iniciada.", bool(usuario["is_admin"])
        return False, (
            "❌ Ese número no coincide con el registrado para esa cuenta. "
            f"Contacta con el admin (☎️ {CONTACTO_TELEFONO}) si necesitas ayuda."
        ), False

    db.create_user(telegram_id, username, phone_number=telefono, is_admin=False)
    return True, f"✅ Usuario *{username}* creado.", False


async def enviar_menu_bot(bot, chat_id, es_admin, saludo=""):
    """Igual que enviar_menu, pero recibe directamente el objeto 'bot' (para poder
    llamarse desde el otro bot, @SMSTienda_bot, tras completar /sync)."""
    texto = (saludo + "\n\n¿Qué quieres hacer?") if saludo else "¿Qué quieres hacer?"
    return await bot.send_message(chat_id, texto, reply_markup=menu_principal_kb(es_admin))


async def confirmar_codigo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    codigo_escrito = update.message.text.strip().upper()
    telegram_id = update.effective_user.id
    pendiente = db.get_pendiente(telegram_id)
    chat_id = update.effective_chat.id

    try:
        await update.message.delete()
    except Exception:
        pass

    if not pendiente or codigo_escrito != pendiente["codigo"]:
        # Código incorrecto o caducado: se invalida y se genera uno nuevo automáticamente.
        code_msg_id = context.user_data.get("code_msg_id")
        if code_msg_id:
            try:
                await context.bot.delete_message(chat_id, code_msg_id)
            except Exception:
                pass
        await context.bot.send_message(chat_id, "❌ Código incorrecto. Te hemos generado uno nuevo:")
        await enviar_solicitud_codigo(chat_id, context, telegram_id)
        return CONFIRM_PHONE

    ok, mensaje_resultado, es_admin_flag = await completar_verificacion(telegram_id, pendiente)

    mensaje_id_sms = pendiente.get("mensaje_id_sms")
    db.borrar_pendiente(telegram_id)

    # Limpieza: se borra el mensaje con el botón de verificar (bot principal)...
    code_msg_id = context.user_data.get("code_msg_id")
    if code_msg_id:
        try:
            await context.bot.delete_message(chat_id, code_msg_id)
        except Exception:
            pass

    # ...y el mensaje con el código que mandó el bot temporal (@SMSTienda_bot).
    if mensaje_id_sms and SMS_BOT_APP:
        try:
            await SMS_BOT_APP.bot.delete_message(telegram_id, mensaje_id_sms)
        except Exception:
            pass

    if not ok:
        await context.bot.send_message(chat_id, mensaje_resultado)
        return ConversationHandler.END

    await enviar_menu(chat_id, context, es_admin_flag, mensaje_resultado)
    return ConversationHandler.END


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operación cancelada.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# ---------------------------------------------------------------------
# Cerrar sesión
# ---------------------------------------------------------------------

async def cerrar_sesion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Sesión cerrada")
    db.set_activa(update.effective_user.id, False)
    context.user_data.clear()
    await query.edit_message_text(
        "🚪 Sesión cerrada. Escribe /start cuando quieras volver a entrar."
    )


# ---------------------------------------------------------------------
# Catálogo / carrito
# ---------------------------------------------------------------------

async def mostrar_catalogo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    categorias = db.get_categories()
    if not categorias:
        kb_vacio = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menú", callback_data="volver_menu")]])
        await query.edit_message_text("Todavía no hay productos en el catálogo.", reply_markup=kb_vacio)
        return

    if len(categorias) == 1:
        await mostrar_productos_de_categoria(query, context, categorias[0])
        return

    botones = [[InlineKeyboardButton(c, callback_data=f"catview_{c}")] for c in categorias]
    botones.append([InlineKeyboardButton("🗂️ Ver todo", callback_data="catview_todas")])
    botones.append([InlineKeyboardButton("⬅️ Menú", callback_data="volver_menu")])
    await query.edit_message_text("¿Qué categoría quieres ver?", reply_markup=InlineKeyboardMarkup(botones))


async def elegir_categoria_catalogo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    categoria = query.data.replace("catview_", "")
    await mostrar_productos_de_categoria(query, context, None if categoria == "todas" else categoria)


async def mostrar_productos_de_categoria(query, context, categoria):
    chat_id = query.message.chat_id
    productos = db.get_products(categoria)

    if not productos:
        kb_vacio = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menú", callback_data="volver_menu")]])
        await query.edit_message_text("No hay productos en esta categoría.", reply_markup=kb_vacio)
        return

    titulo = f"Categoría: {categoria}" if categoria else "Todo el catálogo"
    await query.edit_message_text(f"{titulo} 👇")
    for prod in productos:
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton(f"➕ Añadir · {prod['precio']:.2f}€", callback_data=f"add_{prod['id']}")]]
        )
        with open(prod["imagen"], "rb") as foto:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=foto,
                caption=f"*{prod['nombre']}*\n{prod['categoria']} · {prod['precio']:.2f}€",
                parse_mode="Markdown",
                reply_markup=kb,
            )
    kb_final = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🛒 Ver carrito", callback_data="ver_carrito")],
            [InlineKeyboardButton("⬅️ Menú", callback_data="volver_menu")],
        ]
    )
    await context.bot.send_message(chat_id, "Cuando termines, pulsa 🛒 para ver tu carrito.", reply_markup=kb_final)




async def anadir_al_carrito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    pid = query.data.replace("add_", "")
    cart = get_cart(context)
    cart[pid] = cart.get(pid, 0) + 1
    prod = db.get_product(int(pid))
    await query.answer(f"Añadido: {prod['nombre']} ✅")


def texto_carrito(cart: dict) -> str:
    if not cart:
        return "Tu carrito está vacío 🛒"
    lineas = ["🛒 *Tu carrito:*\n"]
    for pid, qty in cart.items():
        prod = db.get_product(int(pid))
        if prod:
            lineas.append(f"• {prod['nombre']} x{qty} — {prod['precio'] * qty:.2f}€")
    lineas.append(f"\n*Total: {cart_total(cart):.2f}€*")
    return "\n".join(lineas)


async def ver_carrito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cart = get_cart(context)

    botones = []
    if cart:
        botones.append([InlineKeyboardButton("🧾 Finalizar pedido", callback_data="checkout")])
        botones.append([InlineKeyboardButton("🗑️ Vaciar carrito", callback_data="vaciar_carrito")])
    botones.append([InlineKeyboardButton("🎨 Seguir comprando", callback_data="ver_catalogo")])
    botones.append([InlineKeyboardButton("⬅️ Menú", callback_data="volver_menu")])

    await query.edit_message_text(
        texto_carrito(cart), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(botones)
    )


async def vaciar_carrito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    context.user_data["cart"] = {}
    await query.answer("Carrito vaciado 🗑️")
    await ver_carrito(update, context)


async def ver_contacto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menú", callback_data="volver_menu")]])
    await query.edit_message_text(
        f"📞 Contacto: {CONTACTO_TELEFONO}\n👤 Admin: @{ADMIN_USERNAME}", reply_markup=kb
    )


async def volver_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    usuario = db.get_user(update.effective_user.id)
    es_admin_flag = bool(usuario["is_admin"]) if usuario else False
    await editar_a_menu(query, es_admin_flag)


# --- Checkout / ubicación ---

async def pedir_ubicacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    cart = get_cart(context)
    if not cart:
        await query.answer("Tu carrito está vacío", show_alert=True)
        return
    await query.answer()

    kb = ReplyKeyboardMarkup(
        [[KeyboardButton("📍 Enviar mi ubicación", request_location=True)]],
        resize_keyboard=True, one_time_keyboard=True,
    )
    await context.bot.send_message(
        query.message.chat_id, "Para continuar, envía tu ubicación:", reply_markup=kb,
    )


async def recibir_ubicacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loc = update.message.location
    dist = distancia_km(loc.latitude, loc.longitude, VINAROS_LAT, VINAROS_LON)

    if dist > RADIO_MAXIMO_KM:
        await update.message.reply_text(
            "❌ Lo sentimos, no podemos entregar en tu ubicación. Solo repartimos "
            "en Vinaròs (hasta 1 km del centro).\n\n"
            f"Si tienes dudas, contacta al ☎️ {CONTACTO_TELEFONO}.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    await update.message.reply_text("✅ ¡Estás dentro de la zona de reparto!", reply_markup=ReplyKeyboardRemove())
    await enviar_factura(update, context)


async def enviar_factura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cart = get_cart(context)
    chat_id = update.message.chat_id

    if not PROVIDER_TOKEN:
        await context.bot.send_message(
            chat_id, "⚠️ El pago online todavía no está configurado (falta PROVIDER_TOKEN)."
        )
        return

    prices = []
    for pid, qty in cart.items():
        prod = db.get_product(int(pid))
        if prod:
            prices.append(LabeledPrice(prod["nombre"], int(prod["precio"] * qty * 100)))

    await context.bot.send_invoice(
        chat_id=chat_id,
        title="Pedido - Tienda de Pulseras",
        description=texto_carrito(cart).replace("*", ""),
        payload="pedido-tienda-pulseras",
        provider_token=PROVIDER_TOKEN,
        currency="EUR",
        prices=prices,
        start_parameter="tienda-pulseras",
    )


async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)


async def pago_exitoso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["cart"] = {}
    await update.message.reply_text("🎉 ¡Pago recibido! Pedido confirmado. Gracias por tu compra.")


# ---------------------------------------------------------------------
# Admin: usuarios y productos
# ---------------------------------------------------------------------

async def es_admin(update: Update) -> bool:
    usuario = db.get_user(update.effective_user.id)
    return bool(usuario and usuario["is_admin"])


async def admin_ver_usuarios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await es_admin(update):
        await query.answer("Solo el admin puede ver esto.", show_alert=True)
        return
    await query.answer()

    usuarios = db.get_all_users()
    lineas = ["👥 *Usuarios registrados:*\n"]
    for u in usuarios:
        etiqueta = " (admin)" if u["is_admin"] else ""
        estado = "" if u["activa"] else " · sesión cerrada"
        lineas.append(f"• {u['username']}{etiqueta}{estado}")

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menú", callback_data="volver_menu")]])
    await query.edit_message_text("\n".join(lineas), parse_mode="Markdown", reply_markup=kb)


async def admin_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await es_admin(update):
        await query.answer("Solo el admin puede añadir productos.", show_alert=True)
        return ConversationHandler.END
    await query.answer()
    await query.edit_message_text("Nombre del nuevo producto:")
    return ADMIN_NOMBRE


async def admin_add_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nuevo_producto_nombre"] = update.message.text.strip()
    chat_id = update.effective_chat.id

    try:
        await update.message.delete()
    except Exception:
        pass

    categorias = db.get_categories()
    botones = [[InlineKeyboardButton(c, callback_data=f"catsel_{c}")] for c in categorias]
    botones.append([InlineKeyboardButton("➕ Nueva categoría", callback_data="cat_nueva")])
    await context.bot.send_message(
        chat_id, "Elige la categoría del producto (o crea una nueva):",
        reply_markup=InlineKeyboardMarkup(botones),
    )
    return ADMIN_CATEGORIA


async def admin_categoria_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cat_nueva":
        await query.edit_message_text("Escribe el nombre de la nueva categoría:")
        return ADMIN_CATEGORIA

    categoria = query.data.replace("catsel_", "")
    context.user_data["nuevo_producto_categoria"] = categoria
    await query.edit_message_text(f"Categoría: *{categoria}*\n\nPrecio (ej. 3.50):", parse_mode="Markdown")
    return ADMIN_PRECIO


async def admin_categoria_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    categoria = update.message.text.strip()
    chat_id = update.effective_chat.id
    context.user_data["nuevo_producto_categoria"] = categoria

    try:
        await update.message.delete()
    except Exception:
        pass

    await context.bot.send_message(
        chat_id, f"Categoría: *{categoria}*\n\nPrecio (ej. 3.50):", parse_mode="Markdown"
    )
    return ADMIN_PRECIO


async def admin_add_precio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        precio = float(update.message.text.replace(",", "."))
    except ValueError:
        await update.message.reply_text("Precio no válido, escribe solo un número, ej. 3.50:")
        return ADMIN_PRECIO
    context.user_data["nuevo_producto_precio"] = precio

    try:
        await update.message.delete()
    except Exception:
        pass

    await context.bot.send_message(
        update.effective_chat.id,
        "Envía ahora la *foto* del producto (se recortará a cuadrada 1:1 automáticamente):",
        parse_mode="Markdown",
    )
    return ADMIN_FOTO


async def admin_add_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    foto = update.message.photo[-1]
    archivo = await foto.get_file()
    datos = bytes(await archivo.download_as_bytearray())
    datos_cuadrados = recortar_cuadrada(datos)

    nombre = context.user_data["nuevo_producto_nombre"]
    categoria = context.user_data.get("nuevo_producto_categoria", "General")
    precio = context.user_data["nuevo_producto_precio"]

    nombre_archivo = f"{nombre.lower().replace(' ', '_')}_{foto.file_unique_id}.jpg"
    ruta = os.path.join(IMG_DIR, nombre_archivo)
    with open(ruta, "wb") as f:
        f.write(datos_cuadrados)

    db.add_product(nombre, precio, ruta, categoria)

    await update.message.reply_text(
        f"✅ Producto *{nombre}* ({categoria}) añadido al catálogo ({precio:.2f}€), foto recortada a 1:1.",
        parse_mode="Markdown",
    )
    return ConversationHandler.END


# --- Los clientes solo pueden usar chat de texto: nada de fotos/archivos ---

async def contenido_no_permitido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await es_admin(update):
        await update.message.reply_text(
            "Para añadir un producto usa el botón '➕ Añadir producto' del menú."
        )
    else:
        await update.message.reply_text(
            "Solo puedo atender pedidos por chat de texto o los botones del menú. "
            "No se aceptan fotos ni archivos aquí."
        )


# ---------------------------------------------------------------------
# Seed inicial del catálogo
# ---------------------------------------------------------------------

SEED_PRODUCTOS = [
    ("Pulsera clásica Negra", "Clásica", 2.50, "clasico_negro.png"),
    ("Pulsera clásica Blanca", "Clásica", 2.50, "clasico_blanco.png"),
    ("Pulsera clásica Roja", "Clásica", 2.50, "clasico_rojo.png"),
    ("Pulsera clásica Azul", "Clásica", 2.50, "clasico_azul.png"),
    ("Pulsera clásica Verde", "Clásica", 2.50, "clasico_verde.png"),
    ("Pulsera clásica Amarilla", "Clásica", 2.50, "clasico_amarillo.png"),
    ("Pulsera combinada Rojo/Blanco", "Combinada", 3.00, "combinado_rojo_blanco.png"),
    ("Pulsera combinada Azul/Amarillo", "Combinada", 3.00, "combinado_azul_amarillo.png"),
    ("Pulsera combinada Verde/Negro", "Combinada", 3.00, "combinado_verde_negro.png"),
    ("Pulsera combinada Arcoíris", "Combinada", 3.50, "combinado_arcoiris.png"),
]


def sembrar_catalogo_inicial():
    if db.contar_productos() > 0:
        return
    for nombre, categoria, precio, archivo in SEED_PRODUCTOS:
        ruta = os.path.join(IMG_DIR, archivo)
        if os.path.exists(ruta):
            db.add_product(nombre, precio, ruta, categoria)


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

# ---------------------------------------------------------------------
# Segundo bot: SMSTienda_bot (solo entrega el código de verificación,
# no acepta ninguna otra interacción del usuario)
# ---------------------------------------------------------------------

SMS_BOT_APP = None  # se asigna en main_async(); el bot principal lo usa para borrar mensajes
TIENDA_BOT_APP = None  # se asigna en main_async(); @SMSTienda_bot lo usa para /sync


async def sms_bot_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    codigo = db.get_pendiente_codigo(telegram_id)
    if codigo:
        msg = await update.message.reply_text(
            f"📲 Tu código de verificación para *Tienda de Pulseras* es:\n\n*{codigo}*\n\n"
            "Vuelve al bot de la tienda y escríbelo allí, o verifica aquí mismo con:\n"
            "• `/auto` (verificación automática, sin escribir nada)\n"
            f"• `/sync {codigo}`",
            parse_mode="Markdown",
        )
        db.set_mensaje_sms(telegram_id, msg.message_id)
    else:
        await update.message.reply_text(
            "No tienes ningún código pendiente ahora mismo. Pide uno nuevo escribiendo /start "
            "en el bot de la tienda."
        )


async def sms_bot_restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Invalida el código actual y genera uno nuevo."""
    telegram_id = update.effective_user.id
    chat_id = update.effective_chat.id
    pendiente = db.get_pendiente(telegram_id)

    if not pendiente:
        await update.message.reply_text(
            "No tienes ninguna verificación pendiente. Pide una nueva con /start en el bot de la tienda."
        )
        return

    if pendiente.get("mensaje_id_sms"):
        try:
            await context.bot.delete_message(chat_id, pendiente["mensaje_id_sms"])
        except Exception:
            pass

    nuevo_codigo = generar_codigo_verificacion()
    db.set_pendiente(telegram_id, nuevo_codigo)  # conserva purpose/username/teléfono

    msg = await update.message.reply_text(
        f"📲 Nuevo código: *{nuevo_codigo}*\n\n"
        f"Escríbelo en el bot de la tienda, o usa aquí:\n`/sync {nuevo_codigo}`",
        parse_mode="Markdown",
    )
    db.set_mensaje_sms(telegram_id, msg.message_id)


async def _completar_y_notificar(update: Update, context: ContextTypes.DEFAULT_TYPE, pendiente: dict):
    """Completa la verificación, borra los mensajes de los dos bots y avisa/muestra el
    menú en el bot de la tienda. La usan tanto /sync como /auto."""
    telegram_id = update.effective_user.id
    chat_id = update.effective_chat.id

    ok, mensaje_resultado, es_admin_flag = await completar_verificacion(telegram_id, pendiente)

    mensaje_id_sms = pendiente.get("mensaje_id_sms")
    mensaje_id_tienda = pendiente.get("mensaje_id_tienda")
    db.borrar_pendiente(telegram_id)

    if mensaje_id_sms:
        try:
            await context.bot.delete_message(chat_id, mensaje_id_sms)
        except Exception:
            pass
    if mensaje_id_tienda and TIENDA_BOT_APP:
        try:
            await TIENDA_BOT_APP.bot.delete_message(telegram_id, mensaje_id_tienda)
        except Exception:
            pass

    if not ok:
        await update.message.reply_text(mensaje_resultado)
        return

    await update.message.reply_text("✅ ¡Verificado! Vuelve al bot de la tienda.")

    if TIENDA_BOT_APP:
        menu_msg = await enviar_menu_bot(TIENDA_BOT_APP.bot, telegram_id, es_admin_flag, mensaje_resultado)
        TIENDA_BOT_APP.user_data[telegram_id]["last_menu_msg_id"] = menu_msg.message_id


async def sms_bot_sync(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verifica el código escrito como '/sync CÓDIGO' y, si es correcto, completa
    el registro/inicio de sesión sin tener que volver al bot de la tienda a escribirlo."""
    telegram_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text("Escríbelo así: /sync CÓDIGO")
        return

    codigo_escrito = context.args[0].strip().upper()
    pendiente = db.get_pendiente(telegram_id)

    if not pendiente:
        await update.message.reply_text(
            "No tienes ninguna verificación pendiente. Pide una nueva con /start en el bot de la tienda."
        )
        return

    if codigo_escrito != pendiente["codigo"]:
        await update.message.reply_text("❌ Código incorrecto. Usa /restart para pedir uno nuevo.")
        return

    await _completar_y_notificar(update, context, pendiente)


async def sms_bot_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verifica automáticamente con el código que ya está pendiente, sin tener que escribirlo."""
    telegram_id = update.effective_user.id
    pendiente = db.get_pendiente(telegram_id)

    if not pendiente:
        await update.message.reply_text(
            "No tienes ninguna verificación pendiente. Pide una nueva con /start en el bot de la tienda."
        )
        return

    await _completar_y_notificar(update, context, pendiente)


async def sms_bot_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela la verificación pendiente."""
    telegram_id = update.effective_user.id
    chat_id = update.effective_chat.id
    pendiente = db.get_pendiente(telegram_id)

    if pendiente and pendiente.get("mensaje_id_sms"):
        try:
            await context.bot.delete_message(chat_id, pendiente["mensaje_id_sms"])
        except Exception:
            pass

    db.borrar_pendiente(telegram_id)
    await update.message.reply_text(
        "Verificación cancelada. Si la necesitas, pide una nueva con /start en el bot de la tienda."
    )


async def sms_bot_ignorar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Este bot solo entrega códigos: no acepta escribir ni mandar nada más."""
    try:
        await update.message.delete()
    except Exception:
        pass


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def construir_bot_tienda() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()

    login_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSE_ACCION: [CallbackQueryHandler(elegir_accion, pattern="^accion_")],
            ASK_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_username)],
            ASK_PASSWORD_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_password_admin)],
            CONFIRM_ALT_USERNAME: [CallbackQueryHandler(confirmar_username_alternativo, pattern="^alt_")],
            ASK_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_telefono)],
            CONFIRM_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirmar_codigo)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )

    admin_add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_add_start, pattern="^admin_add$")],
        states={
            ADMIN_NOMBRE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_nombre)],
            ADMIN_CATEGORIA: [
                CallbackQueryHandler(admin_categoria_callback, pattern="^(catsel_|cat_nueva$)"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_categoria_texto),
            ],
            ADMIN_PRECIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_precio)],
            ADMIN_FOTO: [MessageHandler(filters.PHOTO, admin_add_foto)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )

    app.add_handler(login_conv)
    app.add_handler(admin_add_conv)
    app.add_handler(CallbackQueryHandler(mostrar_catalogo, pattern="^ver_catalogo$"))
    app.add_handler(CallbackQueryHandler(elegir_categoria_catalogo, pattern="^catview_"))
    app.add_handler(CallbackQueryHandler(ver_carrito, pattern="^ver_carrito$"))
    app.add_handler(CallbackQueryHandler(vaciar_carrito, pattern="^vaciar_carrito$"))
    app.add_handler(CallbackQueryHandler(ver_contacto, pattern="^ver_contacto$"))
    app.add_handler(CallbackQueryHandler(volver_menu, pattern="^volver_menu$"))
    app.add_handler(CallbackQueryHandler(cerrar_sesion, pattern="^cerrar_sesion$"))
    app.add_handler(CallbackQueryHandler(admin_ver_usuarios, pattern="^admin_usuarios$"))
    app.add_handler(CallbackQueryHandler(pedir_ubicacion, pattern="^checkout$"))
    app.add_handler(CallbackQueryHandler(anadir_al_carrito, pattern="^add_"))
    app.add_handler(MessageHandler(filters.LOCATION, recibir_ubicacion))
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, pago_exitoso))
    # Los clientes solo pueden usar texto/botones: se avisa si mandan fotos o archivos.
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL | filters.VIDEO | filters.AUDIO, contenido_no_permitido))
    return app


def construir_bot_sms() -> Application:
    app = Application.builder().token(SMS_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", sms_bot_start))
    app.add_handler(CommandHandler("restart", sms_bot_restart))
    app.add_handler(CommandHandler("sync", sms_bot_sync))
    app.add_handler(CommandHandler("auto", sms_bot_auto))
    app.add_handler(CommandHandler("clear", sms_bot_clear))
    # Cualquier otra cosa que escriban o manden (texto, fotos, archivos...) se ignora/borra.
    app.add_handler(MessageHandler(~filters.COMMAND, sms_bot_ignorar))
    return app


async def main_async():
    global SMS_BOT_APP, TIENDA_BOT_APP

    db.init_db()
    sembrar_catalogo_inicial()

    app_tienda = construir_bot_tienda()
    await app_tienda.initialize()
    await app_tienda.start()
    await app_tienda.updater.start_polling()
    TIENDA_BOT_APP = app_tienda
    logger.info("Bot de la tienda iniciado...")

    if SMS_BOT_TOKEN:
        app_sms = construir_bot_sms()
        await app_sms.initialize()
        await app_sms.start()
        await app_sms.updater.start_polling()
        SMS_BOT_APP = app_sms
        logger.info("Bot de verificación (%s) iniciado...", SMS_BOT_USERNAME)
    else:
        logger.warning("SMS_BOT_TOKEN no configurado: el segundo bot no se ha iniciado.")

    await asyncio.Event().wait()  # mantiene el proceso vivo indefinidamente


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
