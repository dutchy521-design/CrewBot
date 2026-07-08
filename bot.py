import telebot
import os
import random
import string
import time
from dotenv import load_dotenv
from telebot import types
from flask import Flask
import threading
from datetime import datetime, timedelta
from supabase import create_client, Client

load_dotenv()

# ---------------- SUPABASE ----------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------- ENV ----------------
TOKEN = os.getenv("TOKEN")
ADMIN_IDS = [
    184339844,
    8206017051,
    5881431845
]
ADMIN_ID = ADMIN_IDS[0]

admin_search_mode = {}
admin_deposit_mode = {}
bot = telebot.TeleBot(TOKEN)
import logging

telebot.logger.setLevel(logging.DEBUG)
def main_menu():

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

    markup.row("👤 Profil", "📸 Einzahlung posten")
    markup.row("🚀 Community")

    markup.row("🛠️ Admin")

    return markup
# ---------------- WEBHOOK FIX ----------------
bot.remove_webhook()

# ---------------- FLASK ----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot läuft 🚀"

# ---------------- MEMORY ----------------
pending_xp_requests = {}

# ---------------- LEVEL NAMES ----------------
def get_level_name(level):
    levels = {
        1: "👋 Neuling",
        2: "🎁 Bonusjäger",
        3: "💰 Sammler",
        4: "🎰 Stammspieler",
        5: "🍀 Glückspilz",
        6: "💎 VIP",
        7: "⭐ Profi",
        8: "🔥 Elite",
        9: "👑 Legende",
        10: "🏆 CrewBoss"
    }
    return levels.get(level, "🏆 CrewBoss")

def get_level(xp):
    print(f"GET_LEVEL wurde aufgerufen mit XP={xp}")

    if xp >= 40000:
        return 10
    elif xp >= 30000:
        return 9
    elif xp >= 22500:
        return 8
    elif xp >= 15000:
        return 7
    elif xp >= 10000:
        return 6
    elif xp >= 5000:
        return 5
    elif xp >= 2000:
        return 4
    elif xp >= 750:
        return 3
    elif xp >= 250:
        return 2

    return 1
# ---------------- HELPERS ----------------
def generate_code():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=6))

def get_user(user_id):
    user_id = str(user_id)
    res = supabase.table("users").select("*").eq("id", user_id).execute()

    if res.data:
        return res.data[0]

    new_user = {
        "id": user_id,
        "first_name": "",
        "username": "",
        "xp": 0,
        "level": 1,
        "invites": 0,
        "ref_code": generate_code(),
        "used_ref": None,
        "invite_list": [],
        "last_xp": None,
        "daily_streak": 0,
        "last_daily": None
    }

    supabase.table("users").upsert(new_user).execute()
    return new_user

def update_user(user_id, fields):
    supabase.table("users").update(fields).eq("id", str(user_id)).execute()

def add_xp(user_id, amount):
    user = get_user(user_id)

    old_level = int(user.get("level", 1))
    xp = int(user.get("xp", 0)) + amount
    new_level = get_level(xp)

    print(f"XP={xp} | OLD={old_level} | NEW={new_level}")

    update_user(user_id, {
        "xp": xp,
        "level": new_level
    })

    if new_level > old_level:

        if new_level == 10:
            bot.send_message(
                user_id,
                "🏆 Glückwunsch!\n\nDu hast den höchsten Rang der Cashout Crew erreicht!\n👑 CrewBoss"
            )
        else:
            bot.send_message(
                user_id,
                f"""🎉 Levelaufstieg!

                ⭐ Du hast Level {new_level} erreicht!

                🏆 Neuer Rang:
                {get_level_name(new_level)}
                """
            )
# ---------------- DAILY ----------------
@bot.message_handler(commands=["daily"])
def daily(message):

    user = get_user(message.from_user.id)
    update_user(message.from_user.id, {
    "first_name": message.from_user.first_name or "",
    "username": message.from_user.username or ""
})
    now = datetime.now()
    last = user.get("last_daily")
    streak = int(user.get("daily_streak") or 0)

    if last:
        try:
            last_dt = datetime.strptime(last, "%Y-%m-%d %H:%M:%S")

            if now.date() == last_dt.date():
                bot.send_message(message.chat.id, "⏳ Daily schon abgeholt!")
                return

            if now.date() == (last_dt + timedelta(days=1)).date():
                streak += 1
            else:
                streak = 1

        except:
            streak = 1
    else:
        streak = 1

    if streak > 7:
        streak = 1

    xp_gain = streak

    add_xp(message.from_user.id, xp_gain)

    update_user(message.from_user.id, {
        "daily_streak": streak,
        "last_daily": now.strftime("%Y-%m-%d %H:%M:%S")
    })

    bot.send_message(
        message.chat.id,
        f"🎁 Daily abgeholt!\n🔥 Streak: {streak}/7\n⭐ +{xp_gain} XP"
    )

# ---------------- START ----------------
@bot.message_handler(commands=["start"])
def start(message):

    args = message.text.split()
    ref = args[1] if len(args) > 1 else None

    user = get_user(message.from_user.id)
    update_user(message.from_user.id, {
    "first_name": message.from_user.first_name or "",
    "username": message.from_user.username or ""
})
    if ref and not user.get("used_ref"):
        ref_user_id = supabase.table("users").select("id").eq("ref_code", ref).execute()

        if ref_user_id.data:
            inviter_id = ref_user_id.data[0]["id"]

            if str(inviter_id) != str(message.from_user.id):

                inviter = get_user(inviter_id)

                invite_list = inviter.get("invite_list") or []
                invite_list.append({
                    "username": message.from_user.username or "unknown",
                    "date": datetime.now().strftime("%d.%m.%Y %H:%M")
                })

                update_user(inviter_id, {
                    "invites": int(inviter.get("invites", 0)) + 1,
                    "invite_list": invite_list
                })

                add_xp(inviter_id, 20)

                update_user(message.from_user.id, {"used_ref": ref})

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Ja, ich bin 18+", callback_data="age_yes"),
        types.InlineKeyboardButton("❌ Nein", callback_data="age_no")
    )

    bot.send_message(message.chat.id, "🔞 Bist du über 18 Jahre alt?", reply_markup=markup)

# ---------------- CALLBACK ----------------
CHANNEL = "@profitplaysports"

@bot.callback_query_handler(func=lambda call: True)
def callback(call):

    chat_id = call.message.chat.id

    if call.data.startswith("xp_menu_"):

        req_id = call.data.split("_")[2]

        markup = types.InlineKeyboardMarkup(row_width=2)

        markup.add(
            types.InlineKeyboardButton("🟢 +10 XP", callback_data=f"xp10_{req_id}"),
            types.InlineKeyboardButton("🟡 +25 XP", callback_data=f"xp25_{req_id}")
        )

        markup.add(
            types.InlineKeyboardButton("🟠 +50 XP", callback_data=f"xp50_{req_id}"),
            types.InlineKeyboardButton("🔴 +100 XP", callback_data=f"xp100_{req_id}")
        )

        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup
        )

        bot.answer_callback_query(call.id)

        return

    if call.data.startswith("xp_yes_"):
        req_id = call.data.split("_")[2]
        data = pending_xp_requests.get(req_id)

        if not data:
            bot.answer_callback_query(call.id, "❌ Anfrage nicht gefunden")
            return

        user_id = data["user_id"]
        note = data["note"]

        add_xp(user_id, 5)

        supabase.table("notes").insert({
            "user_id": user_id,
            "note": note,
            "date": datetime.now().strftime("%d.%m.%Y %H:%M")
        }).execute()

        bot.answer_callback_query(call.id, "✅ XP vergeben")
        bot.send_message(user_id, "💳 Einzahlung bestätigt +5 XP")

        pending_xp_requests.pop(req_id, None)
        return
    
    if (
        call.data.startswith("xp10_")
        or call.data.startswith("xp25_")
        or call.data.startswith("xp50_")
        or call.data.startswith("xp100_")
    ):

        if call.data.startswith("xp10_"):
            xp = 10
            req_id = call.data.split("_")[1]

        elif call.data.startswith("xp25_"):
            xp = 25
            req_id = call.data.split("_")[1]

        elif call.data.startswith("xp50_"):
            xp = 50
            req_id = call.data.split("_")[1]

        else:
            xp = 100
            req_id = call.data.split("_")[1]

        data = pending_xp_requests.get(req_id)

        if not data:
            bot.answer_callback_query(call.id, "ℹ️ Anfrage bereits bearbeitet.")
            return

        user_id = data["user_id"]
        note = data["note"]

        add_xp(user_id, xp)

        supabase.table("notes").insert({
            "user_id": user_id,
            "note": note,
            "date": datetime.now().strftime("%d.%m.%Y %H:%M")
        }).execute()

        bot.answer_callback_query(call.id, f"✅ {xp} XP vergeben")

        bot.send_message(
            user_id,
            f"💳 Einzahlung bestätigt\n⭐ +{xp} XP"
        )
        
        bot.edit_message_caption(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            caption=call.message.caption + f"\n\n✅ {xp} XP vergeben",
            reply_markup=None
        )
        pending_xp_requests.pop(req_id, None)

        return

    if call.data.startswith("xp_no_"):
        req_id = call.data.split("_")[2]
        pending_xp_requests.pop(req_id, None)
        bot.answer_callback_query(call.id, "❌ Abgelehnt")
        return

    if call.data == "age_no":
        bot.send_message(chat_id, "❌ Kein Zugriff.")
        return

    if call.data == "age_yes":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Zum Kanal", url="https://t.me/profitplaysports"))
        markup.add(types.InlineKeyboardButton("✅ Ich bin beigetreten", callback_data="check_channel"))
        bot.send_message(chat_id, "👉 Folgst du schon unserem Kanal?", reply_markup=markup)
        return

    if call.data == "check_channel":
        try:
            member = bot.get_chat_member(CHANNEL, call.from_user.id)
            if member.status not in ["member", "administrator", "creator"]:
                bot.send_message(chat_id, "❌ Nicht im Kanal.")
                return
        except:
            bot.send_message(chat_id, "⚠️ Fehler.")
            return

        user = get_user(chat_id)
        ref_link = f"https://t.me/Crew_1Bot?start={user['ref_code']}"

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🚀 Mini App", web_app=types.WebAppInfo("https://crewbotminiapp.dutchy521.workers.dev/")))
        markup.add(types.InlineKeyboardButton("📦 Deals öffnen", callback_data="open_deals"))

        bot.send_message(
            chat_id,
            f"✅ Freigeschaltet\n\nHier dein persönlicher Einladungslink:\n{ref_link}",
            reply_markup=main_menu()
        )
        return
    if call.data == "open_deals":

        markup = types.InlineKeyboardMarkup()

        markup.add(
            types.InlineKeyboardButton(
                "🔥 SpinBoss",
                url="https://spbs.lynmonkel.com/?mid=374972_2187035"
            )
        )

        markup.add(
            types.InlineKeyboardButton(
                "🎰 Wintino",
                url="https://wtno.pslera.com/?mid=376790_2195828"
            )
        )

        markup.add(
            types.InlineKeyboardButton(
                "🆕 Reelson",
                url="https://reelson.live/tzkkgjhuq"
            )
        )

        bot.send_message(
            chat_id,
            "🎁 Cashout Crew Deals\n\nWähle dein Casino:",
            reply_markup=markup
        )

        return

# ---------------- SCREENSHOT ----------------
@bot.message_handler(content_types=['photo'])
def screenshot(message):

    note = message.caption or "Keine Notiz"
    username = message.from_user.username or "unknown"
    first_name = message.from_user.first_name or "Unbekannt"
    username = message.from_user.username
    timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")

    req_id = str(message.message_id)

    pending_xp_requests[req_id] = {
        "user_id": str(message.from_user.id),
        "note": note
    }

    markup = types.InlineKeyboardMarkup()

    markup.add(
        types.InlineKeyboardButton("💰 XP vergeben", callback_data=f"xp_menu_{req_id}")
    )

    markup.add(
        types.InlineKeyboardButton("❌ Ablehnen", callback_data=f"xp_no_{req_id}")
    )

    for admin_id in ADMIN_IDS:

        bot.send_photo(
            admin_id,
            message.photo[-1].file_id,
            caption=(
            f"📸 Screenshot\n"
            f"👤 {first_name}\n"
            f"📱 {'@' + username if username else 'Kein Username'}\n"
            f"🕒 {timestamp}\n\n"
            f"💬 {note}"
        ),
            reply_markup=markup
        )

# ---------------- NOTES ----------------
@bot.message_handler(commands=["notes"])
def notes(message):

    res = supabase.table("notes").select("*").eq("user_id", str(message.from_user.id)).execute()

    if not res.data:
        bot.send_message(message.chat.id, "Keine Einzahlungen")
        return

    text = "💰 Einzahlungen:\n\n"

    for n in res.data:
        text += f"{n['note']} ({n['date']})\n"

    bot.send_message(message.chat.id, text)

# ---------------- XP ----------------

@bot.message_handler(func=lambda m: m.text == "👤 Profil")
def profile_button(message):

    user = get_user(message.from_user.id)

    ref_link = f"https://t.me/Crew_1Bot?start={user['ref_code']}"
    notes = supabase.table("notes")\
        .select("*")\
        .eq("user_id", str(message.from_user.id))\
        .execute()
    deposit_count = len(notes.data) if notes.data else 0
    deposits = ""

    if notes.data:

        deposits = "\n💰 Letzte Einzahlungen:\n\n"

        for n in notes.data[-5:]:
            deposits += f"• {n['note']}\n"
    text = f"""
👤 {user.get('first_name') or 'Spieler'}

⭐ Level: {user.get('level', 1)}
🏆 {get_level_name(user.get('level', 1))}

📊 XP Gesamt: {user.get('xp', 0)}
📸 Bestätigte Einzahlungen: {deposit_count}

👥 Deine Einladungen: {user.get('invites', 0)}

🔗 Dein Ref-Link:

{ref_link}

{deposits}
"""

    bot.send_message(
        message.chat.id,
        text
    )

@bot.message_handler(func=lambda m: m.text == "📸 Einzahlung posten")
def deposit_button(message):

    bot.send_message(
        message.chat.id,
        """📸 Einzahlung einreichen

Sende einfach einen Screenshot deiner Einzahlung.

Schreibe als Text dazu:

💰 Betrag
🎰 Casino

Beispiel:

30€ Hype Casino

oder

50€ Rooli

Ein Admin prüft deinen Screenshot anschließend und vergibt die XP. ⭐"""
    )
@bot.message_handler(func=lambda m: m.text == "🚀 Community")
def group_button(message):

    bot.send_message(
        message.chat.id,
        "👥 Hier geht's direkt zu unserer Community:\n\nhttps://t.me/+9-h-MOTRqs9lMjQy"
    )

@bot.message_handler(func=lambda m: m.text == "🛠️ Admin")
def admin_panel(message):

    if message.from_user.id not in ADMIN_IDS:
        return

    markup = types.ReplyKeyboardMarkup(
        resize_keyboard=True
    )

    markup.row("📊 Statistiken")
    markup.row("👤 User suchen")
    markup.row("💰 Letzte Einzahlungen")
    markup.row("🎁 Admin Einzahlung")
    markup.row("🏆 Top Kunden")
    markup.row("🔙 Zurück")
    bot.send_message(
        message.chat.id,
        "🛠️ Adminbereich",
        reply_markup=markup
    )

@bot.message_handler(func=lambda m: m.text == "🔙 Zurück")
def back_button(message):

    bot.send_message(
        message.chat.id,
        "🏠 Hauptmenü",
        reply_markup=main_menu()
    )
@bot.message_handler(func=lambda m: m.text == "📊 Statistiken")
def stats_button(message):

    if message.from_user.id not in ADMIN_IDS:
        return

    users = supabase.table("users").select("*").execute()
    notes = supabase.table("notes").select("*").execute()

    user_count = len(users.data) if users.data else 0
    deposit_count = len(notes.data) if notes.data else 0

    total_xp = 0
    total_invites = 0

    if users.data:
        for user in users.data:
            total_xp += user.get("xp", 0) or 0
            total_invites += user.get("invites", 0) or 0

    bot.send_message(
        message.chat.id,
        f"""📊 Cashout Crew Statistik

👥 User: {user_count}

📸 Einzahlungen: {deposit_count}

⭐ XP Gesamt: {total_xp}

👥 Einladungen: {total_invites}
"""
    )

@bot.message_handler(func=lambda m: m.text == "👤 User suchen")
def search_user_button(message):

    if message.from_user.id not in ADMIN_IDS:
        return

    admin_search_mode[message.from_user.id] = True

    bot.send_message(
        message.chat.id,
        "👤 Bitte Username eingeben (ohne @)"
    )

@bot.message_handler(func=lambda m: m.from_user.id in admin_search_mode)
def search_user_handler(message):

    if message.from_user.id not in ADMIN_IDS:
        return

    username = message.text.replace("@", "").strip()

    res = supabase.table("users")\
        .select("*")\
        .eq("username", username)\
        .execute()

    admin_search_mode.pop(message.from_user.id, None)

    if not res.data:

        bot.send_message(
            message.chat.id,
            "❌ Kein Benutzer gefunden."
        )
        return

    user = res.data[0]

    notes = supabase.table("notes")\
        .select("*")\
        .eq("user_id", str(user["id"]))\
        .execute()
    admin_deposits = supabase.table("admin_deposits")\
    .select("*")\
    .eq("username", user.get("username"))\
    .execute()

    deposit_count = len(notes.data) if notes.data else 0
    last_deposits = ""
    admin_text = ""
    admin_total = 0
    if notes.data:

        last_deposits = "\n💰 Letzte Einzahlungen:\n"

        for n in notes.data[-3:]:
            last_deposits += f"\n• {n['note']}"

    if admin_deposits.data:

        admin_text = "\n\n🎁 Admin-Einzahlungen:\n"

        for d in admin_deposits.data:

            amount = d.get("amount", 0) or 0
            admin_total += float(amount)

            admin_text += (
                f"\n• {amount}€ "
                f"{d.get('brand', '-')}"
                f" ({d.get('reason', '-')})"
            )

        admin_text += f"\n\n💰 Gesamt erhalten: {admin_total:.0f}€"
    bot.send_message(
    message.chat.id,
    f"""👤 {user.get('first_name') or 'Unbekannt'}

📛 Username: @{user.get('username') or '-'}

🆔 ID: {user.get('id')}

⭐ XP: {user.get('xp', 0)}
🏆 Level: {user.get('level', 1)}

👥 Einladungen: {user.get('invites', 0)}

🎭 Avatar: {user.get('avatar', '-')}

🔗 Ref-Code: {user.get('ref_code', '-')}

📸 Einzahlungen: {deposit_count}

{last_deposits}

{admin_text}
"""
)

@bot.message_handler(func=lambda m: m.text == "💰 Letzte Einzahlungen")
def latest_deposits(message):

    if message.from_user.id not in ADMIN_IDS:
        return

    notes = supabase.table("notes")\
        .select("*")\
        .execute()

    if not notes.data:

        bot.send_message(
            message.chat.id,
            "❌ Keine Einzahlungen gefunden."
        )
        return

    text = "💰 Letzte Einzahlungen\n\n"

    for n in notes.data[-10:]:

        user_id = n.get("user_id")

        user = get_user(user_id)

        username = user.get("username") or "unbekannt"

        text += f"👤 @{username}\n"
        text += f"💳 {n['note']}\n\n"

    bot.send_message(
        message.chat.id,
        text
    )

@bot.message_handler(func=lambda m: m.text == "🎁 Admin Einzahlung")
def admin_deposit_start(message):

    if message.from_user.id not in ADMIN_IDS:
        return
    admin_search_mode.pop(message.from_user.id, None)
    admin_deposit_mode[message.from_user.id] = {
        "step": "username"
    }

    bot.send_message(
        message.chat.id,
        "👤 Username eingeben (ohne @)"
    )

@bot.message_handler(func=lambda m: m.from_user.id in admin_deposit_mode)
def admin_deposit_handler(message):

    if message.from_user.id not in ADMIN_IDS:
        return

    data = admin_deposit_mode[message.from_user.id]

    if data["step"] == "username":

        data["username"] = message.text.replace("@", "").strip()
        data["step"] = "brand"

        bot.send_message(
            message.chat.id,
            "🎰 Brand eingeben"
        )
        return

    if data["step"] == "brand":

        data["brand"] = message.text.strip()
        data["step"] = "amount"

        bot.send_message(
            message.chat.id,
            "💰 Betrag eingeben"
        )
        return

    if data["step"] == "amount":

        data["amount"] = message.text.strip()
        data["step"] = "reason"

        bot.send_message(
            message.chat.id,
            "📝 Grund eingeben (Neukunde, Level-Up, Quiz usw.)"
        )
        return

    if data["step"] == "reason":

        data["reason"] = message.text.strip()

        supabase.table("admin_deposits").insert({
            "username": data["username"],
            "brand": data["brand"],
            "amount": str(data["amount"]).replace("€", ""),
            "reason": data["reason"],
            "admin_name": message.from_user.first_name or "Admin"
        }).execute()

        admin_deposit_mode.pop(message.from_user.id, None)
        admin_search_mode.pop(message.from_user.id, None)
        bot.send_message(
            message.chat.id,
            f"""✅ Admin-Einzahlung gespeichert

👤 {data['username']}
🎰 {data['brand']}
💰 {data['amount']}€
📝 {data['reason']}
"""
        )

@bot.message_handler(func=lambda m: m.text == "🏆 Top Kunden")
def customer_overview(message):

    if message.from_user.id not in ADMIN_IDS:
        return

    users = supabase.table("users")\
        .select("*")\
        .execute()
    users.data = sorted(
        users.data,
        key=lambda x: x.get("xp", 0) or 0,
        reverse=True
    )

    if not users.data:

        bot.send_message(
            message.chat.id,
            "❌ Keine Nutzer gefunden."
        )
        return

    text = "🏆 Top Kunden\n\n"

    for user in users.data[:20]:

        username = user.get("username") or "unbekannt"

        notes = supabase.table("notes")\
            .select("*")\
            .eq("user_id", str(user["id"]))\
            .execute()

        own_deposits = len(notes.data) if notes.data else 0

        admin_deposits = supabase.table("admin_deposits")\
            .select("*")\
            .eq("username", username)\
            .execute()

        admin_count = 0
        admin_total = 0

        if admin_deposits.data:

            admin_count = len(admin_deposits.data)

            for d in admin_deposits.data:

                amount = d.get("amount", 0) or 0
                admin_total += float(amount)

        text += (
            f"👤 @{username}\n"
            f"📸 Eigene Einzahlungen: {own_deposits}\n"
            f"🎁 Admin-Einzahlungen: {admin_count}\n"
            f"💰 Erhalten: {admin_total:.0f}€\n\n"
        )

    bot.send_message(
        message.chat.id,
        text
    )
# ---------------- BROADCAST ----------------
@bot.message_handler(commands=["broadcast"])
def broadcast(message):

    if message.from_user.id not in ADMIN_IDS:
        return

    text = message.text.replace("/broadcast", "").strip()

    if not text:
        bot.send_message(message.chat.id, "❌ Bitte Nachricht eingeben.")
        return

    users = supabase.table("users").select("*").execute()

    sent = 0

    for user in users.data:

        try:
            user_id = user["id"]
            first_name = user.get("first_name") or "Crew-Mitglied"
            final_text = f"""
👋 Hallo {first_name},

{text}

🍀 Viel Glück!
"""

            bot.send_message(user_id, final_text)

            sent += 1

        except Exception as e:
            print(e)

    bot.send_message(message.chat.id, f"✅ Rundmail an {sent} User gesendet.")
# ---------------- RUN ----------------
def run():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

if __name__ == "__main__":
    import sys

    if os.getenv("RUN_MAIN") == "true":
        sys.exit()

    flask_thread = threading.Thread(target=run)
    flask_thread.daemon = True
    flask_thread.start()

    while True:
        try:
            print(">>> Polling gestartet...")

            bot.infinity_polling(
                skip_pending=True,
                timeout=20,
                long_polling_timeout=20
            )

        except Exception:
            import traceback
            traceback.print_exc()
            print(">>> Neustart in 5 Sekunden...")
            time.sleep(5)