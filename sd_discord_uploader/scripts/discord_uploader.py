"""
Stable Diffusion reForge Extension: Discord Auto Uploader
Automatically uploads generated images to a Discord channel via webhook.
"""

import gradio as gr
import modules.scripts as scripts
import requests
import json
import io
from datetime import datetime
from pathlib import Path

CONFIG_FILE = Path(__file__).parent.parent / "config.json"


def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "webhook_url": "",
        "enabled": False,
        "include_prompt": True,
        "include_negative_prompt": False,
        "include_params": True,
        "mention_role_id": "",
        "upload_grid": False,
    }


def save_config(config: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def build_embed(p, processed, seed: int) -> dict:
    config = load_config()
    fields = []

    if config.get("include_prompt") and getattr(p, "prompt", ""):
        prompt_text = p.prompt[:1024]
        fields.append({"name": "Prompt", "value": f"```{prompt_text}```", "inline": False})

    if config.get("include_negative_prompt") and getattr(p, "negative_prompt", ""):
        neg_text = p.negative_prompt[:1024]
        fields.append({"name": "Negative Prompt", "value": f"```{neg_text}```", "inline": False})

    if config.get("include_params"):
        model_name = getattr(p, "sd_model_name", None) or "unknown"
        sampler = getattr(p, "sampler_name", "unknown")
        params = (
            f"Model: `{model_name}`\n"
            f"Steps: `{getattr(p, 'steps', '?')}` | CFG: `{getattr(p, 'cfg_scale', '?')}` | Sampler: `{sampler}`\n"
            f"Size: `{getattr(p, 'width', '?')}x{getattr(p, 'height', '?')}` | Seed: `{seed}`"
        )
        fields.append({"name": "Parameters", "value": params, "inline": False})

    return {
        "title": "New Image Generated",
        "color": 0x5865F2,
        "fields": fields,
        "footer": {"text": f"Stable Diffusion reForge • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"},
    }


def upload_image(webhook_url: str, image, filename: str, embed: dict, mention_role_id: str = ""):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)

    content = f"<@&{mention_role_id}>" if mention_role_id else ""
    payload = {"embeds": [embed]}
    if content:
        payload["content"] = content

    files = {
        "file": (filename, buffer, "image/png"),
        "payload_json": (None, json.dumps(payload)),
    }

    response = requests.post(webhook_url, files=files, timeout=30)
    response.raise_for_status()
    return response.status_code


class DiscordUploaderScript(scripts.Script):
    def title(self):
        return "Discord Auto Uploader"

    def show(self, is_img2img):
        return scripts.AlwaysVisible

    def ui(self, is_img2img):
        config = load_config()

        with gr.Accordion("Discord Auto Uploader", open=False):
            enabled = gr.Checkbox(label="Enable Discord Upload", value=config.get("enabled", False))
            webhook_url = gr.Textbox(
                label="Discord Webhook URL",
                placeholder="https://discord.com/api/webhooks/xxxxx/yyyyy",
                value=config.get("webhook_url", ""),
                type="password",
            )
            with gr.Row():
                include_prompt = gr.Checkbox(label="Prompt", value=config.get("include_prompt", True))
                include_negative = gr.Checkbox(label="Negative Prompt", value=config.get("include_negative_prompt", False))
                include_params = gr.Checkbox(label="Parameters", value=config.get("include_params", True))
                upload_grid = gr.Checkbox(label="Upload Grid", value=config.get("upload_grid", False))
            mention_role_id = gr.Textbox(
                label="Mention Role ID (optional)",
                placeholder="Discord Role ID to mention",
                value=config.get("mention_role_id", ""),
            )
            with gr.Row():
                save_btn = gr.Button("Save Settings", variant="primary")
                test_btn = gr.Button("Test Webhook")
            status_text = gr.Textbox(label="Status", interactive=False)

            def save_settings(en, url, inc_p, inc_n, inc_params, grid, role_id):
                cfg = {
                    "enabled": en,
                    "webhook_url": url,
                    "include_prompt": inc_p,
                    "include_negative_prompt": inc_n,
                    "include_params": inc_params,
                    "upload_grid": grid,
                    "mention_role_id": role_id,
                }
                save_config(cfg)
                return "Settings saved!"

            def test_webhook(url):
                if not url:
                    return "Error: Webhook URL is empty."
                try:
                    payload = {
                        "embeds": [{
                            "title": "Webhook Test",
                            "description": "Discord Auto Uploader is connected!",
                            "color": 0x57F287,
                        }]
                    }
                    r = requests.post(url, json=payload, timeout=10)
                    r.raise_for_status()
                    return f"Test successful! (HTTP {r.status_code})"
                except Exception as e:
                    return f"Test failed: {e}"

            save_btn.click(
                fn=save_settings,
                inputs=[enabled, webhook_url, include_prompt, include_negative, include_params, upload_grid, mention_role_id],
                outputs=[status_text],
            )
            test_btn.click(fn=test_webhook, inputs=[webhook_url], outputs=[status_text])

        return [enabled, webhook_url, include_prompt, include_negative, include_params, upload_grid, mention_role_id]

    def postprocess(self, p, processed, enabled, webhook_url, include_prompt, include_negative, include_params, upload_grid, mention_role_id):
        if not enabled or not webhook_url:
            return

        # Save current UI settings
        save_config({
            "enabled": enabled,
            "webhook_url": webhook_url,
            "include_prompt": include_prompt,
            "include_negative_prompt": include_negative,
            "include_params": include_params,
            "upload_grid": upload_grid,
            "mention_role_id": mention_role_id,
        })

        first_img_index = getattr(processed, "index_of_first_image", 0)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for i, image in enumerate(processed.images):
            # Skip grid image unless requested
            is_grid = i < first_img_index
            if is_grid and not upload_grid:
                continue

            if is_grid:
                seed = getattr(processed, "seed", 0)
                filename = f"sd_grid_{timestamp}.png"
            else:
                img_index = i - first_img_index
                seeds = getattr(processed, "all_seeds", [getattr(processed, "seed", 0)])
                seed = seeds[img_index] if img_index < len(seeds) else getattr(processed, "seed", 0)
                filename = f"sd_{timestamp}_{img_index}.png"

            embed = build_embed(p, processed, seed)

            try:
                status = upload_image(webhook_url, image, filename, embed, mention_role_id)
                print(f"[Discord Uploader] Uploaded {filename} (HTTP {status})")
            except Exception as e:
                print(f"[Discord Uploader] Failed to upload {filename}: {e}")
