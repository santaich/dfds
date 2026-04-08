"""
Shared utilities: config I/O and PNG info parser.
"""

import json
import re
import random
from pathlib import Path

CONFIG_FILE = Path(__file__).parent.parent / "bot_config.json"


def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "upload_channel_id": None,
        "listen_channel_id": None,
        "sd_api_url": "http://127.0.0.1:7860",
    }


def save_config(config: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


# ---------------------------------------------------------------------------
# PNG info parser
# ---------------------------------------------------------------------------

# Keys that appear in the parameter line (case-sensitive, as SD outputs them)
_KNOWN_KEYS = (
    "Steps", "Sampler", "Schedule type", "CFG scale", "Distilled CFG Scale",
    "Seed", "Size", "Model hash", "Model", "VAE hash", "VAE",
    "Denoising strength", "Clip skip", "Hires upscale", "Hires upscaler",
    "Hires steps", "Hires CFG scale", "ADetailer model", "ADetailer version",
    "TI hashes", "Lora hashes", "Version",
)

# Build a regex that matches any known key followed by ": "
_KEY_PATTERN = re.compile(
    r"(?:^|,\s*)(" + "|".join(re.escape(k) for k in _KNOWN_KEYS) + r"):\s*",
)


def _parse_params_line(line: str) -> dict:
    """Extract key-value pairs from the generation parameter line."""
    params: dict[str, str] = {}
    matches = list(_KEY_PATTERN.finditer(line))
    for i, m in enumerate(matches):
        key = m.group(1)
        value_start = m.end()
        value_end = matches[i + 1].start() if i + 1 < len(matches) else len(line)
        value = line[value_start:value_end].rstrip(", ").strip()
        params[key] = value
    return params


def parse_pnginfo(text: str) -> dict | None:
    """
    Parse a Stable Diffusion PNG info string into an SD API payload dict.

    Expected format::

        <positive prompt>
        Negative prompt: <negative prompt>
        Steps: 20, Sampler: DPM++ 2M Karras, CFG scale: 7, Seed: 1234, Size: 512x768, Model: name, ...

    Returns None if the text does not look like a valid PNG info string.
    """
    text = text.strip()
    lines = text.splitlines()

    # Find the params line (contains "Steps:")
    params_line_idx = None
    for i in range(len(lines) - 1, -1, -1):
        if re.search(r"\bSteps:\s*\d+", lines[i]):
            params_line_idx = i
            break

    if params_line_idx is None:
        return None

    params_text = lines[params_line_idx]
    pre_params = "\n".join(lines[:params_line_idx]).strip()

    # Split positive / negative prompt
    neg_match = re.search(r"(?:^|\n)Negative prompt:\s*", pre_params)
    if neg_match:
        prompt = pre_params[: neg_match.start()].strip()
        negative_prompt = pre_params[neg_match.end() :].strip()
    else:
        prompt = pre_params
        negative_prompt = ""

    params = _parse_params_line(params_text)

    # Build SD API payload
    payload: dict = {"prompt": prompt, "negative_prompt": negative_prompt}

    if "Steps" in params:
        try:
            payload["steps"] = int(params["Steps"])
        except ValueError:
            payload["steps"] = 20

    if "Sampler" in params:
        sampler = params["Sampler"]
        # reForge / Forge uses "Schedule type" as a separate field
        if "Schedule type" in params:
            sampler = f"{sampler} {params['Schedule type']}"
        payload["sampler_name"] = sampler

    if "CFG scale" in params:
        try:
            payload["cfg_scale"] = float(params["CFG scale"])
        except ValueError:
            pass

    if "Seed" in params:
        try:
            seed = int(params["Seed"])
        except ValueError:
            seed = -1
        payload["seed"] = random.randint(0, 2**32 - 1) if seed == -1 else seed
    else:
        payload["seed"] = random.randint(0, 2**32 - 1)

    if "Size" in params:
        m = re.fullmatch(r"(\d+)x(\d+)", params["Size"])
        if m:
            payload["width"] = int(m.group(1))
            payload["height"] = int(m.group(2))

    if "Clip skip" in params:
        try:
            clip_skip = int(params["Clip skip"])
            payload.setdefault("override_settings", {})["CLIP_stop_at_last_layers"] = clip_skip
        except ValueError:
            pass

    # Model — prefer exact checkpoint name; fall back to model hash lookup via API
    if "Model" in params:
        payload.setdefault("override_settings", {})["sd_model_checkpoint"] = params["Model"]

    if "Denoising strength" in params:
        try:
            payload["denoising_strength"] = float(params["Denoising strength"])
        except ValueError:
            pass

    return payload
