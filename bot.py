import logging
import re
import uuid
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
)

from config import (
    BOT_TOKEN, ADMIN_TELEGRAM_ID, KBZPAY_ACCOUNT_NAME, KBZPAY_PHONE_NUMBER,
    DIAMOND_PRODUCTS, PASS_PRODUCTS, STAR_CARD_PRODUCT, LOG_FILE
)
from database import (
    init_db, add_user, create_order, update_order_screenshot, update_order_status,
    get_order, get_pending_orders, get_last_n_orders, get_daily_stats
)

# Enable logging
logging.basicConfig(
    format=
'%(asctime)s - %(name)s - %(levelname)s - %(message)s'
, level=logging.INFO,
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Conversation states
(CATEGORY_SELECTION, PACKAGE_SELECTION, STAR_CARD_QUANTITY, PLAYER_ID_SERVER_ID,
 PAYMENT_SCREENSHOT, ADMIN_REJECT_REASON) = range(6)

# --- Burmese Strings (Customer-facing) ---
WELCOME_MESSAGE = (
    "မင်္ဂလာပါ 👋 GoodBoy MLBB Bot မှ ကြိုဆိုပါတယ်။\n\n" +
    "Mobile Legends: Bang Bang စိန်၊ Pass နှင့် Star Card များကို ဝယ်ယူရန် အောက်ပါခလုတ်များမှ ရွေးချယ်နိုင်ပါတယ်။"
)

MAIN_MENU_DIAMOND = "💎 Diamond Top-up"
MAIN_MENU_PASS = "🎟 Pass"
MAIN_MENU_STAR_CARD = "⭐ Star Card"
MAIN_MENU_HOW_TO_ORDER = "ℹ️ မှာယူနည်း"
MAIN_MENU_CANCEL = "❌ ဖျက်သိမ်းမည်"

DIAMOND_CATEGORY_TITLE = "💎 Diamond Top-up"
PASS_CATEGORY_TITLE = "🎟 Pass"
STAR_CARD_CATEGORY_TITLE = "⭐ Star Card"

SELECT_QUANTITY_MESSAGE = "Star Card အရေအတွက် (1-10) ကို ရိုက်ထည့်ပေးပါ။"
INVALID_QUANTITY_MESSAGE = "အရေအတွက် မှားယွင်းနေပါသည်။ 1 မှ 10 အတွင်း ဂဏန်းတစ်ခု ရိုက်ထည့်ပေးပါ။"

ASK_PLAYER_ID_SERVER_ID = (
    "ဂိမ်း Player ID နှင့် Server ID ကို ဥပမာ: `123456789 2055` ပုံစံအတိုင်း ပို့ပေးပါ။"
)
INVALID_PLAYER_ID_FORMAT = (
    "Player ID သို့မဟုတ် Server ID ပုံစံ မှားယွင်းနေပါသည်။\n" +
    "ဥပမာ: `123456789 2055` ပုံစံအတိုင်း ပြန်ပို့ပေးပါ။"
)

PAYMENT_INFO_MESSAGE = (
    "မှာယူမှု အသေးစိတ်:\n" +
    "{}
" +
    "စုစုပေါင်း: {} Ks\n\n" +
    "KBZPay မှ ငွေပေးချေရန် အောက်ပါအချက်အလက်များကို အသုံးပြုပါ။\n" +
    "အကောင့်အမည်: {}\n" +
    "ဖုန်းနံပါတ်: {}\n\n" +
    "ငွေလွှဲပြီးပါက ငွေလွှဲပြေစာ (screenshot) ကို ဓာတ်ပုံအဖြစ် ပို့ပေးပါ။"
)

ORDER_RECEIVED_MESSAGE = "မှာယူမှုလက်ခံရရှိပါပြီ။ ငွေစစ်ဆေးနေပါတယ်၊ ခဏစောင့်ပေးပါ။"

PAYMENT_SCREENSHOT_REQUIRED = "ငွေလွှဲပြေစာကို ဓာတ်ပုံအဖြစ်သာ ပို့ပေးပါ။"

ORDER_APPROVED_MESSAGE = "ငွေစစ်ဆေးပြီးပါပြီ။ ထည့်ပေးနေပါပြီ၊ ခဏစောင့်ပေးပါ။"
ORDER_DONE_MESSAGE = "ထည့်ပေးပြီးပါပြီခင်ဗျာ။ ဂိမ်းထဲဝင်စစ်ပေးပါ။ ကျေးဇူးတင်ပါတယ် 💎"
ORDER_REJECTED_MESSAGE = "မှာယူမှု ပယ်ဖျက်လိုက်ပါပြီ။ အကြောင်းအရင်း: {}"

HOW_TO_ORDER_MESSAGE = (
    "မှာယူနည်း အဆင့်ဆင့်:\n\n" +
    "1. သင်ဝယ်ယူလိုသော အမျိုးအစား (Diamond, Pass, Star Card) ကို ရွေးချယ်ပါ။\n" +
    "2. လိုချင်သော ပက်ကေ့ချ်ကို ရွေးချယ်ပါ။\n" +
    "3. Player ID နှင့် Server ID ကို မှန်ကန်စွာ ရိုက်ထည့်ပါ။\n" +
    "4. ဖော်ပြထားသော KBZPay အကောင့်သို့ ငွေလွှဲပြီး ငွေလွှဲပြေစာ (screenshot) ကို ဓာတ်ပုံအဖြစ် ပို့ပေးပါ။\n" +
    "5. Bot မှ သင့်မှာယူမှုကို လက်ခံရရှိကြောင်း အကြောင်းကြားပြီးနောက် Admin မှ စစ်ဆေးကာ စိန်/Pass/Star Card ထည့်သွင်းပေးပါလိမ့်မည်။\n\n" +
    "အဆင်မပြေမှုများရှိပါက Admin ကို ဆက်သွယ်နိုင်ပါသည်။"
)

CANCEL_MESSAGE = "မှာယူမှုကို ဖျက်သိမ်းလိုက်ပါပြီ။"

ADMIN_PROMPT_REJECT_REASON = "မှာယူမှု ပယ်ဖျက်ရခြင်း အကြောင်းအရင်းကို ရိုက်ထည့်ပေးပါ။"

# --- Admin Strings ---
ADMIN_ORDER_SUMMARY = (
    "🔔 New Order #{} 🔔\n\n" +
    "📦 Package: {} ({})\n" +
    "🔢 Quantity: {}\n" +
    "💰 Price: {} Ks\n" +
    "👤 Player ID: {}\n" +
    "🌐 Server ID: {}\n" +
    "🙋 Customer: @{}\n" +
    "🆔 Customer ID: {}\n" +
    "⏰ Timestamp: {}"
)

ADMIN_STATS_MESSAGE = (
    "📊 Today's Statistics ({}):\n\n" +
    "Total Orders: {}\n" +
    "Pending Orders: {}\n" +
    "Completed Orders: {}\n" +
    "Rejected Orders: {}\n" +
    "Total Revenue: {} Ks"
)

ADMIN_PENDING_ORDERS_TITLE = "⏳ Pending Orders:"
ADMIN_NO_PENDING_ORDERS = "လက်ရှိ ဆောင်ရွက်ဆဲ မှာယူမှုများ မရှိပါ။"
ADMIN_ORDER_ITEM = "#{} - {} ({} Ks) from @{} (ID: {})"

ADMIN_LAST_ORDERS_TITLE = "📋 Last 10 Orders:"
ADMIN_NO_ORDERS = "မှာယူမှုများ မရှိသေးပါ။"

ADMIN_BROADCAST_SUCCESS = "{} users received the broadcast message."
ADMIN_BROADCAST_FAILED = "Failed to send broadcast to {} users."
ADMIN_BROADCAST_USAGE = "Usage: /broadcast <message>"

ADMIN_HELP_MESSAGE = (
    "Admin Commands:\n\n" +
    "/stats - View today's order statistics\n" +
    "/pending - List all pending orders\n" +
    "/orders - List the last 10 orders\n" +
    "/broadcast <message> - Send a message to all bot users\n" +
    "/help - Show this admin command guide"
)

# --- Helper Functions ---
def generate_order_id():
    """Generates a unique order ID."""
    timestamp = datetime.now().strftime("%Y%m%d")
    unique_id = uuid.uuid4().hex[:4].upper() # Short unique string
    return f"ORD-{timestamp}-{unique_id}"

def get_main_menu_keyboard():
    """Returns the main menu inline keyboard."""
    keyboard = [
        [InlineKeyboardButton(MAIN_MENU_DIAMOND, callback_data=
'category_diamond')],
        [InlineKeyboardButton(MAIN_MENU_PASS, callback_data=
'category_pass')],
        [InlineKeyboardButton(MAIN_MENU_STAR_CARD, callback_data=
'category_star_card')],
        [InlineKeyboardButton(MAIN_MENU_HOW_TO_ORDER, callback_data=
'how_to_order')],
        [InlineKeyboardButton(MAIN_MENU_CANCEL, callback_data=
'cancel')]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context) -> int:
    """Sends a welcome message and shows the main menu."""
    user = update.effective_user
    add_user(user.id, user.username)
    logger.info(f"User {user.id} ({user.username}) started the bot.")

    await update.message.reply_text(WELCOME_MESSAGE, reply_markup=get_main_menu_keyboard())
    return CATEGORY_SELECTION

async def cancel(update: Update, context) -> int:
    """Cancels the current conversation and returns to the main menu."""
    user = update.effective_user
    logger.info(f"User {user.id} ({user.username}) cancelled the conversation.")
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(CANCEL_MESSAGE, reply_markup=get_main_menu_keyboard())
    else:
        await update.message.reply_text(CANCEL_MESSAGE, reply_markup=get_main_menu_keyboard())
    return CATEGORY_SELECTION

async def how_to_order(update: Update, context) -> int:
    """Displays instructions on how to order."""
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(HOW_TO_ORDER_MESSAGE, reply_markup=get_main_menu_keyboard())
    return CATEGORY_SELECTION

async def category_selection(update: Update, context) -> int:
    """Handles category selection from the main menu."""
    query = update.callback_query
    await query.answer()
    category = query.data.split(
'_
')[1]

    context.user_data[
'category'
] = category
    keyboard = []
    title = ""

    if category == 
'diamond'
:
        title = DIAMOND_CATEGORY_TITLE
        for name, details in DIAMOND_PRODUCTS.items():
            keyboard.append([InlineKeyboardButton(f"{details['description_mm']} - {details['price']} Ks", callback_data=f"package_{name}")])
    elif category == 
'pass'
:
        title = PASS_CATEGORY_TITLE
        for name, details in PASS_PRODUCTS.items():
            keyboard.append([InlineKeyboardButton(f"{details['description_mm']} - {details['price']} Ks", callback_data=f"package_{name}")])
    elif category == 
'star_card'
:
        title = STAR_CARD_CATEGORY_TITLE
        name = list(STAR_CARD_PRODUCT.keys())[0]
        details = STAR_CARD_PRODUCT[name]
        # For Star Card, we first ask for quantity, then player ID.
        # So, the next state will be STAR_CARD_QUANTITY
        context.user_data[
'selected_package'
] = {
            
'name'
: name,
            
'price'
: details[
'price'
],
            
'type'
: 
'star_card'
,
            
'description_mm'
: details[
'description_mm'
]
        }
        await query.edit_message_text(SELECT_QUANTITY_MESSAGE)
        return STAR_CARD_QUANTITY

    keyboard.append([InlineKeyboardButton("⬅️ နောက်သို့", callback_data=
'back_to_main')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"{title}\n\nကျေးဇူးပြု၍ သင်ဝယ်ယူလိုသော ပက်ကေ့ချ်ကို ရွေးချယ်ပါ။", reply_markup=reply_markup)
    return PACKAGE_SELECTION

async def package_selection(update: Update, context) -> int:
    """Handles package selection for Diamond and Pass categories."""
    query = update.callback_query
    await query.answer()
    package_name = query.data.split(
'_
', 1)[1]

    category = context.user_data[
'category'
]
    selected_product = None

    if category == 
'diamond'
:
        selected_product = DIAMOND_PRODUCTS.get(package_name)
        package_type = 
'diamond'
    elif category == 
'pass'
:
        selected_product = PASS_PRODUCTS.get(package_name)
        package_type = 
'pass'

    if not selected_product:
        await query.edit_message_text("မှားယွင်းနေသော ပက်ကေ့ချ်။ ကျေးဇူးပြု၍ ပြန်ရွေးချယ်ပါ။", reply_markup=get_main_menu_keyboard())
        return CATEGORY_SELECTION

    context.user_data[
'selected_package'
] = {
        
'name'
: package_name,
        
'price'
: selected_product[
'price'
],
        
'type'
: package_type,
        
'description_mm'
: selected_product[
'description_mm'
]
    }
    context.user_data[
'quantity'
] = 1 # Default quantity for non-star card items

    await query.edit_message_text(ASK_PLAYER_ID_SERVER_ID)
    return PLAYER_ID_SERVER_ID

async def star_card_quantity_input(update: Update, context) -> int:
    """Handles Star Card quantity input."""
    user_input = update.message.text
    try:
        quantity = int(user_input)
        if 1 <= quantity <= 10:
            context.user_data[
'quantity'
] = quantity
            await update.message.reply_text(ASK_PLAYER_ID_SERVER_ID)
            return PLAYER_ID_SERVER_ID
        else:
            await update.message.reply_text(INVALID_QUANTITY_MESSAGE)
            return STAR_CARD_QUANTITY
    except ValueError:
        await update.message.reply_text(INVALID_QUANTITY_MESSAGE)
        return STAR_CARD_QUANTITY

async def player_id_server_id_input(update: Update, context) -> int:
    """Handles Player ID and Server ID input and asks for payment screenshot."""
    player_info = update.message.text.strip()
    match = re.match(r"^(\\d+)\\s+(\\d+)$", player_info)

    if not match:
        await update.message.reply_text(INVALID_PLAYER_ID_FORMAT)
        return PLAYER_ID_SERVER_ID

    player_id = match.group(1)
    server_id = match.group(2)

    context.user_data[
'player_id'
] = player_id
    context.user_data[
'server_id'
] = server_id

    selected_package = context.user_data[
'selected_package'
]
    quantity = context.user_data.get(
'quantity'
, 1)
    total_price = selected_package[
'price'
] * quantity

    order_summary_text = (
        f"{selected_package['description_mm']} x {quantity}\n" +
        f"Player ID: {player_id}\n" +
        f"Server ID: {server_id}"
    )

    await update.message.reply_text(
        PAYMENT_INFO_MESSAGE.format(
            order_summary_text, total_price, KBZPAY_ACCOUNT_NAME, KBZPAY_PHONE_NUMBER
        )
    )
    return PAYMENT_SCREENSHOT

async def handle_payment_screenshot(update: Update, context) -> int:
    """Handles the payment screenshot, saves order, and forwards to admin."""
    if not update.message.photo:
        await update.message.reply_text(PAYMENT_SCREENSHOT_REQUIRED)
        return PAYMENT_SCREENSHOT

    user = update.effective_user
    photo_file_id = update.message.photo[-1].file_id

    selected_package = context.user_data[
'selected_package'
]
    quantity = context.user_data.get(
'quantity'
, 1)
    total_price = selected_package[
'price'
] * quantity
    player_id = context.user_data[
'player_id'
]
    server_id = context.user_data[
'server_id'
]

    order_id = generate_order_id()
    create_order(
        user.id, order_id, selected_package[
'name'
], selected_package[
'type'
],
        quantity, total_price, player_id, server_id
    )
    update_order_screenshot(order_id, photo_file_id)

    logger.info(f"Order {order_id} created by user {user.id} ({user.username}).")

    # Notify customer
    await update.message.reply_text(ORDER_RECEIVED_MESSAGE)

    # Notify admin
    admin_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve_{order_id}")],
        [InlineKeyboardButton("💎 Done", callback_data=f"admin_done_{order_id}")],
        [InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject_{order_id}")]
    ])

    order_summary_for_admin = ADMIN_ORDER_SUMMARY.format(
        order_id, selected_package[
'name'
], selected_package[
'type'
],
        quantity, total_price, player_id, server_id,
        user.username or 
'N/A'
, user.id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    await context.bot.send_photo(
        chat_id=ADMIN_TELEGRAM_ID,
        photo=photo_file_id,
        caption=order_summary_for_admin,
        reply_markup=admin_keyboard
    )

    context.user_data.clear() # Clear user data after order is placed
    return ConversationHandler.END

async def admin_callback_handler(update: Update, context) -> int:
    """Handles admin actions (approve, done, reject)."""
    query = update.callback_query
    await query.answer()
    data = query.data.split(
'_
')
    action = data[1]
    order_id = data[2]

    order = get_order(order_id)
    if not order:
        await query.edit_message_text(f"Order {order_id} not found.")
        return ConversationHandler.END

    user_telegram_id = order[2] # user_telegram_id column

    if action == 
'approve'
:
        update_order_status(order_id, 
'approved'
)
        await context.bot.send_message(chat_id=user_telegram_id, text=ORDER_APPROVED_MESSAGE)
        await query.edit_message_caption(caption=query.message.caption + 
'\n\nStatus: ✅ Approved'
, reply_markup=None)
        logger.info(f"Admin {query.from_user.id} approved order {order_id}.")
    elif action == 
'done'
:
        update_order_status(order_id, 
'done'
)
        await context.bot.send_message(chat_id=user_telegram_id, text=ORDER_DONE_MESSAGE)
        await query.edit_message_caption(caption=query.message.caption + 
'\n\nStatus: 💎 Done'
, reply_markup=None)
        logger.info(f"Admin {query.from_user.id} marked order {order_id} as done.")
    elif action == 
'reject'
:
        context.user_data[
'admin_reject_order_id'
] = order_id
        await query.edit_message_caption(caption=query.message.caption + 
'\n\nStatus: ❌ Rejected (awaiting reason)'
, reply_markup=None)
        await context.bot.send_message(chat_id=query.from_user.id, text=ADMIN_PROMPT_REJECT_REASON)
        return ADMIN_REJECT_REASON

    return ConversationHandler.END

async def admin_receive_reject_reason(update: Update, context) -> int:
    """Receives rejection reason from admin and sends to customer."""
    admin_id = update.effective_user.id
    if admin_id != ADMIN_TELEGRAM_ID:
        return ConversationHandler.END

    reason = update.message.text
    order_id = context.user_data.pop(
'admin_reject_order_id'
, None)

    if order_id:
        order = get_order(order_id)
        if order:
            user_telegram_id = order[2]
            update_order_status(order_id, 
'rejected'
, admin_notes=reason)
            await context.bot.send_message(chat_id=user_telegram_id, text=ORDER_REJECTED_MESSAGE.format(reason))
            await update.message.reply_text(f"Order {order_id} rejected with reason sent to customer.")
            logger.info(f"Admin {admin_id} rejected order {order_id} with reason: {reason}.")
    else:
        await update.message.reply_text("Error: No active rejection order found.")

    return ConversationHandler.END

# --- Admin Commands ---
async def stats(update: Update, context) -> None:
    """Sends today's statistics to the admin."""
    if update.effective_user.id != ADMIN_TELEGRAM_ID:
        return

    stats_data = get_daily_stats()
    today_date = datetime.now().strftime("%Y-%m-%d")
    message = ADMIN_STATS_MESSAGE.format(
        today_date,
        stats_data[
'total_orders_today'
],
        stats_data[
'pending_orders_today'
],
        stats_data[
'completed_orders_today'
],
        stats_data[
'rejected_orders_today'
],
        stats_data[
'total_revenue_today'
]
    )
    await update.message.reply_text(message)

async def pending_orders(update: Update, context) -> None:
    """Lists all pending orders to the admin."""
    if update.effective_user.id != ADMIN_TELEGRAM_ID:
        return

    pending = get_pending_orders()
    if not pending:
        await update.message.reply_text(ADMIN_NO_PENDING_ORDERS)
        return

    message = ADMIN_PENDING_ORDERS_TITLE + 
'\n\n'
    for order in pending:
        # order tuple: (id, order_id, user_telegram_id, package_name, package_type, quantity, price, player_id, server_id, screenshot_file_id, status, timestamp, admin_notes, username)
        order_id = order[1]
        package_name = order[3]
        price = order[6]
        customer_username = order[13] if order[13] else 
'N/A'
        customer_id = order[2]
        message += ADMIN_ORDER_ITEM.format(order_id, package_name, price, customer_username, customer_id) + 
'\n'

    await update.message.reply_text(message)

async def last_orders(update: Update, context) -> None:
    """Lists the last 10 orders to the admin."""
    if update.effective_user.id != ADMIN_TELEGRAM_ID:
        return

    orders = get_last_n_orders(10)
    if not orders:
        await update.message.reply_text(ADMIN_NO_ORDERS)
        return

    message = ADMIN_LAST_ORDERS_TITLE + 
'\n\n'
    for order in orders:
        order_id = order[1]
        package_name = order[3]
        price = order[6]
        customer_username = order[13] if order[13] else 
'N/A'
        customer_id = order[2]
        status = order[10]
        message += f"{ADMIN_ORDER_ITEM.format(order_id, package_name, price, customer_username, customer_id)} - Status: {status}\n"

    await update.message.reply_text(message)

async def broadcast(update: Update, context) -> None:
    """Sends a broadcast message to all users."""
    if update.effective_user.id != ADMIN_TELEGRAM_ID:
        return

    if not context.args:
        await update.message.reply_text(ADMIN_BROADCAST_USAGE)
        return

    message_to_send = 
' '
.join(context.args)

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id FROM users")
    users = cursor.fetchall()
    conn.close()

    sent_count = 0
    failed_count = 0
    for user_id_tuple in users:
        user_id = user_id_tuple[0]
        try:
            await context.bot.send_message(chat_id=user_id, text=message_to_send)
            sent_count += 1
        except Exception as e:
            logger.error(f"Failed to send broadcast to user {user_id}: {e}")
            failed_count += 1
    
    await update.message.reply_text(ADMIN_BROADCAST_SUCCESS.format(sent_count))
    if failed_count > 0:
        await update.message.reply_text(ADMIN_BROADCAST_FAILED.format(failed_count))

async def admin_help(update: Update, context) -> None:
    """Sends the admin command guide."""
    if update.effective_user.id != ADMIN_TELEGRAM_ID:
        return
    await update.message.reply_text(ADMIN_HELP_MESSAGE)

def main() -> None:
    """Starts the bot."""
    init_db()

    application = Application.builder().token(BOT_TOKEN).build()

    # Conversation Handler for ordering flow
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CATEGORY_SELECTION: [
                CallbackQueryHandler(category_selection, pattern=
'^category_')
, # Handles diamond, pass, star_card
                CallbackQueryHandler(how_to_order, pattern=
'^how_to_order$')
,
                CallbackQueryHandler(cancel, pattern=
'^cancel$')
,
            ],
            PACKAGE_SELECTION: [
                CallbackQueryHandler(package_selection, pattern=
'^package_')
,
                CallbackQueryHandler(start, pattern=
'^back_to_main$')
, # Back to main menu
            ],
            STAR_CARD_QUANTITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, star_card_quantity_input),
            ],
            PLAYER_ID_SERVER_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, player_id_server_id_input),
            ],
            PAYMENT_SCREENSHOT: [
                MessageHandler(filters.PHOTO, handle_payment_screenshot),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_payment_screenshot), # To catch non-photo input
            ],
            ADMIN_REJECT_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_receive_reject_reason),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel, pattern=
'^cancel$')
,
        ],
    )

    application.add_handler(conv_handler)

    # Admin callback handler (for approve/done/reject buttons on order messages)
    application.add_handler(CallbackQueryHandler(admin_callback_handler, pattern=
'^admin_')
)

    # Admin commands
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("pending", pending_orders))
    application.add_handler(CommandHandler("orders", last_orders))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("help", admin_help))

    # Run the bot until the user presses Ctrl-C
    logger.info("Bot started polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == 
'__main__'
:
    main()
