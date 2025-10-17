import os
import threading
from flask import Flask
from main import bot, DISCORD_TOKEN

# Flask app
app = Flask(__name__)


@app.route("/")
def home():
    return "Marcy-Bot is running!"


def run_flask():
    port = int(os.environ.get("PORT", 10000))  # use Render's assigned port
    app.run(host="0.0.0.0", port=port)


# Start Flask in daemon thread
threading.Thread(target=run_flask, daemon=True).start()

# Run Discord bot
bot.run(DISCORD_TOKEN)
