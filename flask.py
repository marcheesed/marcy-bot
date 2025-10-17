import os
import threading
from flask import Flask
from main import bot, DISCORD_TOKEN  # import your bot instance and token

# --- Flask app ---
app = Flask(__name__)


@app.route("/")
def home():
    return "Marcy-Bot is running!"


def run_flask():
    port = int(os.environ.get("PORT", 10000))  # Render assigns $PORT automatically
    app.run(host="0.0.0.0", port=port)


# --- Start Flask in a separate thread ---
threading.Thread(target=run_flask).start()

# --- Run Discord bot ---
bot.run(DISCORD_TOKEN)
