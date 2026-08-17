from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_main_menu_keyboard(show_installment: bool = False) -> InlineKeyboardMarkup:
    """Returns the main menu keyboard layout.

    show_installment: only True for customers who have an eligible
    installment arrangement. Normal customers must never see this button
    (see spec section 20 - Installment Menu Visibility).
    """
    keyboard = [
        [InlineKeyboardButton("🏠 Home", callback_data="home")],
        [InlineKeyboardButton("🛒 Buy EA", callback_data="buy_ea"), InlineKeyboardButton("🔄 Broker Change", callback_data="broker_change")],
        [InlineKeyboardButton("🆓 Free Trial", callback_data="free_trial"), InlineKeyboardButton("📥 Downloads", callback_data="downloads")],
        [InlineKeyboardButton("📜 License Details", callback_data="license_details"), InlineKeyboardButton("📋 My Orders", callback_data="my_orders")],
        [InlineKeyboardButton("☎️ Support", callback_data="support")],
    ]

    if show_installment:
        keyboard.append([InlineKeyboardButton("💳 My Installment", callback_data="my_installment")])

    return InlineKeyboardMarkup(keyboard)
