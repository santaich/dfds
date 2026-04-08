"""
Discord Bot entry point — loads cogs and starts the bot.
"""

import asyncio
import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ["DISCORD_BOT_TOKEN"]

COGS = [
    "cogs.admin",
    "cogs.sd_reply",
]


class SDBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        for cog in COGS:
            await self.load_extension(cog)
            print(f"[Bot] Loaded {cog}")
        await self.tree.sync()
        print("[Bot] Slash commands synced.")

    async def on_ready(self):
        print(f"[Bot] Logged in as {self.user} (ID: {self.user.id})")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="for PNG info strings",
            )
        )


if __name__ == "__main__":
    bot = SDBot()
    bot.run(BOT_TOKEN)
