import os
import logging
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from dotenv import load_dotenv

import httpx
# SSL verification is disabled ONLY when explicitly opted into via env var
# (e.g. for a local dev machine sitting behind a self-signed proxy/cert).
# Previously this was force-disabled for every environment, including
# production, which silently defeats TLS certificate validation on every
# outgoing request (to Telegram's API, the backend, etc). Never disable
# this in production.
_DISABLE_SSL_VERIFY = os.getenv("DISABLE_SSL_VERIFY", "false").lower() in ("1", "true", "yes")
HTTPX_VERIFY = not _DISABLE_SSL_VERIFY
if _DISABLE_SSL_VERIFY:
    logging.warning("DISABLE_SSL_VERIFY is set - httpx SSL certificate verification is disabled. Do NOT use this in production.")
    _original_init = httpx.AsyncClient.__init__
    def _patched_init(self, *args, **kwargs):
        kwargs['verify'] = False
        _original_init(self, *args, **kwargs)
    httpx.AsyncClient.__init__ = _patched_init

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters, ConversationHandler

from keyboards.menu import get_main_menu_keyboard
from utils.api_client import register_user, get_products, create_order, get_user, is_installment_eligible

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)


async def build_main_menu(telegram_id) -> InlineKeyboardMarkup:
    """Builds the main menu keyboard, showing the 'My Installment' button
    only for customers who actually have an eligible installment arrangement."""
    show_installment = await is_installment_eligible(str(telegram_id))
    return get_main_menu_keyboard(show_installment=show_installment)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    db_user = await get_user(str(user.id))
    if db_user:
        context.user_data['db_user_id'] = db_user['id']
        context.user_data['db_user_phone'] = db_user.get('phone')
        context.user_data['db_user_name'] = db_user.get('name')
        await update.message.reply_text(
            f"Welcome back, {db_user['name']}!\n\nPlease select an option below:",
            reply_markup=await build_main_menu(user.id)
        )
        return ConversationHandler.END
        
    # Ask for full name explicitly
    await update.message.reply_text(
        f"Welcome to Infinity Trader!\n\nPlease enter your **Full Name** to register and continue:",
        parse_mode="Markdown"
    )
    context.user_data['awaiting_name'] = True
    context.user_data['temp_telegram_id'] = user.id
    context.user_data['temp_username'] = user.username
    return ConversationHandler.END

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data.startswith("approve_") and not data.startswith("approve_change_"):
        admin_id = os.getenv("ADMIN_CHAT_ID")
        if str(update.effective_user.id) != str(admin_id):
            await query.answer("You are not authorized to perform this action.", show_alert=True)
            return
            
        order_id = int(data.split("_")[1])
        
        from utils.api_client import approve_order, reject_order
        
        resp = await approve_order(order_id)
        if "error" not in resp:
            mt5_id = resp.get("mt5_id", "")
            kb = [
                [InlineKeyboardButton("🚀 Generate Full Lifetime License", callback_data=f"generate_lifetime_{order_id}_{mt5_id}")],
                [InlineKeyboardButton("💳 Create Installment Arrangement", callback_data=f"create_installment_{order_id}")]
            ]
            await query.edit_message_text(
                f"✅ Order #{order_id} has been APPROVED.\n\nMT5 ID: `{mt5_id}`\n\nWhat would you like to do?",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(kb)
            )
            
            # Notify Customer
            try:
                telegram_id = resp.get("telegram_id")
                if telegram_id:
                    msg = (
                        f"✅ *YOUR ORDER HAS BEEN APPROVED*\n\n"
                        f"Your EA order (ORD-{order_id}) has been approved.\n\n"
                        f"Your EA is being prepared and will be delivered to you shortly."
                    )
                    await context.bot.send_message(chat_id=telegram_id, text=msg, parse_mode="Markdown")
            except Exception as e:
                logging.error(f"Failed to notify user: {e}")
        else:
            await query.answer(f"Failed: {resp['error']}", show_alert=True)
        return

    if data.startswith("reject_") and not data.startswith("reject_change_"):
        admin_id = os.getenv("ADMIN_CHAT_ID")
        if str(update.effective_user.id) != str(admin_id):
            await query.answer("You are not authorized to perform this action.", show_alert=True)
            return
            
        order_id = int(data.split("_")[1])
        from utils.api_client import reject_order
        
        resp = await reject_order(order_id)
        if "error" not in resp:
            await query.edit_message_text(f"❌ Order #{order_id} has been REJECTED.")
            try:
                telegram_id = resp.get("telegram_id")
                if telegram_id:
                    msg = (
                        f"❌ *ORDER NOT APPROVED*\n\n"
                        f"Your EA order (ORD-{order_id}) has not been approved by the administrator.\n\n"
                        f"Please contact support for more information."
                    )
                    await context.bot.send_message(chat_id=telegram_id, text=msg, parse_mode="Markdown")
            except:
                pass
        else:
            await query.answer(f"Failed: {resp['error']}", show_alert=True)
        return

    if data.startswith("generate_lifetime_"):
        admin_id = os.getenv("ADMIN_CHAT_ID")
        if str(update.effective_user.id) != str(admin_id):
            await query.answer("You are not authorized to perform this action.", show_alert=True)
            return
            
        # Format: generate_lifetime_{order_id}_{mt5_id}
        # Use maxsplit=3 to preserve underscores in the MT5 ID
        _, _, order_id_str, mt5_id = data.split("_", 3)
        order_id = int(order_id_str)
        
        await query.edit_message_text(f"🚀 Generating Lifetime License for Order #{order_id} (MT5: {mt5_id})...")
        
        from utils.api_client import generate_license
        resp = await generate_license(order_id, mt5_id)
        
        if "error" in resp:
            await query.edit_message_text(f"❌ *Error generating license:*\n{resp['error']}", parse_mode="Markdown")
            return
            
        await query.edit_message_text(
            f"✅ *Lifetime License Generated!*\n\n"
            f"Order: ORD-{order_id}\n"
            f"MT5 ID: `{mt5_id}`\n\n"
            f"⏳ EA is now compiling. File will be auto-delivered to the customer when ready.\n\n"
            f"If the customer doesn't receive it within 10 minutes, use the button below:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📤 Resend EA to Customer", callback_data=f"resend_ea_{order_id}")
            ]])
        )
        
        # Notify customer
        base_url = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
        import httpx
        async with httpx.AsyncClient(verify=HTTPX_VERIFY) as client:
            order_resp = await client.get(f"{base_url}/orders/{order_id}")
            if order_resp.status_code == 200:
                user_id = order_resp.json().get("user_id")
                user_resp = await client.get(f"{base_url}/users/by-id/{user_id}")
                if user_resp.status_code == 200:
                    telegram_id = user_resp.json().get("telegram_id")
                    if telegram_id:
                        msg = (
                            f"✅ *Your Order is Approved!*\n\n"
                            f"MT5 ID: `{mt5_id}`\n\n"
                            f"Your EA is currently compiling and will be delivered here shortly.\n"
                            f"Please wait — this usually takes 2-5 minutes."
                        )
                        try:
                            await context.bot.send_message(chat_id=telegram_id, text=msg, parse_mode="Markdown")
                        except:
                            pass
        return

    if data.startswith("resend_ea_"):
        admin_id = os.getenv("ADMIN_CHAT_ID")
        if str(update.effective_user.id) != str(admin_id):
            await query.answer("Not authorized.", show_alert=True)
            return
        
        order_id = int(data.split("_")[2])
        base_url = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
        import httpx
        async with httpx.AsyncClient(verify=HTTPX_VERIFY) as client:
            # Get license for this order
            order_resp = await client.get(f"{base_url}/orders/{order_id}")
            if order_resp.status_code != 200:
                await query.answer("Order not found.", show_alert=True)
                return
            
            user_id = order_resp.json().get("user_id")
            lic_resp = await client.get(f"{base_url}/licenses/user/{user_id}")
            if lic_resp.status_code != 200:
                await query.answer("No license found.", show_alert=True)
                return
            
            lics = lic_resp.json()
            lic = next((l for l in lics if l.get("order_id") == order_id), None)
            
            if not lic:
                await query.answer("No license found for this order.", show_alert=True)
                return
            
            lic_status = lic.get("status")
            lic_id = lic.get("id")
            
            if lic_status != "active":
                await query.answer(
                    f"⏳ EA is still {lic_status}. Cannot resend yet. Worker must compile it first.",
                    show_alert=True
                )
                return
            
            # File is compiled — trigger delivery manually
            delivery_resp = await client.get(f"{base_url}/licenses/{lic_id}/delivery-info")
            if delivery_resp.status_code != 200:
                await query.answer("Failed to get delivery info.", show_alert=True)
                return
            
            info = delivery_resp.json()
            telegram_id = info.get("telegram_id")
            mt5_id = info.get("mt5_id")
            download_url = info.get("download_url")
            
            if not download_url:
                await query.answer("❌ File not in storage yet. Worker may still be running.", show_alert=True)
                return
            
            # Download and resend the file directly from here
            token = os.getenv("TELEGRAM_BOT_TOKEN")
            file_resp = await client.get(download_url)
            if file_resp.status_code == 200:
                import io
                doc = io.BytesIO(file_resp.content)
                doc.name = f"InfinityTrader_{mt5_id}.ex5"
                try:
                    await context.bot.send_document(
                        chat_id=int(telegram_id),
                        document=doc,
                        caption=f"📦 *InfinityTrader EA*\nMT5 ID: `{mt5_id}`\n\n✅ Your EA file — install in MetaTrader 5 Expert Advisors folder.",
                        parse_mode="Markdown"
                    )
                    await query.answer("✅ EA file resent to customer!", show_alert=True)
                except Exception as e:
                    await query.answer(f"Failed to send: {e}", show_alert=True)
            else:
                await query.answer(f"❌ Could not download file from storage (HTTP {file_resp.status_code}).", show_alert=True)
        return


    if data.startswith("create_installment_"):
        admin_id = os.getenv("ADMIN_CHAT_ID")
        if str(update.effective_user.id) != str(admin_id):
            await query.answer("You are not authorized to perform this action.", show_alert=True)
            return
            
        order_id = int(data.split("_")[2])
        
        # Verify MT5 ID exists
        base_url = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
        import httpx
        async with httpx.AsyncClient(verify=HTTPX_VERIFY) as client:
            resp = await client.get(f"{base_url}/orders/{order_id}")
            if resp.status_code == 200:
                order_data = resp.json()
                if not order_data.get("mt5_id"):
                    await query.answer("MT5 ID has not been received yet. Please wait for the customer to submit their MT5 ID.", show_alert=True)
                    return
            else:
                await query.answer("Failed to fetch order details to verify MT5 ID.", show_alert=True)
                return

        context.user_data['install_order_id'] = order_id
        context.user_data['install_step'] = 'total_amount'
        
        await query.edit_message_text(f"💳 *Create Installment Arrangement for Order #{order_id}*\n\nPlease enter the **Total agreed amount** (e.g. 20000):", parse_mode="Markdown")
        return

    if data.startswith("manage_installment_"):
        admin_id = os.getenv("ADMIN_CHAT_ID")
        if str(update.effective_user.id) != str(admin_id):
            await query.answer("You are not authorized to perform this action.", show_alert=True)
            return
            
        order_id = int(data.split("_")[2])
        base_url = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
        import httpx
        async with httpx.AsyncClient(verify=HTTPX_VERIFY) as client:
            resp = await client.get(
                f"{base_url}/installments/admin/{order_id}",
                headers={"X-Admin-Key": os.getenv("ADMIN_API_KEY", "")}
            )
            if resp.status_code == 200:
                data_json = resp.json()
                is_final = data_json['installments_paid'] >= data_json['installment_count']
                expiry_val = data_json['license_expiry']
                expiry_display = expiry_val.split('T')[0] if expiry_val else 'Lifetime ♾️'
                msg = (
                    f"💳 *INSTALLMENT MANAGEMENT*\n\n"
                    f"Order: ORD-{order_id}\n"
                    f"MT5 ID: `{data_json['mt5_id']}`\n\n"
                    f"Total: ₹{data_json['total_amount']:,.0f}\n"
                    f"Per Installment: ₹{data_json['installment_amount']:,.0f}\n\n"
                    f"Paid: ₹{data_json['amount_paid']:,.0f}\n"
                    f"Remaining: ₹{data_json['amount_remaining']:,.0f}\n\n"
                    f"Progress: {data_json['installments_paid']}/{data_json['installment_count']} payments\n\n"
                    f"License: {data_json['license_status'].title()}\n"
                    f"Expires: {expiry_display}"
                )
                kb = [
                    [InlineKeyboardButton("Mark Payment Received", callback_data=f"mark_install_paid_{order_id}")],
                    [InlineKeyboardButton("🔍 Check Compile Status", callback_data=f"check_compile_status_{order_id}")],
                    [InlineKeyboardButton("Payment History", callback_data=f"install_history_{order_id}")],
                    [InlineKeyboardButton("Disable Arrangement", callback_data=f"disable_install_{order_id}")]
                ]
                await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
            else:
                await query.answer("Installment arrangement not found.", show_alert=True)
        return

    if data.startswith("mark_install_paid_"):
        admin_id = os.getenv("ADMIN_CHAT_ID")
        if str(update.effective_user.id) != str(admin_id):
            await query.answer("You are not authorized to perform this action.", show_alert=True)
            return
            
        order_id = int(data.split("_")[3])
        base_url = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
        import httpx
        async with httpx.AsyncClient(verify=HTTPX_VERIFY) as client:
            # Fetch installment info
            resp = await client.get(
                f"{base_url}/installments/admin/{order_id}",
                headers={"X-Admin-Key": os.getenv("ADMIN_API_KEY", "")}
            )
            if resp.status_code == 200:
                inst_data = resp.json()
                amount = inst_data['installment_amount']
                pay_resp = await client.post(f"{base_url}/installments/pay", json={"order_id": order_id, "amount": amount})
                if pay_resp.status_code == 200:
                    await query.edit_message_text(
                        f"✅ Payment of ₹{amount:,.0f} recorded for Order #{order_id}.\n\nLicense extended and compilation queued.",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("📋 Manage Installment", callback_data=f"manage_installment_{order_id}")],
                            [InlineKeyboardButton("🔍 Check Compile Status", callback_data=f"check_compile_status_{order_id}")]
                        ])
                    )
                    # Notify customer
                    try:
                        order_resp = await client.get(f"{base_url}/orders/{order_id}")
                        if order_resp.status_code == 200:
                            user_id = order_resp.json().get("user_id")
                            user_resp = await client.get(f"{base_url}/users/by-id/{user_id}")
                            if user_resp.status_code == 200:
                                telegram_id = user_resp.json().get("telegram_id")
                                if telegram_id:
                                    # Re-fetch updated installment data after payment
                                    updated_resp = await client.get(
                f"{base_url}/installments/admin/{order_id}",
                headers={"X-Admin-Key": os.getenv("ADMIN_API_KEY", "")}
            )
                                    updated_data = updated_resp.json() if updated_resp.status_code == 200 else inst_data
                                    next_due = updated_data.get("next_due_date", "")
                                    next_due_str = next_due.split("T")[0] if next_due else "N/A"
                                    remaining = updated_data.get("amount_remaining", 0)
                                    cust_msg = (
                                        f"✅ *INSTALLMENT PAYMENT CONFIRMED*\n\n"
                                        f"Payment of ₹{amount:,.0f} has been confirmed.\n\n"
                                        f"Your EA is being recompiled for the next {inst_data['installment_amount'] > 0 and inst_data.get('license_period_days') or 35}-day period.\n\n"
                                        f"Remaining balance: ₹{remaining:,.0f}\n"
                                        f"Next payment due: {next_due_str}\n\n"
                                        f"Your updated EA file will be delivered here shortly."
                                    )
                                    await context.bot.send_message(chat_id=telegram_id, text=cust_msg, parse_mode="Markdown")
                    except Exception as e:
                        logging.error(f"Failed to notify customer after payment: {e}")
                else:
                    await query.answer("Failed to record payment.", show_alert=True)
            else:
                await query.answer("Could not fetch installment details.", show_alert=True)
        return


    if data.startswith("check_compile_status_"):
        admin_id = os.getenv("ADMIN_CHAT_ID")
        if str(update.effective_user.id) != str(admin_id):
            await query.answer("Not authorized.", show_alert=True)
            return
            
        order_id = int(data.split("_")[3])
        base_url = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
        import httpx
        async with httpx.AsyncClient(verify=HTTPX_VERIFY) as client:
            order_resp = await client.get(f"{base_url}/orders/{order_id}")
            if order_resp.status_code != 200:
                await query.answer("Order not found.", show_alert=True)
                return
                
            user_id = order_resp.json().get("user_id")
            lic_resp = await client.get(f"{base_url}/licenses/user/{user_id}")
            if lic_resp.status_code == 200:
                lics = lic_resp.json()
                lic = next((l for l in lics if l.get("order_id") == order_id), None)
                if lic:
                    status = lic.get("status")
                    if status == "active":
                        await query.answer("✅ File compiled and sent to customer.", show_alert=True)
                    elif status in ("generating", "pending"):
                        await query.answer("⏳ Still compiling. Will be delivered automatically when done.", show_alert=True)
                    elif status == "failed":
                        await query.answer("❌ Compilation failed. Please contact admin.", show_alert=True)
                    else:
                        await query.answer(f"Status: {status}", show_alert=True)
                else:
                    await query.answer("No license found for this order yet.", show_alert=True)
            else:
                await query.answer("Could not fetch license status.", show_alert=True)
        return

    if data == "license_details":
        await render_licenses(update, context)
        return
        
    if data == "my_installment":
        await render_installment_status(update, context)
        return

    if data.startswith("view_license_"):
        lic_id = int(data.split("_")[2])
        tid = str(update.effective_user.id)
        base_url = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
        
        async with httpx.AsyncClient(verify=HTTPX_VERIFY, follow_redirects=True) as client:
            resp = await client.get(f"{base_url}/licenses/telegram/{tid}")
            if resp.status_code == 200:
                licenses = resp.json()
                lic = next((l for l in licenses if l['id'] == lic_id), None)
                if lic:
                    status_icon = "🟢" if lic['status'] == 'active' else "🔴" if lic['status'] == 'expired' else "⚫"
                    expiry = lic['expiry_date'].split('T')[0] if lic['expiry_date'] else "Never"
                    activated = lic['purchase_date'].split('T')[0] if lic['purchase_date'] else "Unknown"
                    ltype = "Trial" if lic.get('license_type') == 'trial' else "Lifetime"
                    
                    text = (
                        f"📋 *LICENSE DETAILS*\n\n"
                        f"MT5 ID: `{lic['mt5_id']}`\n\n"
                        f"Type:\n{ltype}\n\n"
                        f"Status:\n{status_icon} {lic['status'].title()}\n\n"
                        f"Expiry:\n{expiry}"
                    )
                    
                    kb = []
                    if ltype == "Lifetime":
                        kb.append([InlineKeyboardButton("🔄 Broker Change", callback_data="broker_change")])
                    kb.append([InlineKeyboardButton("🏠 Home", callback_data="home")])
                    
                    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
                    return
        await query.edit_message_text("❌ License not found.")
        return

    if data == "my_orders":
        await render_orders(update, context)
        return
        
    if data == "downloads":
        await render_downloads(update, context)
        return
        
    if data.startswith("download_ea_"):
        parts = data.split("_")
        lic_id = int(parts[2])
        mt5_id = parts[3]
        base_url = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
        
        await query.edit_message_text(f"⏳ Retrieving your EA file for MT5 ID {mt5_id}...")
        
        async with httpx.AsyncClient(verify=HTTPX_VERIFY, follow_redirects=True) as client:
            # We add a security check: ensure the license actually belongs to the user by querying their licenses first
            tid = str(update.effective_user.id)
            resp = await client.get(f"{base_url}/licenses/telegram/{tid}")
            if resp.status_code == 200:
                licenses = resp.json()
                if not any(l['id'] == lic_id for l in licenses):
                    await query.edit_message_text("❌ Access denied. This file does not belong to you.")
                    return
            else:
                await query.edit_message_text("❌ Authorization failed.")
                return
                
            download_url = f"{base_url}/licenses/{lic_id}/download"
            file_resp = await client.get(download_url)
            if file_resp.status_code == 200:
                import io
                doc = io.BytesIO(file_resp.content)
                doc.name = f"InfinityTrader_{mt5_id}.ex5"
                await query.message.reply_document(document=doc, caption=f"📦 Here is your EA for MT5 ID: {mt5_id}")
                await query.edit_message_text("✅ File sent below!")
            else:
                await query.edit_message_text(f"❌ Could not retrieve file for MT5 ID {mt5_id}.\nIt might still be compiling or there is an issue with the storage.")
        return
    if data == "broker_change":
        user_id = context.user_data.get('db_user_id')
        tid = update.effective_user.id
        if not user_id:
            await query.edit_message_text("Session expired. Please send /start again.")
            return
            
        await query.edit_message_text("Fetching your active licenses...")
        base_url = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
        import httpx
        async with httpx.AsyncClient(verify=HTTPX_VERIFY, follow_redirects=True) as client:
            resp = await client.get(f"{base_url}/licenses/telegram/{tid}")
            
        if resp.status_code != 200:
            await query.edit_message_text("Failed to fetch your licenses. Please contact support.")
            return
            
        licenses = resp.json()
        active_licenses = [lic for lic in licenses if lic['status'] == 'active' and lic.get('license_type') == 'paid']
        
        if not active_licenses:
            await query.edit_message_text("You do not have any active Lifetime licenses eligible for a broker change.")
            return
            
        if len(active_licenses) == 1:
            lic = active_licenses[0]
            context.user_data['bc_license_id'] = lic['id']
            context.user_data['bc_old_mt5_id'] = lic['mt5_id']
            context.user_data['bc_old_broker'] = lic.get('broker', 'Unknown')
            
            context.user_data['awaiting_broker_change_mt5_id'] = True
            await query.edit_message_text(
                f"🔄 *Broker Change*\n\nSelected License:\nMT5 ID: `{lic['mt5_id']}`\nBroker: `{lic.get('broker', 'Unknown')}`\n\nPlease enter your **NEW MT5 ID**:",
                parse_mode="Markdown"
            )
            return
            
        msg = (
            "🔄 *BROKER CHANGE*\n\n"
            "You have multiple active EA licenses.\n"
            "Please select the license for which you want to change the broker."
        )
        # Keep only the license id in callback_data (Telegram caps it at 64
        # bytes, and a broker name or MT5 ID containing "_" would break the
        # old split-on-"_" parsing). Store the actual license details in
        # user_data and look them up by id when the button is pressed.
        context.user_data['bc_pending_licenses'] = {str(lic['id']): lic for lic in active_licenses}
        kb = []
        for lic in active_licenses:
            broker_name = lic.get('broker', 'Unknown')
            kb.append([InlineKeyboardButton(f"🔄 MT5 {lic['mt5_id']} - {broker_name}", callback_data=f"bc_select_{lic['id']}")])
        kb.append([InlineKeyboardButton("⬅️ Back", callback_data="main_menu")])
        
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return
        
    if data.startswith("bc_select_"):
        lic_id = data[len("bc_select_"):]
        lic = context.user_data.get('bc_pending_licenses', {}).get(lic_id)
        if not lic:
            await query.edit_message_text("Session expired. Please start the broker change again from the menu.")
            return

        old_mt5 = lic['mt5_id']
        old_broker = lic.get('broker', 'Unknown')

        context.user_data['bc_license_id'] = lic_id
        context.user_data['bc_old_mt5_id'] = old_mt5
        context.user_data['bc_old_broker'] = old_broker
        
        context.user_data['awaiting_broker_change_mt5_id'] = True
        await query.edit_message_text(
            f"🔄 *Broker Change*\n\nSelected License:\nMT5 ID: `{old_mt5}`\nBroker: `{old_broker}`\n\nPlease enter your **NEW MT5 ID**:",
            parse_mode="Markdown"
        )
        return

    if data == "cancel_broker_change":
        context.user_data['bc_license_id'] = None
        context.user_data['bc_new_mt5_id'] = None
        context.user_data['bc_new_broker'] = None
        await query.edit_message_text("❌ Broker change request cancelled.")
        return
        
    if data == "submit_broker_change":
        lic_id = context.user_data.get('bc_license_id')
        new_mt5 = context.user_data.get('bc_new_mt5_id')
        new_broker = context.user_data.get('bc_new_broker')
        tid = update.effective_user.id
        
        if not lic_id or not new_mt5 or not new_broker:
            await query.edit_message_text("Session data lost. Please try again.")
            return
            
        await query.edit_message_text("Submitting your request...")
        from utils.api_client import request_broker_change
        resp = await request_broker_change(lic_id, new_mt5, new_broker, tid)
        
        if "error" in resp:
            await query.edit_message_text(f"❌ Failed: {resp['error']}")
            return
            
        request_id = resp['request_id']
        
        # Notify Admin
        admin_chat_id = os.getenv("ADMIN_CHAT_ID")
        if admin_chat_id:
            admin_msg = (
                f"🔄 *BROKER CHANGE REQUEST*\n\n"
                f"Request ID: BCR-{request_id}\n"
                f"Customer: {context.user_data.get('db_user_name', 'Unknown')}\n"
                f"Telegram ID: `{tid}`\n\n"
                f"Selected License ID: {lic_id}\n"
                f"Old MT5 ID: `{context.user_data.get('bc_old_mt5_id')}`\n"
                f"Old Broker: `{context.user_data.get('bc_old_broker')}`\n\n"
                f"Requested Change:\n"
                f"New MT5 ID: `{new_mt5}`\n"
                f"New Broker: `{new_broker}`\n\n"
                f"Status: Pending Admin Approval"
            )
            kb = [
                [InlineKeyboardButton("✅ APPROVE", callback_data=f"approve_change_{request_id}"),
                 InlineKeyboardButton("❌ REJECT", callback_data=f"reject_change_{request_id}")]
            ]
            try:
                await context.bot.send_message(chat_id=admin_chat_id, text=admin_msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
            except Exception as e:
                logging.error(f"Failed to notify admin: {e}")
                
        await query.edit_message_text("✅ Your broker change request has been submitted and is pending admin approval.")
        
        # Clear state
        context.user_data['bc_license_id'] = None
        context.user_data['bc_new_mt5_id'] = None
        context.user_data['bc_new_broker'] = None
        return

    if data.startswith("approve_change_") or data.startswith("reject_change_"):
        admin_id = os.getenv("ADMIN_CHAT_ID")
        if str(update.effective_user.id) != str(admin_id):
            await query.answer("You are not authorized to perform this action.", show_alert=True)
            return
            
        action = data.split("_")[0]
        request_id = int(data.split("_")[2])
        
        from utils.api_client import approve_broker_change, reject_broker_change
        
        if action == "approve":
            resp = await approve_broker_change(request_id)
            if "error" not in resp:
                await query.edit_message_text(f"✅ Broker Change Request #{request_id} has been APPROVED. New EA is compiling.")
                # Notify User
                try:
                    telegram_id = resp.get("telegram_id")
                    if telegram_id:
                        msg = (
                            f"✅ *Your Broker Change has been approved.*\n\n"
                            f"Your old MT5 ID association has been deactivated.\n"
                            f"Your new Lifetime EA is now compiling and will be sent here shortly."
                        )
                        await context.bot.send_message(chat_id=telegram_id, text=msg, parse_mode="Markdown")
                except Exception as e:
                    logging.error(f"Failed to notify user: {e}")
            else:
                await query.answer(f"Failed: {resp['error']}", show_alert=True)
                
        elif action == "reject":
            resp = await reject_broker_change(request_id)
            if "error" not in resp:
                await query.edit_message_text(f"❌ Broker Change Request #{request_id} has been REJECTED.")
                try:
                    telegram_id = resp.get("telegram_id")
                    if telegram_id:
                        msg = (
                            f"❌ *Broker Change Request Rejected.*\n\n"
                            f"Your existing Lifetime EA remains associated with your current MT5 ID.\n"
                            f"Please contact the admin for assistance."
                        )
                        await context.bot.send_message(chat_id=telegram_id, text=msg, parse_mode="Markdown")
                except:
                    pass
            else:
                await query.answer(f"Failed: {resp['error']}", show_alert=True)
        return

    if data.startswith("admin_edit_"):
        admin_id = os.getenv("ADMIN_CHAT_ID")
        if str(update.effective_user.id) != str(admin_id):
            await query.answer("Unauthorized.", show_alert=True)
            return
            
        setting_key = data.replace("admin_edit_", "")
        context.user_data['awaiting_admin_setting_key'] = setting_key
        await query.edit_message_text(f"Please enter the new value for `{setting_key}`:", parse_mode="Markdown")
        return

    if data == "buy_ea":
        p_type = "EA"
        products = await get_products(product_type=p_type)
        if not products:
            try:
                await query.edit_message_text("No EA products available at this time.", reply_markup=await build_main_menu(update.effective_user.id))
            except Exception:
                pass
            return
            
        user_id = context.user_data.get('db_user_id')
        if not user_id:
            await query.edit_message_text("Session expired. Please send /start again.")
            return
        
        # Only show Lifetime plan (duration == 0), no price on button
        lifetime_plans = [p for p in products if p.get('duration', 0) == 0]
        if not lifetime_plans:
            lifetime_plans = products  # fallback: show all if none are lifetime
        
        if len(lifetime_plans) == 1:
            # Only one plan — skip selection, go straight to MT5 ID
            plan = lifetime_plans[0]
            context.user_data['pending_product_id'] = plan['id']
            context.user_data['pending_p_type'] = p_type
            
            if not context.user_data.get('db_user_phone'):
                await query.edit_message_text("Please enter your **Mobile Number** to continue:", parse_mode="Markdown")
                context.user_data['awaiting_phone'] = True
                return
            
            await proceed_to_order_summary(update, context)
            return
        else:
            # Multiple lifetime plans — show selection without price
            keyboard = []
            for p in lifetime_plans:
                keyboard.append([InlineKeyboardButton(
                    f"📦 {p['name']}",
                    callback_data=f"buy_product_{p['id']}_{p_type}"
                )])
            keyboard.append([InlineKeyboardButton("« Back", callback_data="main_menu")])
            
            await query.edit_message_text(
                "🛒 *Select Your EA Plan*\n\nChoose a plan to continue:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
    elif data == "buy_vps":
        p_type = "VPS"
        products = await get_products(product_type=p_type)
        if not products:
            try:
                await query.edit_message_text(f"No {p_type} products available.", reply_markup=await build_main_menu(update.effective_user.id))
            except Exception:
                pass
            return
            
        keyboard = []
        for p in products:
            keyboard.append([InlineKeyboardButton(f"{p['name']} - ₹{p['price']}", callback_data=f"buy_product_{p['id']}_{p_type}")])
        keyboard.append([InlineKeyboardButton("« Back to Menu", callback_data="main_menu")])
        
        try:
            await query.edit_message_text(f"Please select a {p_type} Plan:", reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception:
            pass
        
    elif data.startswith("buy_product_"):
        parts = data.split("_")
        product_id = int(parts[2])
        p_type = parts[3]
        user_id = context.user_data.get('db_user_id')
        
        if not user_id:
            await query.edit_message_text("Session expired. Please send /start again.")
            return
            
        context.user_data['pending_product_id'] = product_id
        context.user_data['pending_p_type'] = p_type
        
        if not context.user_data.get('db_user_phone'):
            await query.edit_message_text("Please enter your **Mobile Number** to continue with the order:", parse_mode="Markdown")
            context.user_data['awaiting_phone'] = True
            return
            
        # Phone already on file - check if EA or VPS
        if p_type == "EA":
            await proceed_to_order_summary(update, context)
            return
        
        await query.edit_message_text("Please enter your **MT5 ID** to continue with the order:", parse_mode="Markdown")
        context.user_data["awaiting_mt5_id"] = True
        
    elif data == "free_trial":
        user_id = context.user_data.get('db_user_id')
        if not user_id:
            await query.edit_message_text("Session expired. Please send /start again.")
            return
            
        context.user_data['awaiting_trial_mt5_id'] = True
        
        trial_msg = (
            "🆓 *FREE TRIAL*\n\n"
            "Try the EA before purchasing.\n\n"
            "Please enter your **MT5 ID**:"
        )
        try:
            await query.edit_message_text(trial_msg, parse_mode="Markdown")
        except Exception:
            pass
            
    elif data == "main_menu" or data == "home":
        try:
            await query.edit_message_text("Please select an option below:", reply_markup=await build_main_menu(update.effective_user.id))
        except Exception:
            pass

async def proceed_to_order_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    product_id = context.user_data.get('pending_product_id')
    p_type = context.user_data.get('pending_p_type')
    user_id = context.user_data.get('db_user_id')
    mt5_id = context.user_data.get('pending_mt5_id', '')
    
    if not user_id:
        if update.message:
            await update.message.reply_text("Session expired. Please /start again.")
        else:
            await update.callback_query.edit_message_text("Session expired. Please /start again.")
        return
        
    order = await create_order(user_id, product_id, p_type, mt5_id=mt5_id)
    if not order or "error" in order:
        err = order.get("error", "Unknown") if order else "Failed to create order"
        msg = f"❌ *Error:*\n```\n{err}\n```"
        if update.message:
            await update.message.reply_text(msg, parse_mode="Markdown")
        else:
            await update.callback_query.edit_message_text(msg, parse_mode="Markdown")
        return
        
    products = await get_products()
    product = next((p for p in products if p['id'] == product_id), None)
    
    from utils.api_client import get_settings
    settings = await get_settings()
    admin_username = settings.get("support_username", os.getenv("ADMIN_USERNAME", "@infinitytrader004"))
    if not admin_username.startswith("@"):
        admin_username = f"@{admin_username}"
    
    display_mt5 = f"`{mt5_id}`" if mt5_id else "*(Provided after approval)*"
    summary = (
        f"📋 *ORDER SUMMARY*\n\n"
        f"Order ID: #ORD-{order['id']}\n"
        f"👤 Name: {context.user_data.get('db_user_name', 'Unknown')}\n"
        f"📱 Phone: {context.user_data.get('db_user_phone', 'Unknown')}\n"
        f"🖥 MT5 ID: {display_mt5}\n"
        f"📦 Plan: {product['name'] if product else 'Unknown'}\n\n"
        f"Status: ⏳ Pending Admin Approval\n\n"
        f"Please contact the admin to discuss and confirm your order.\n"
        f"Your EA will only be generated after admin approval."
    )
    
    keyboard = [[InlineKeyboardButton("📞 Contact Admin", url=f"https://t.me/{admin_username.lstrip('@')}")] ]
    
    if update.message:
        await update.message.reply_text(summary, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(summary, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        
    admin_chat_id = os.getenv("ADMIN_CHAT_ID")
    if admin_chat_id:
        display_mt5 = f"`{mt5_id}`" if mt5_id else "*(Provided after approval)*"
        admin_msg = (
            f"🆕 *NEW EA ORDER*\n\n"
            f"Order ID: ORD-{order['id']}\n"
            f"Customer Name: {context.user_data.get('db_user_name', 'Unknown')}\n"
            f"Phone: {context.user_data.get('db_user_phone', 'Unknown')}\n"
            f"MT5 ID: {display_mt5}\n"
            f"Telegram ID: `{update.effective_user.id}`\n"
            f"Plan: {product['name'] if product else 'Unknown'}\n"
            f"Status: Pending Admin Approval"
        )
        admin_kb = [
            [
                InlineKeyboardButton("✅ APPROVE", callback_data=f"approve_{order['id']}"),
                InlineKeyboardButton("❌ REJECT", callback_data=f"reject_{order['id']}")
            ]
        ]
        try:
            await context.bot.send_message(
                chat_id=admin_chat_id,
                text=admin_msg,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(admin_kb)
            )
        except Exception as e:
            logging.error(f"Failed to notify admin: {e}")
            
    context.user_data['pending_product_id'] = None
    context.user_data['pending_mt5_id'] = None

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    install_step = context.user_data.get('install_step')
    if install_step:
        order_id = context.user_data.get('install_order_id')
        if install_step == 'total_amount':
            context.user_data['install_total_amount'] = float(text)
            context.user_data['install_step'] = 'installment_amount'
            await update.message.reply_text("Please enter the **Installment amount** (e.g. 5000):", parse_mode="Markdown")
            return
        elif install_step == 'installment_amount':
            context.user_data['install_amount'] = float(text)
            context.user_data['install_step'] = 'installments'
            await update.message.reply_text("Please enter the **Number of installments** (e.g. 4):", parse_mode="Markdown")
            return
        elif install_step == 'installments':
            context.user_data['install_count'] = int(text)
            context.user_data['install_step'] = 'first_payment'
            await update.message.reply_text("Please enter the **First payment amount** (e.g. 5000):", parse_mode="Markdown")
            return
        elif install_step == 'first_payment':
            context.user_data['install_first_payment'] = float(text)
            context.user_data['install_step'] = 'license_duration'
            await update.message.reply_text("Please enter the **License duration per payment in days** (e.g. 35):", parse_mode="Markdown")
            return
        elif install_step == 'license_duration':
            duration = int(text)
            context.user_data['install_step'] = None
            
            payload = {
                "order_id": order_id,
                "total_amount": context.user_data['install_total_amount'],
                "installment_amount": context.user_data['install_amount'],
                "installment_count": context.user_data['install_count'],
                "first_payment_amount": context.user_data['install_first_payment'],
                "license_period_days": duration
            }
            
            base_url = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
            import httpx
            async with httpx.AsyncClient(verify=HTTPX_VERIFY) as client:
                resp = await client.post(f"{base_url}/installments/create", json=payload)
                if resp.status_code == 200:
                    kb = InlineKeyboardMarkup([[InlineKeyboardButton("📋 Manage Installment", callback_data=f"manage_installment_{order_id}")]])
                    await update.message.reply_text(
                        f"✅ *Installment Arrangement Created*\n\n"
                        f"Order #{order_id}\n"
                        f"Total: ₹{payload['total_amount']:,.0f}\n"
                        f"Installment: ₹{payload['installment_amount']:,.0f} × {payload['installment_count']}\n"
                        f"First payment: ₹{payload['first_payment_amount']:,.0f} ✅ Confirmed\n"
                        f"License period: {duration} days\n\n"
                        f"EA is now compiling and will be delivered to the customer.",
                        parse_mode="Markdown",
                        reply_markup=kb
                    )
                    # Notify customer
                    try:
                        order_resp = await client.get(f"{base_url}/orders/{order_id}")
                        if order_resp.status_code == 200:
                            user_id = order_resp.json().get("user_id")
                            user_resp = await client.get(f"{base_url}/users/by-id/{user_id}")
                            if user_resp.status_code == 200:
                                telegram_id = user_resp.json().get("telegram_id")
                                if telegram_id:
                                    cust_msg = (
                                        f"✅ *INSTALLMENT ARRANGEMENT SET UP*\n\n"
                                        f"Your installment plan has been created.\n\n"
                                        f"First payment of ₹{payload['first_payment_amount']:,.0f} has been confirmed.\n"
                                        f"Your EA is now being compiled and will be delivered here shortly.\n\n"
                                        f"License will be active for {duration} days.\n"
                                        f"Remaining balance: ₹{payload['total_amount'] - payload['first_payment_amount']:,.0f}\n\n"
                                        f"Contact admin to confirm each subsequent payment and extend your license."
                                    )
                                    await context.bot.send_message(chat_id=telegram_id, text=cust_msg, parse_mode="Markdown")
                    except Exception as e:
                        logging.error(f"Failed to notify customer on arrangement: {e}")
                else:
                    await update.message.reply_text(f"❌ Error creating arrangement: {resp.text}")
            return


    if context.user_data.get('awaiting_name'):
        context.user_data['awaiting_name'] = False
        tid = context.user_data.get('temp_telegram_id')
        username = context.user_data.get('temp_username')
        
        db_user = await register_user(
            telegram_id=tid, name=text, username=username, phone=None
        )
        if db_user:
            context.user_data['db_user_id'] = db_user['id']
            context.user_data['db_user_name'] = db_user['name']
            
        await update.message.reply_text(f"Thank you, {text}.\n\nPlease enter your **Mobile Number**:", parse_mode="Markdown")
        context.user_data['awaiting_phone'] = True
        return

    if context.user_data.get('awaiting_phone'):
        context.user_data['awaiting_phone'] = False
        phone = text.strip()
        user_id = context.user_data.get('db_user_id')
        
        if user_id:
            from utils.api_client import update_user_phone
            await update_user_phone(user_id, phone)
            context.user_data['db_user_phone'] = phone
            
        # Check if they were in the middle of a purchase
        if context.user_data.get('pending_product_id'):
            p_type = context.user_data.get('pending_p_type')
            if p_type == "EA":
                await proceed_to_order_summary(update, context)
            else:
                await update.message.reply_text(
                    "Please enter your **MT5 ID** to continue:",
                    parse_mode="Markdown"
                )
                context.user_data['awaiting_mt5_id'] = True
            return
            
        welcome_text = (
            f"Registration complete!\n\n"
            "Please select an option below:"
        )
        await update.message.reply_text(welcome_text, reply_markup=await build_main_menu(update.effective_user.id))
        return

    if context.user_data.get('awaiting_mt5_id'):
        context.user_data['awaiting_mt5_id'] = False
        mt5_id = text.strip()
        context.user_data['pending_mt5_id'] = mt5_id
        await proceed_to_order_summary(update, context)
        return

    setting_key = context.user_data.get('awaiting_admin_setting_key')
    if setting_key:
        context.user_data['awaiting_admin_setting_key'] = None
        new_val = text.strip()
        
        from utils.api_client import update_setting
        success = await update_setting(setting_key, new_val)
        if success:
            await update.message.reply_text(f"✅ Setting `{setting_key}` updated to `{new_val}`.", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"❌ Failed to update `{setting_key}`.")
        return

    if context.user_data.get('awaiting_broker_change_mt5_id'):
        context.user_data['awaiting_broker_change_mt5_id'] = False
        new_mt5_id = text.strip()
        context.user_data['bc_new_mt5_id'] = new_mt5_id
        
        context.user_data['awaiting_broker_change_broker_name'] = True
        await update.message.reply_text("Please enter your **NEW BROKER NAME**:", parse_mode="Markdown")
        return

    if context.user_data.get('awaiting_broker_change_broker_name'):
        context.user_data['awaiting_broker_change_broker_name'] = False
        new_broker = text.strip()
        
        lic_id = context.user_data.get('bc_license_id')
        old_mt5 = context.user_data.get('bc_old_mt5_id')
        old_broker = context.user_data.get('bc_old_broker')
        new_mt5_id = context.user_data.get('bc_new_mt5_id')
        
        msg = (
            "📋 *BROKER CHANGE REQUEST*\n\n"
            f"Current MT5 ID: `{old_mt5}`\n"
            f"Current Broker: `{old_broker}`\n\n"
            f"New MT5 ID: `{new_mt5_id}`\n"
            f"New Broker: `{new_broker}`\n\n"
            "License: Lifetime\n"
            "Status: Pending Admin Approval"
        )
        
        context.user_data['bc_new_broker'] = new_broker
        
        kb = [
            [InlineKeyboardButton("📨 Submit Request", callback_data="submit_broker_change")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_broker_change")]
        ]
        
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    if context.user_data.get('awaiting_trial_mt5_id'):
        context.user_data['awaiting_trial_mt5_id'] = False
        mt5_id = text.strip()
        user_id = context.user_data.get('db_user_id')
        tid = str(update.effective_user.id)
        
        from utils.api_client import request_free_trial
        
        await update.message.reply_text("Checking trial eligibility...")
        
        resp = await request_free_trial(tid, mt5_id)
        
        if "error" in resp:
            if resp['error'] == "ALREADY_CLAIMED":
                import datetime
                month_name = datetime.datetime.now().strftime("%B %Y")
                err_msg = (
                    f"⚠️ *FREE TRIAL ALREADY USED*\n\n"
                    f"You have already used your free trial for this month.\n\n"
                    f"Free Trial:\n3 Days\n\n"
                    f"Trial Used:\n{month_name}\n\n"
                    f"You can request another free trial next month."
                )
                kb = [[InlineKeyboardButton("🏠 Home", callback_data="home")]]
                await update.message.reply_text(err_msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
            else:
                err_text = str(resp['error'])[:2000]
                await update.message.reply_text(f"❌ *Trial Request Failed:*\n\n{err_text}", parse_mode="Markdown")
            return
            
        success_msg = (
            f"🎁 *FREE TRIAL ACTIVATED*\n\n"
            f"MT5 ID: `{mt5_id}`\n\n"
            f"Trial Duration: 3 Days\n\n"
            f"Expires:\n{resp.get('expiry_date', 'Unknown')}\n\n"
            f"You may use the trial once this calendar month.\n\n"
            "⚙️ Please wait 1-2 minutes while we compile your trial EA. We will send the file here automatically."
        )
        await update.message.reply_text(success_msg, parse_mode="Markdown")
        return

    await update.message.reply_text("Please use the /start menu to select an option.")

async def render_licenses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = str(update.effective_user.id)
    base_url = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
    
    msg_target = update.message if update.message else update.callback_query
    await msg_target.reply_text("Fetching your licenses...")
    
    async with httpx.AsyncClient(verify=HTTPX_VERIFY, follow_redirects=True) as client:
        resp = await client.get(f"{base_url}/licenses/telegram/{tid}")
        if resp.status_code == 200:
            licenses = resp.json()
            home_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="home")]])
            if not licenses:
                await msg_target.reply_text("❌ *No licenses found.*\n\nYou don't currently have any EA licenses.", parse_mode="Markdown", reply_markup=home_kb)
                return
                
            if len(licenses) == 1:
                l = licenses[0]
                status_icon = "🟢" if l['status'] == 'active' else "🔴" if l['status'] == 'expired' else "⚫"
                expiry = l['expiry_date'].split('T')[0] if l['expiry_date'] else "Never"
                activated = l['purchase_date'].split('T')[0] if l['purchase_date'] else "Unknown"
                ltype = "Trial" if l.get('license_type') == 'trial' else "Lifetime"
                
                text = (
                    f"🔐 *LICENSE DETAILS*\n\n"
                    f"MT5 ID: `{l['mt5_id']}`\n"
                    f"License Type: {ltype}\n"
                    f"Status: {status_icon} {l['status'].title()}\n"
                    f"Activated: {activated}\n"
                    f"Expires: {expiry}"
                )
                await msg_target.reply_text(text, parse_mode="Markdown", reply_markup=home_kb)
                return
                
            # Multiple licenses
            text = "📋 *Your Licenses:*\n\nPlease select a license below to view details or manage it."
            kb = []
            for idx, l in enumerate(licenses, 1):
                status_icon = "🟢" if l['status'] == 'active' else "🔴" if l['status'] == 'expired' else "⚫"
                ltype = "Trial" if l.get('license_type') == 'trial' else "Lifetime"
                button_text = f"MT5 {l['mt5_id']} — {ltype} — {status_icon} {l['status'].title()}"
                
                kb.append([InlineKeyboardButton(button_text, callback_data=f"view_license_{l['id']}")])
                
            kb.append([InlineKeyboardButton("🏠 Home", callback_data="home")])
            await msg_target.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        else:
            await msg_target.reply_text("❌ Unable to load your licenses right now.\nPlease try again or contact support.")

async def render_installment_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Renders the customer's installment status. Shared by the /installment
    command and the 'my_installment' menu button so this logic lives in one
    place instead of being duplicated."""
    from utils.api_client import get_installment_status, get_settings

    tid = str(update.effective_user.id)
    msg_target = update.message if update.message else update.callback_query
    data = await get_installment_status(tid)

    home_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="home")]])

    if data is None:
        await msg_target.reply_text(
            "ℹ️ *No active installment arrangement found.*\n\nIf you have an installment plan, please contact the admin.",
            parse_mode="Markdown",
            reply_markup=home_kb
        )
        return

    license_expiry = data.get("license_expiry", "")
    expiry_str = license_expiry.split("T")[0] if license_expiry else "Never"
    next_due = data.get("next_due_date", "")
    next_due_str = next_due.split("T")[0] if next_due else "Completed"
    status_icon = "🟢" if data.get("license_status") == "active" else "🔴" if data.get("license_status") == "expired" else "⚫"

    payment_warning = ""
    if data.get("installment_status") != "completed" and next_due:
        try:
            next_due_dt = datetime.strptime(next_due.split("T")[0], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            days_left = (next_due_dt - datetime.now(timezone.utc)).days
            payment_warning = "\n⚠️ Payment Due Soon" if days_left <= 5 else "\n✅ Active"
        except Exception:
            pass

    msg = (
        "💳 *YOUR INSTALLMENT PLAN*\n\n"
        f"Plan: {data.get('product_name', 'EA')}\n"
        f"MT5 ID: `{data.get('mt5_id', 'N/A')}`\n\n"
        f"Total Amount: ₹{data.get('total_amount', 0):,.0f}\n"
        f"Installment: ₹{data.get('installment_amount', 0):,.0f}\n\n"
        f"Paid: ₹{data.get('amount_paid', 0):,.0f}\n"
        f"Remaining: ₹{data.get('amount_remaining', 0):,.0f}\n\n"
        f"Progress: {data.get('installments_paid', 0)}/{data.get('installment_count', 0)} payments\n\n"
        f"License: {status_icon} {str(data.get('license_status', 'N/A')).title()}\n"
        f"Expires: {expiry_str}\n"
        f"Next Payment: ₹{data.get('installment_amount', 0):,.0f} (Due: {next_due_str}){payment_warning}\n\n"
        f"To make your next payment, contact the admin."
    )

    settings = await get_settings()
    admin_username = settings.get("support_username", os.getenv("ADMIN_USERNAME", "@infinitytrader004"))
    if not admin_username.startswith("@"):
        admin_username = f"@{admin_username}"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📞 Contact Admin", url=f"https://t.me/{admin_username.lstrip('@')}")],
        [InlineKeyboardButton("🏠 Home", callback_data="home")]
    ])
    await msg_target.reply_text(msg, parse_mode="Markdown", reply_markup=kb)


async def render_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = str(update.effective_user.id)
    base_url = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
    
    msg_target = update.message if update.message else update.callback_query
    await msg_target.reply_text("Fetching your orders...")
    
    async with httpx.AsyncClient(verify=HTTPX_VERIFY, follow_redirects=True) as client:
        resp = await client.get(f"{base_url}/orders/telegram/{tid}")
        if resp.status_code == 200:
            orders = resp.json()
            home_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="home")]])
            if not orders:
                await msg_target.reply_text("📭 *You don't have any orders yet.*", parse_mode="Markdown", reply_markup=home_kb)
                return
                
            text = "🧾 *MY ORDERS*\n\n"
            for order in orders:
                status = order['status']
                if status == "approved" or "approved" in status:
                    status_display = "✅ Approved"
                elif status == "pending_admin_approval":
                    status_display = "⏳ Pending Admin Approval"
                elif status == "rejected":
                    status_display = "❌ Rejected"
                else:
                    status_display = f"ℹ️ {status.replace('_', ' ').title()}"
                    
                created = order['created_at'].split('T')[0] if order.get('created_at') else "Unknown"
                price_str = f"₹{order.get('price', 0):,.0f}" if order.get('price') else "Free"
                
                text += (
                    f"Order #ORD-{order['id']}\n"
                    f"Plan: {order.get('product_name', 'Unknown')}\n"
                    f"Price: {price_str}\n"
                    f"Status: {status_display}\n"
                    f"Created: {created}\n\n"
                )
            
            await msg_target.reply_text(text, parse_mode="Markdown", reply_markup=home_kb)
        else:
            await msg_target.reply_text("❌ Unable to load your orders right now.\nPlease try again or contact support.")

async def orders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await render_orders(update, context)

async def licenses_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await render_licenses(update, context)

async def render_downloads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = str(update.effective_user.id)
    base_url = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
    msg_target = update.message if update.message else update.callback_query
    await msg_target.reply_text("Fetching your downloads...")
    
    async with httpx.AsyncClient(verify=HTTPX_VERIFY, follow_redirects=True) as client:
        resp = await client.get(f"{base_url}/licenses/telegram/{tid}")
        if resp.status_code == 200:
            licenses = resp.json()
            active_licenses = [l for l in licenses if l['status'] == 'active']
            home_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="home")]])
            if not active_licenses:
                await msg_target.reply_text("❌ *No files available.*\n\nYou don't have any active EA licenses to download.", parse_mode="Markdown", reply_markup=home_kb)
                return
                
            text = "📥 *YOUR DOWNLOADS*\n\n"
            kb = []
            
            for idx, l in enumerate(active_licenses, 1):
                ltype = "Trial" if l.get('license_type') == 'trial' else "Lifetime"
                gen = l['purchase_date'].split('T')[0] if l['purchase_date'] else "Unknown"
                
                text += (
                    f"{idx}️⃣ InfinityTrader_{l['mt5_id']}.ex5\n"
                    f"   MT5 ID: {l['mt5_id']}\n"
                    f"   License: {ltype}\n"
                    f"   Generated: {gen}\n\n"
                )
                
                kb.append([InlineKeyboardButton(f"⬇️ Download EA (MT5 {l['mt5_id']})", callback_data=f"download_ea_{l['id']}_{l['mt5_id']}")])
                
            kb.append([InlineKeyboardButton("🏠 Home", callback_data="home")])
            await msg_target.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        else:
            await msg_target.reply_text("❌ Unable to load your downloads right now.\nPlease try again or contact support.")

async def downloads_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await render_downloads(update, context)

import json

class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")
        
    def do_POST(self):
        if self.path == "/internal/delivery":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
                license_id = data.get('license_id')
                if license_id:
                    # We need to trigger an async task to send the document
                    # Since we are in a sync thread, we use asyncio.run_coroutine_threadsafe if we had the event loop
                    # But the simplest way is to use a background thread and requests or httpx to fetch the document
                    # and send it via Telegram API directly.
                    threading.Thread(target=self.send_delivery, args=(license_id,), daemon=True).start()
                    
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
            except Exception as e:
                logging.error(f"Internal delivery error: {e}")
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b"Error")
        else:
            self.send_response(404)
            self.end_headers()

    def send_delivery(self, license_id):
        import asyncio
        asyncio.run(self.async_send_delivery(license_id))
        
    async def async_send_delivery(self, license_id):
        base_url = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        try:
            async with httpx.AsyncClient(verify=HTTPX_VERIFY, follow_redirects=True) as client:
                resp = await client.get(f"{base_url}/licenses/{license_id}/delivery-info")
                if resp.status_code == 200:
                    info = resp.json()
                    chat_id = info.get("telegram_id")
                    mt5_id = info.get("mt5_id")
                    download_url = info.get("download_url")
                    
                    if chat_id and download_url:
                        # Notify customer EA is ready
                        msg = f"✅ *Your EA is Ready!*\n\nYour EA for MT5 ID `{mt5_id}` has been compiled.\nDownloading and sending your file now..."
                        await client.post(
                            f"https://api.telegram.org/bot{token}/sendMessage",
                            json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}
                        )
                        
                        file_resp = await client.get(download_url)
                        admin_chat_id = os.getenv("ADMIN_CHAT_ID")
                        if file_resp.status_code == 200:
                            files = {
                                "document": (f"InfinityTrader_{mt5_id}.ex5", file_resp.content, "application/octet-stream")
                            }
                            send_data = {
                                "chat_id": chat_id,
                                "caption": f"📦 *InfinityTrader EA*\nMT5 ID: `{mt5_id}`\n\n✅ Your EA file is ready. Install it in MetaTrader 5 Expert Advisors folder.",
                                "parse_mode": "Markdown"
                            }
                            doc_resp = await client.post(
                                f"https://api.telegram.org/bot{token}/sendDocument",
                                data=send_data,
                                files=files
                            )
                            if doc_resp.status_code == 200:
                                # Notify admin of successful delivery
                                if admin_chat_id:
                                    await client.post(
                                        f"https://api.telegram.org/bot{token}/sendMessage",
                                        json={
                                            "chat_id": admin_chat_id,
                                            "text": f"✅ *EA Delivered Successfully*\n\nMT5 ID: `{mt5_id}`\nCustomer Telegram: `{chat_id}`\n\nFile sent to customer.",
                                            "parse_mode": "Markdown"
                                        }
                                    )
                            else:
                                admin_chat_id = os.getenv('ADMIN_CHAT_ID')
                                if admin_chat_id:
                                    admin_note = f'✅ EA file delivered to customer.\nMT5 ID: `{mt5_id}`\nTelegram ID: `{chat_id}`'
                                    await client.post(
                                        f'https://api.telegram.org/bot{token}/sendMessage',
                                        json={'chat_id': admin_chat_id, 'text': admin_note, 'parse_mode': 'Markdown'}
                                    )
                        else:
                            logging.error(f"Failed to download EX5: {file_resp.status_code}")
                            admin_chat_id = os.getenv('ADMIN_CHAT_ID')
                            if admin_chat_id:
                                await client.post(
                                    f'https://api.telegram.org/bot{token}/sendMessage',
                                    json={'chat_id': admin_chat_id, 'text': f'❌ Failed to deliver EA to customer {chat_id} (MT5: {mt5_id}). File not found in storage.'}
                                )
        except Exception as e:
            logging.error(f"Delivery failed: {e}")

def start_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), DummyHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    logging.info(f"Webhook server started on port {port}")

from telegram import BotCommand

async def post_init(application):
    commands = [
        BotCommand("start", "Start the bot and see the main menu"),
        BotCommand("licenses", "View your active MT5 licenses"),
        BotCommand("downloads", "Download your compiled EA files"),
        BotCommand("orders", "View your order history"),
        BotCommand("installment", "View your installment plan status")
    ]
    await application.bot.set_my_commands(commands)

async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Your Telegram Chat ID is: `{update.effective_user.id}`", parse_mode="Markdown")

async def admintest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = os.getenv("ADMIN_CHAT_ID")
    if str(update.effective_user.id) != str(admin_id):
        return
    await update.message.reply_text("✅ Admin notification test successful")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = os.getenv("ADMIN_CHAT_ID")
    if str(update.effective_user.id) != str(admin_id):
        await update.message.reply_text("❌ You are not authorized to access the admin panel.")
        return
        
    from utils.api_client import get_settings
    settings = await get_settings()
    
    msg = (
        "⚙️ *Admin Configuration Panel*\n\n"
        f"Free Trial Enabled: `{settings.get('free_trial_enabled', 'Not Set')}`\n"
        f"Trial Duration (Days): `{settings.get('trial_duration', 'Not Set')}`\n"
        f"Max Trials / Month: `{settings.get('max_trials', 'Not Set')}`\n"
        f"Broker Change Fee: `{settings.get('broker_change_fee', 'Not Set')}`\n"
        f"Support Username: `{settings.get('support_username', 'Not Set')}`\n\n"
        "Click a button below to change a setting:"
    )
    
    kb = [
        [InlineKeyboardButton("Edit Trial Status", callback_data="admin_edit_free_trial_enabled"), InlineKeyboardButton("Edit Trial Duration", callback_data="admin_edit_trial_duration")],
        [InlineKeyboardButton("Edit Max Trials", callback_data="admin_edit_max_trials"), InlineKeyboardButton("Edit Change Fee", callback_data="admin_edit_broker_change_fee")],
        [InlineKeyboardButton("Edit Support Username", callback_data="admin_edit_support_username")]
    ]
    
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def installment_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await render_installment_status(update, context)

def main():
    start_dummy_server()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    application = ApplicationBuilder().token(token).post_init(post_init).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("licenses", licenses_command))
    application.add_handler(CommandHandler("downloads", downloads_command))
    application.add_handler(CommandHandler("orders", orders_command))
    application.add_handler(CommandHandler("installment", installment_command))
    application.add_handler(CommandHandler("myid", myid_command))
    application.add_handler(CommandHandler("admintest", admintest_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    logging.info("Starting Infinity Trader Bot...")
    application.run_polling()

if __name__ == '__main__':
    main()
