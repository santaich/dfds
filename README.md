# Stable Diffusion → Discord Auto Uploader

reForgeで生成した画像をDiscordの特定チャンネルに自動アップロードするツールです。

## 構成

```
dfds/
├── sd_discord_uploader/   # reForge拡張機能
│   ├── scripts/
│   │   └── discord_uploader.py
│   ├── install.py
│   └── config.json        # 自動生成
└── discord_bot/           # Discord Bot（オプション）
    ├── bot.py
    ├── requirements.txt
    └── .env.example
```

---

## セットアップ方法

### 方法A: Webhook のみ（簡単・推奨）

Botなしで、Webhookだけで画像をアップロードできます。

#### 1. Discord Webhookを作成する

1. Discordでアップロード先チャンネルの設定を開く
2. 「連携サービス」→「ウェブフック」→「新しいウェブフック」
3. WebhookのURLをコピーしておく

#### 2. reForge拡張機能をインストールする

`sd_discord_uploader` フォルダごと reForge の `extensions/` ディレクトリにコピー:

```
<reForge>/extensions/sd_discord_uploader/
```

#### 3. reForgeを起動する

1. reForgeを起動（または再起動）
2. txt2img / img2imgのUIに「Discord Auto Uploader」アコーディオンが表示される
3. WebhookのURLを貼り付けて「Save Settings」
4. 「Test Webhook」で接続確認

---

### 方法B: Discord Bot（スラッシュコマンド付き）

管理コマンドが必要な場合はBotも使えます。

#### 1. Discord Botを作成する

1. [Discord Developer Portal](https://discord.com/developers/applications) でアプリ作成
2. 「Bot」タブでトークンをコピー
3. 「OAuth2」→「URL Generator」で `bot` + `applications.commands` スコープを選択
4. 権限: `Send Messages`, `Manage Messages`, `Embed Links`, `Attach Files`
5. 生成されたURLでBotをサーバーに招待

#### 2. Botを起動する

```bash
cd discord_bot
cp .env.example .env
# .envにBotトークンを記入

pip install -r requirements.txt
python bot.py
```

#### 3. スラッシュコマンド

| コマンド | 説明 |
|----------|------|
| `/setchannel #channel` | アップロードチャンネルを設定 |
| `/sdstatus` | Bot設定を確認 |
| `/purge [count]` | チャンネルのメッセージを削除 |

---

## 拡張機能の設定項目

| 設定 | 説明 |
|------|------|
| Enable Discord Upload | アップロードのON/OFF |
| Discord Webhook URL | DiscordのWebhook URL |
| Prompt | プロンプトをメッセージに含める |
| Negative Prompt | ネガティブプロンプトを含める |
| Parameters | 生成パラメータ（モデル・ステップ等）を含める |
| Upload Grid | グリッド画像もアップロードする |
| Mention Role ID | 投稿時にメンションするロールID |
