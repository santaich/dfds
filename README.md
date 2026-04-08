# Stable Diffusion ↔ Discord Bot

reForgeと連携するDiscordツールセットです。

## 構成

```
dfds/
├── sd_discord_uploader/        # reForge拡張機能：生成画像を自動アップロード
│   ├── scripts/
│   │   └── discord_uploader.py
│   ├── install.py
│   └── config.json             # 自動生成
└── discord_bot/                # Discord Bot
    ├── bot.py                  # エントリポイント
    ├── requirements.txt
    ├── .env.example
    └── cogs/
        ├── admin.py            # スラッシュコマンド（管理者用）
        ├── sd_reply.py         # PNGInfo受信→画像生成→リプライ
        └── utils.py            # 設定・PNGInfoパーサー
```

---

## 機能1: reForge拡張機能（Webhook自動アップロード）

reForgeで画像を生成するたびに、指定したDiscordチャンネルへ自動投稿します。

### セットアップ

**1. Discord Webhookを作成**

1. 投稿先チャンネルの設定を開く
2. 「連携サービス」→「ウェブフック」→「新しいウェブフック」
3. WebhookのURLをコピー

**2. 拡張機能をインストール**

`sd_discord_uploader/` フォルダごと reForge の `extensions/` にコピー:

```
<reForge>/extensions/sd_discord_uploader/
```

**3. reForge再起動後の設定**

txt2imgのUIの「Discord Auto Uploader」アコーディオンを開いて:
- WebhookのURLを貼り付け → 「Save Settings」
- 「Test Webhook」で動作確認

### UI設定項目

| 設定 | 説明 |
|------|------|
| Enable Discord Upload | ON/OFF切り替え |
| Discord Webhook URL | WebhookのURL |
| Prompt | プロンプトをメッセージに含める |
| Negative Prompt | ネガティブプロンプトを含める |
| Parameters | モデル・ステップ数・Seed等を含める |
| Upload Grid | グリッド画像もアップロード |
| Mention Role ID | 投稿時にメンションするロールID |

---

## 機能2: Discord Bot（PNGInfo → 画像生成リプライ）

特定チャンネルにPNG情報文字列を貼り付けると、その設定で画像を生成してリプライします。

```
[あなた] masterpiece, 1girl...
         Negative prompt: lowres, bad anatomy
         Steps: 20, Sampler: DPM++ 2M Karras, CFG scale: 7, Seed: -1, Size: 512x768, Model: dreamshaper_8

[Bot]    → 生成した画像をリプライで返す（Seed=-1の場合はランダムに設定）
```

### セットアップ

**1. Discord Botを作成**

1. [Discord Developer Portal](https://discord.com/developers/applications) でアプリ作成
2. 「Bot」タブでトークンをコピー
3. 「OAuth2」→「URL Generator」でスコープ選択:
   - Scopes: `bot`, `applications.commands`
   - Permissions: `Send Messages`, `Read Message History`, `Embed Links`, `Attach Files`
4. 生成されたURLでBotをサーバーに招待

**2. reForge APIを有効化**

reForgeの起動時に `--api` フラグを付ける:

```
webui.bat --api
# または
python launch.py --api
```

APIが有効なら `http://127.0.0.1:7860/docs` にアクセスできます。

**3. Botを起動**

```bash
cd discord_bot
cp .env.example .env
# .env に DISCORD_BOT_TOKEN を記入

pip install -r requirements.txt
python bot.py
```

**4. チャンネルを設定（Discordのスラッシュコマンド）**

```
/setlistenchannel #pnginfo-channel   ← PNGInfoを貼るチャンネル
/setsdapi http://127.0.0.1:7860      ← reForge APIのURL（デフォルト値）
```

### スラッシュコマンド一覧（管理者のみ）

| コマンド | 説明 |
|----------|------|
| `/setlistenchannel #ch` | PNGInfo受信チャンネルを設定 |
| `/setchannel #ch` | Webhookアップロード先チャンネルを設定 |
| `/setsdapi <url>` | reForge APIのURLを設定 |
| `/sdstatus` | 現在の設定を確認 |
| `/purge [count]` | アップロードチャンネルのメッセージを削除 |

### PNGInfoの取得方法

reForgeの「PNG Info」タブに生成した画像をドラッグ＆ドロップすると情報文字列が表示されます。それをそのままDiscordにコピペするだけです。

---

## Seed の扱い

- PNGInfoの `Seed` がそのまま使用されます
- `Seed: -1` の場合はランダムなSeedが設定されます
- リプライのEmbedには実際に使用されたSeed番号が表示されます
