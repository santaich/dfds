"""
SD Reply Cog — listens for PNG info strings in a configured channel,
generates an image via the reForge API, and replies with the result.
"""

import io
import base64
import textwrap
import aiohttp
import discord
from discord.ext import commands
from .utils import load_config, parse_pnginfo

# Max characters shown for prompt/negative prompt in the reply embed
_FIELD_MAX = 1024


class SDReplyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Re-use a single aiohttp session for the lifetime of the cog
        self._session: aiohttp.ClientSession | None = None

    async def cog_load(self):
        self._session = aiohttp.ClientSession()

    async def cog_unload(self):
        if self._session:
            await self._session.close()

    # ------------------------------------------------------------------
    # Message listener
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots (including self)
        if message.author.bot:
            return

        config = load_config()
        listen_channel_id = config.get("listen_channel_id")
        if not listen_channel_id or message.channel.id != listen_channel_id:
            return

        payload = parse_pnginfo(message.content)
        if payload is None:
            # Not a valid PNG info string — ignore silently
            return

        sd_api_url = config.get("sd_api_url", "http://127.0.0.1:7860")

        async with message.channel.typing():
            try:
                image_bytes, used_seed = await self._generate(sd_api_url, payload)
            except aiohttp.ClientConnectorError:
                await message.reply(
                    "Could not connect to the reForge API. Is it running?",
                    mention_author=False,
                )
                return
            except SDAPIError as e:
                await message.reply(f"SD API error: {e}", mention_author=False)
                return

        embed = self._build_embed(payload, used_seed)
        file = discord.File(fp=io.BytesIO(image_bytes), filename="generated.png")
        embed.set_image(url="attachment://generated.png")

        await message.reply(embed=embed, file=file, mention_author=False)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _generate(self, api_url: str, payload: dict) -> tuple[bytes, int]:
        """
        POST to /sdapi/v1/txt2img and return (png_bytes, actual_seed).
        Raises SDAPIError on non-200 responses.
        """
        endpoint = f"{api_url}/sdapi/v1/txt2img"

        async with self._session.post(endpoint, json=payload, timeout=aiohttp.ClientTimeout(total=300)) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise SDAPIError(f"HTTP {resp.status}: {body[:200]}")
            data = await resp.json()

        image_b64: str = data["images"][0]
        image_bytes = base64.b64decode(image_b64)

        # Extract actual seed from the info JSON embedded in the response
        import json as _json
        info = _json.loads(data.get("info", "{}"))
        used_seed = info.get("seed", payload.get("seed", -1))

        return image_bytes, used_seed

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

        params_parts = [
            f"Seed: `{used_seed}`",
            f"Steps: `{payload.get('steps', '?')}`",
            f"CFG: `{payload.get('cfg_scale', '?')}`",
            f"Sampler: `{payload.get('sampler_name', '?')}`",
        ]
        if "width" in payload and "height" in payload:
            params_parts.append(f"Size: `{payload['width']}x{payload['height']}`")
        if "override_settings" in payload:
            model = payload["override_settings"].get("sd_model_checkpoint", "")
            if model:
                params_parts.append(f"Model: `{model}`")

        embed.add_field(name="Parameters", value="\n".join(params_parts), inline=False)
        return embed


class SDAPIError(Exception):
    pass


async def setup(bot: commands.Bot):
    await bot.add_cog(SDReplyCog(bot))
