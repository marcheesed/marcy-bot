import discord
from discord.ext import commands
import re
from dotenv import load_dotenv
import os
from flask import Flask, jsonify, send_file
import threading
import asyncio
from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("No Discord token in .env!")

# ---------------- Discord Bot Setup ----------------
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


def load_roles(file_path):
    roles = {}
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("-"):
                continue
            # Match "emoji name #hex"
            match = re.match(r"^(\S+)\s+(.+?)\s+(#[0-9A-Fa-f]{6})$", line)
            if match:
                emoji, role_name, color_hex = match.groups()
                roles[emoji] = {
                    "name": role_name,
                    "color": int(color_hex.lstrip("#"), 16),
                }
    return roles


# Load both sets
color_roles = load_roles("roles.txt")
pronoun_roles = load_roles("pronouns.txt")
boundary_roles = load_roles("boundaries.txt")


# --- Create or update roles ---
async def ensure_roles_exist(guild):
    for roles_dict in [color_roles, pronoun_roles]:
        for emoji, data in roles_dict.items():
            existing = discord.utils.get(guild.roles, name=data["name"])
            if not existing:
                await guild.create_role(
                    name=data["name"], color=discord.Color(data["color"])
                )
            else:
                if existing.color.value != data["color"]:
                    await existing.edit(color=discord.Color(data["color"]))


# --- Helper: read/write tracked message IDs ---
def get_tracked_ids():
    try:
        with open("tracked_message.txt", "r") as f:
            return [int(x.strip()) for x in f.readlines() if x.strip()]
    except FileNotFoundError:
        return []


def save_tracked_id(message_id):
    with open("tracked_message.txt", "a") as f:
        f.write(str(message_id) + "\n")


# --- Command to post the reaction messages ---


@bot.command()
async def postboundaries(ctx):
    # Ensure these roles exist
    for emoji, data in boundary_roles.items():
        existing = discord.utils.get(ctx.guild.roles, name=data["name"])
        if not existing:
            await ctx.guild.create_role(
                name=data["name"], color=discord.Color(data["color"])
            )
        else:
            if existing.color.value != data["color"]:
                await existing.edit(color=discord.Color(data["color"]))

    # Post messages
    emojis = list(boundary_roles.keys())
    chunk_size = 8

    for i in range(0, len(emojis), chunk_size):
        chunk = emojis[i : i + chunk_size]
        description = "React to get a boundary role:\n\n"
        for emoji in chunk:
            data = boundary_roles[emoji]
            description += f"{emoji} — {data['name']}\n"

        embed = discord.Embed(
            title="Marcy's Boundary Roles",
            description=description,
            color=0xFF69B4,
        )
        message = await ctx.send(embed=embed)

        for emoji in chunk:
            await message.add_reaction(emoji)
            save_tracked_id(message.id)


@bot.command()
async def postpronouns(ctx):
    await ensure_roles_exist(
        ctx.guild
    )  # ensures both color & pronoun roles exist, or just pronoun if you want

    emojis = list(pronoun_roles.keys())
    chunk_size = 8

    for i in range(0, len(emojis), chunk_size):
        chunk = emojis[i : i + chunk_size]
        description = "React to get a pronoun role:\n\n"
        for emoji in chunk:
            data = pronoun_roles[emoji]
            description += f"{emoji} — {data['name']}\n"

        embed = discord.Embed(
            title="Marcy's Pronoun Roles",
            description=description,
            color=0x04943B,
        )
        message = await ctx.send(embed=embed)

        for emoji in chunk:
            await message.add_reaction(emoji)

        save_tracked_id(message.id)


@bot.command()
async def postroles(ctx):
    await ensure_roles_exist(ctx.guild)

    emojis = list(reaction_roles.keys())
    chunk_size = 8

    for i in range(0, len(emojis), chunk_size):
        chunk = emojis[i : i + chunk_size]
        description = "React to get a color role:\n\n"
        for emoji in chunk:
            data = reaction_roles[emoji]
            description += f"{emoji} — {data['name']}\n"

        embed = discord.Embed(
            title="Marcy's Color Roles",
            description=description,
            color=0x04943B,
        )
        message = await ctx.send(embed=embed)

        for emoji in chunk:
            await message.add_reaction(emoji)

        save_tracked_id(message.id)


# --- Reaction handlers ---
@bot.event
async def on_raw_reaction_add(payload):
    if payload.member.bot:
        return
    tracked_ids = get_tracked_ids()
    if payload.message_id not in tracked_ids:
        return

    guild = bot.get_guild(payload.guild_id)
    emoji = str(payload.emoji)

    for roles_dict in [color_roles, pronoun_roles, boundary_roles]:
        if emoji in roles_dict:
            role_name = roles_dict[emoji]["name"]
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                await payload.member.add_roles(role)


@bot.event
async def on_raw_reaction_remove(payload):
    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    if not member or member.bot:
        return
    tracked_ids = get_tracked_ids()
    if payload.message_id not in tracked_ids:
        return

    emoji = str(payload.emoji)

    for roles_dict in [color_roles, pronoun_roles, boundary_roles]:
        if emoji in roles_dict:
            role_name = roles_dict[emoji]["name"]
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                await member.remove_roles(role)


# ---------------- Flask App Setup ----------------
app = Flask(__name__)


@app.route("/")
def bot_status_image():
    # Get bot avatar URL
    bot_user = bot.user
    if bot_user is None:
        # Bot not ready yet
        status_text = "Offline"
        avatar_url = "https://file.garden/aBi0tvXzESnPXzr_/56a89d72d4c48d2bcb34e454b4d3c38e.jpg"  # placeholder image
        bot_name = "Bot"
    else:
        status_text = "Active"
        avatar_url = str(bot_user.avatar.url)
        bot_name = bot_user.name

    # Download avatar
    response = requests.get(avatar_url)
    avatar_img = Image.open(BytesIO(response.content)).convert("RGBA")

    # Create a new image
    width, height = 300, 128
    img = Image.new("RGBA", (width, height), (30, 30, 30, 255))  # dark background

    # Paste avatar
    avatar_img = avatar_img.resize((128, 128))
    img.paste(avatar_img, (0, 0), avatar_img)

    # Add text
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()

    # Bot name on top
    draw.text((140, 10), f"{bot_user.name}", fill=(255, 255, 255, 255), font=font)

    # Bot status below
    draw.text(
        (140, 30), f"Bot Status: {status_text}", fill=(255, 255, 255, 255), font=font
    )

    # Save to BytesIO
    output = BytesIO()
    img.save(output, format="PNG")
    output.seek(0)

    return send_file(output, mimetype="image/png")


# ---------------- Run both ----------------
def run_flask():
    app.run(host="0.0.0.0", port=5000)


def run_bot():
    asyncio.run(bot.start(TOKEN))


if __name__ == "__main__":
    # Start Flask in a separate thread
    threading.Thread(target=run_flask).start()
    # Run Discord bot in main thread
    run_bot()
