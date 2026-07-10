# RoadUncle - Telegram RAG Chatbot

An production-ready Telegram Bot integrated with the Google Gemini API, capable of retrieval-augmented generation (RAG) using local system documents.

## Features
- **Context Preservation:** Uses unique Telegram Chat IDs to maintain independent conversation histories.
- **Auditable Logging:** Automatically appends conversation history to a markdown file for external tool auditing.
- **Containerized Implementation:** Security-hardened non-root user setup within a minimal Docker container.

## Getting Started

1. Clone the repository.
2. Place your system prompts in `soul.md` and facts in `mvl_data.txt`.
3. Create an empty log file on your host machine:
   ```bash
   touch interactions.md

### Deployment with Docker
**Build the image:**

Bash
docker build -t roaduncle-bot .

**Run the container securely using bind-mounts for persistent logging:**

Bash
docker run -d \
  --name roaduncle_live \
  -e TELEGRAM_BOT_TOKEN="your_telegram_token" \
  -e GOOGLE_API_KEY="your_gemini_key" \
  -v ./interactions.md:/app/interactions.md:rw \
  --restart unless-stopped \
  roaduncle-bot
