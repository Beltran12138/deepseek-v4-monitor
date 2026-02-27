# DeepSeek-V4 Release Monitor

A comprehensive monitoring tool for DeepSeek-V4 release signals across multiple platforms.

## Features
- **PolyMarket**: Real-time tracking of release date market prices and volume.
- **Hugging Face**: Monitoring `deepseek-ai` models and datasets for new or updated repositories.
- **GitHub**: Tracking infrastructure repos (DeepGEMM, FlashMLA, EPLB, etc.) for new branches or commits.
- **Twitter (X)**: Monitoring official and key community accounts via RSSHub.
- **Reddit**: Searching `r/LocalLLaMA` for the latest discussions and leaks.
- **Notifications**: Instant alerts via Windows desktop popups and Telegram Bot.

## Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Beltran12138/deepseek-v4-monitor.git
   cd deepseek-v4-monitor
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**:
   - Copy `.env.example` to `.env`.
   - Fill in your `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
   - (Optional) Add a `GITHUB_TOKEN` to avoid API rate limiting.

4. **Run the monitor**:
   ```bash
   python monitor.py
   ```

## Configuration
All configurations are managed via the `.env` file. You can adjust the check interval and price alert thresholds there.

## License
MIT
