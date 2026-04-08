"""
SD Reply Cog — listens for PNG info strings in a configured channel,
queues generation jobs, and replies with results one at a time.

Queue behaviour:
  - Each valid PNG info message is added to an asyncio.Queue (FIFO).
  - A single background worker processes jobs sequentially so only one
    generation runs against the reForge API at a time.
  - Reactions on the original message show live status:
      🕐  queued (waiting)
      ⚙️  generating now
      ✅  done
      ❌  error
"""

import asyncio
import io
import base64
import json
import textwrap
from dataclasses import dataclass

import aiohttp
import discord
from discord.ext import commands

from .utils import load_config, parse_pnginfo

_FIELD_MAX = 1024


@dataclass
class _Job:
    message: discord.Message
    payload: dict
    sd_api_url: str


class SDReplyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._session: aiohttp.ClientSession | None = None
        self._queue: asyncio.Queue[_Job] = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None

    async def cog_load(self):
        self._session = aiohttp.ClientSession()
        self._worker_task = asyncio.create_task(self._worker(), name="sd-reply-worker")

    async def cog_unload(self):
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        if self._session:
            await self._session.close()

    # ------------------------------------------------------------------
    # Message listener — validates and enqueues
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        config = load_config()
        listen_channel_id = config.get("listen_channel_id")
        if not listen_channel_id or message.channel.id != listen_channel_id:
            return

        payload = parse_pnginfo(message.content)
        if payload is None:
            return  # not a PNG info string, ignore silently

        sd_api_url = config.get("sd_api_url", "http://127.0.0.1:7860")

        queue_pos = self._queue.qsize()  # jobs waiting (excludes the one currently running)
        job = _Job(message=message, payload=payload, sd_api_url=sd_api_url)
        await self._queue.put(job)

        await self._set_reaction(message, "🕐")

        # Let the user know their position if something is already in flight
        if queue_pos > 0:
            await message.reply(
                f"Queued at position {queue_pos + 1}. Please wait.",
                mention_author=False,
                delete_after=10,
            )

    # ------------------------------------------------------------------
    # Background worker — processes jobs one at a time
    # ------------------------------------------------------------------

    async def _worker(self):
        while True:
            job = await self._queue.get()
            try:
                await self._process(job)
            except Exception as exc:
                print(f"[SD Reply] Unhandled worker error: {exc}")
            finally:
                self._queue.task_done()

    async def _process(self, job: _Job):
        message = job.message

        await self._set_reaction(message, "⚙️")

        try:
            async with message.channel.typing():
                image_bytes, used_seed = await self._generate(job.sd_api_url, job.payload)

        except aiohttp.ClientConnectorError:
            await message.reply(
                "Could not connect to the reForge API.\n"
                "Make sure reForge is running with the `--api` flag.",
                mention_author=False,
            )
            await self._set_reaction(message, "❌")
            return

        except SDAPIError as exc:
            await message.reply(f"SD API error: {exc}", mention_author=False)
            await self._set_reaction(message, "❌")
            return

        embed = self._build_embed(job.payload, used_seed)
        file = discord.File(fp=io.BytesIO(image_bytes), filename="generated.png")
        embed.set_image(url="attachment://generated.png")

        await message.reply(embed=embed, file=file, mention_author=False)
        await self._set_reaction(message, "✅")

    # ------------------------------------------------------------------
    # SD API call
    # ------------------------------------------------------------------

    async def _generate(self, api_url: str, payload: dict) -> tuple[bytes, int]:
        endpoint = f"{api_url}/sdapi/v1/txt2img"

        async with self._session.post(
            endpoint,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=600),
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise SDAPIError(f"HTTP {resp.status}: {body[:300]}")
            data = await resp.json()

        image_bytes = base64.b64decode(data["images"][0])
        info = json.loads(data.get("info", "{}"))
        used_seed = info.get("seed", payload.get("seed", -1))

        return image_bytes, used_seed

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _set_reaction(self, message: discord.Message, emoji: str):
        """Replace all bot reactions on a message with a single new one."""
        try:
            for reaction in message.reactions:
                if reaction.me:
                    await message.remove_reaction(reaction.emoji, self.bot.user)
        except discord.HTTPException:
            pass
        try:
            await message.add_reaction(emoji)
        except discord.HTTPException:
            pass

    @staticmethod
    def _build_embed(payload: dict, used_seed: int) -> discord.Embed:
        embed = discord.Embed(title="Image Generated", color=0x5865F2)

        prompt = payload.get("prompt", "")
        if prompt:
            embed.add_field(
                name="Prompt",
                value=f"```{textwrap.shorten(prompt, _FIELD_MAX - 6, placeholder='...')}```",
                inline=False,
            )

        negative = payload.get("negative_prompt", "")
        if negative:
            embed.add_field(
                name="Negative Prompt",
                value=f"```{textwrap.shorten(negative, _FIELD_MAX - 6, placeholder='...')}```",
                inline=False,
            )

        parts = [
            f"Seed: `{used_seed}`",
            f"Steps: `{payload.get('steps', '?')}`",
            f"CFG: `{payload.get('cfg_scale', '?')}`",
            f"Sampler: `{payload.get('sampler_name', '?')}`",
        ]
        if "width" in payload and "height" in payload:
            parts.append(f"Size: `{payload['width']}x{payload['height']}`")
        model = payload.get("override_settings", {}).get("sd_model_checkpoint", "")
        if model:
            parts.append(f"Model: `{model}`")

        embed.add_field(name="Parameters", value="\n".join(parts), inline=False)
        return embed


class SDAPIError(Exception):
    pass


async def setup(bot: commands.Bot):
    await bot.add_cog(SDReplyCog(bot))
