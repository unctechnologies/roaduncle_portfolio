import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ---------------------------------------------------------------------------
# Configuration & Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Strict environment variable loading for Docker injection
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")

KNOWLEDGE_BASE_DIR = os.environ.get("KNOWLEDGE_BASE_DIR", "./APP")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# ---------------------------------------------------------------------------
# Knowledge base loader
# ---------------------------------------------------------------------------
def load_system_prompt(directory: str) -> str:
    kb_path = Path("/app")
    
    soul_path = kb_path / "soul.md"
    if not soul_path.exists():
        soul_path = Path("soul.md")
        
    soul_content = soul_path.read_text(encoding="utf-8").strip() if soul_path.exists() else "You are a professional MVL assistant."

    data_path = kb_path / "mvl_data.txt"
    data_content = data_path.read_text(encoding="utf-8").strip() if data_path.exists() else ""

    return f"{soul_content}\n\nUSE THIS DATA FOR FACTS:\n{data_content}"

SYSTEM_PROMPT = load_system_prompt(KNOWLEDGE_BASE_DIR)

# ---------------------------------------------------------------------------
# Session / conversation store
# ---------------------------------------------------------------------------
sessions: dict[str, list] = {}

def get_or_create_session(session_id: str) -> list:
    if session_id not in sessions:
        sessions[session_id] = []
    return sessions[session_id]

# ---------------------------------------------------------------------------
# Interaction logging
# ---------------------------------------------------------------------------
def log_interaction(user_message: str, bot_response: str):
    try:
        timestamp = datetime.now().strftime("%-m/%-d/%Y, %-I:%M:%S %p")
        entry = f"### [{timestamp}]\n**User:** {user_message}\n**RoadUncle:** {bot_response}\n\n---\n"
        
        log_file = Path("/app/interactions.md")
        
        if not log_file.exists():
            log_file.write_text("# Chatbot Interactions Log\n\n" + entry, encoding="utf-8")
        else:
            with log_file.open("a", encoding="utf-8") as f:
                f.write(entry)
    except Exception as e:
        logger.error(f"Failed to log interaction: {e}")

# ---------------------------------------------------------------------------
# Telegram Event Handlers
# ---------------------------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = "Hello! I am your RoadUncle assistant. Ask me anything, or use /reset to clear our conversation history."
    await update.message.reply_text(welcome_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    if not user_message or not user_message.strip():
        return

    session_id = str(update.effective_chat.id)
    history = get_or_create_session(session_id)

    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=SYSTEM_PROMPT,
    )
    chat_session = model.start_chat(history=history)

    await context.bot.send_chat_action(chat_id=session_id, action="typing")

    try:
        response = await chat_session.send_message_async(user_message)
        reply_text = response.text
        
        log_interaction(user_message, reply_text)
        sessions[session_id] = chat_session.history
        
        await update.message.reply_text(reply_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        await update.message.reply_text("Sorry, I encountered an internal error processing your request.")

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session_id = str(update.effective_chat.id)
    if session_id in sessions:
        del sessions[session_id]
        await update.message.reply_text("Session cleared successfully.")
    else:
        await update.message.reply_text("You have no active session to clear.")

async def list_sessions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    active_ids = list(sessions.keys())
    if not active_ids:
        await update.message.reply_text("No active sessions currently on this host.")
    else:
        await update.message.reply_text(f"Active sessions: {', '.join(active_ids)}")

# ---------------------------------------------------------------------------
# Application Entry Point
# ---------------------------------------------------------------------------
def main():
    # Enforce token validation before starting up the bot
    if not TELEGRAM_BOT_TOKEN:
        logger.critical("Missing TELEGRAM_BOT_TOKEN environment variable!")
        return
    if not GEMINI_API_KEY:
        logger.critical("Missing GOOGLE_API_KEY environment variable!")
        return

    # Configure Gemini API
    genai.configure(api_key=GEMINI_API_KEY)

    # Build the Telegram Bot
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(CommandHandler("sessions", list_sessions_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("RoadUncle Bot is polling inside container...")
    application.run_polling()

if __name__ == "__main__":
    main()
