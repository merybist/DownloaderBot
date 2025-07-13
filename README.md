# Video Downloader Bot

This is a Telegram bot that allows users to download videos from YouTube, TikTok, and Instagram. Simply send a link to the bot, and it will fetch and send you the video file.

## Features

- Download videos from **YouTube**
- Download videos from **TikTok**
- Download videos from **Instagram**
- Simple and user-friendly interface

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/merybist/DownloaderBot
cd DownloaderBot
```

### 2. Configure the bot

Create a `.env` file in the root directory of the project and add your Telegram Bot API token:

```plaintext

### 3. (Optional) Run your own local Telegram Bot API server

If you want to use your own local Telegram Bot API server, follow the official guide here: [How to build and run Telegram Bot API server locally](https://tdlib.github.io/telegram-bot-api/build.html)

### 4. Install dependencies and run the bot

1. Install Python 3.10+ and [pip](https://pip.pypa.io/en/stable/).
2. Install dependencies:

    ```bash
    pip install -r requirements.txt
    ```

3. Run the bot:

    ```bash
    python main.py
    ```
```
Or using Docker:

```
docker compose up -d
```

To use your local image, update docker-compose.yml to:

```
services:
  merybot:
    build:
      context: .
      dockerfile: Dockerfile
    volumes:
      - .:/app
    container_name: merybot
    restart: always
```

## Usage

- Send a YouTube, TikTok, or Instagram video link to the bot in Telegram.
- The bot will process the link and send you the video file.

## License

This project is licensed under the MIT License. See the [LICENCE](LICENCE) file for details.
