import os
import json
import logging
from datetime import datetime
from pathlib import Path

import google.generativeai as genai
import numpy as np
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ---------------------------------------------------------------------------
# Configuration & Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
EMBEDDING_MODEL = "models/gemini-embedding-001" 

# ---------------------------------------------------------------------------
# Knowledge Base & Embeddings Global Store
# ---------------------------------------------------------------------------
KNOWLEDGE_BASE = []
DATABASE_VECTORS = []
SOUL_INSTRUCTION = ""

def init_knowledge_base():
    """Loads the core personality and pre-computes semantic weights cleanly."""
    global KNOWLEDGE_BASE, DATABASE_VECTORS, SOUL_INSTRUCTION
    kb_path = Path("/app")
    
    # 1. Load Persona / Soul
    soul_path = kb_path / "soul.md"
    if not soul_path.exists():
        soul_path = Path("soul.md")
    SOUL_INSTRUCTION = soul_path.read_text(encoding="utf-8").strip() if soul_path.exists() else "You are RoadUncle, a professional South African MVL assistant."

    # 2. Load JSON Rules Dataset
    json_path = kb_path / "mvl_data.json"
    if not json_path.exists():
        json_path = Path("mvl_data.json")
        
    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                KNOWLEDGE_BASE = json.load(f)
            
            logger.info("Generating semantic database embeddings... (Happens once on startup)")
            DATABASE_VECTORS = []  
            
            for item in KNOWLEDGE_BASE:
                category = item.get('category', '')
                sub_category = item.get('sub_category', '')
                function_text = item.get('function', '')
                kw_list = " ".join(item.get('keywords', [])) 
                
                # Structural text generation
                searchable_text = f"Category: {category} | Sub-Category: {sub_category} | Action: {function_text} | Keywords: {kw_list}"
                
                # FIXED: Changed 'contents' to 'content' and removed the erroneous [0] slice
                result = genai.embed_content(model=EMBEDDING_MODEL, content=searchable_text, task_type="RETRIEVAL_QUERY")
                DATABASE_VECTORS.append(result['embedding'])
                
            logger.info(f"SUCCESS: Successfully indexed {len(DATABASE_VECTORS)} entries into vector space.")
            
        except Exception as e:
            logger.critical(f"CRITICAL FAULT: Failed to compile knowledge base: {e}")
    else:
        logger.warning("mvl_data.json file not found. Vector lookups will fail.")

def get_best_matches(user_message: str, threshold: float = 0.38) -> list[dict]:
    """Calculates cosine similarity and logs a detailed leaderboard for debugging."""
    if not DATABASE_VECTORS:
        return None, 0.0
        
    try:
        # FIXED: Changed 'contents' to 'content' and removed [0] slice
        res = genai.embed_content(model=EMBEDDING_MODEL, content=user_message, task_type="RETRIEVAL_QUERY")
        user_vector = np.array(res['embedding'])
        
        scored_items = []
        for idx, db_vector in enumerate(DATABASE_VECTORS):
            db_vec = np.array(db_vector)
            dot_product = np.dot(user_vector, db_vec)
            norm_user = np.linalg.norm(user_vector)
            norm_db = np.linalg.norm(db_vec)
            
            similarity = dot_product / (norm_user * norm_db) if (norm_user > 0 and norm_db > 0) else 0.0
            scored_items.append((similarity, KNOWLEDGE_BASE[idx]))
            
        # Sort items by highest similarity score
        scored_items.sort(key=lambda x: x[0], reverse=True)
        
        # PRINT DEBUG LEADERBOARD LIVE TO CONTAINER TERMINAL
        print("\n" + "="*60, flush=True)
        print(f"DEBUG VECTOR MATCHING FOR: '{user_message}'", flush=True)
        print("="*60, flush=True)
        for rank, (score, item) in enumerate(scored_items[:3]):
            print(f"Rank {rank+1} [Score: {score:.4f}]", flush=True)
            print(f"   Category:     {item.get('category')}", flush=True)
            print(f"   Sub-Category: {item.get('sub_category')}", flush=True)
            print(f"   Function:     {item.get('function')}\n", flush=True)
        print("="*60 + "\n", flush=True)
        
        return [item for score, item in scored_items[:2] if score >= threshold] 
    except Exception as e:
        logger.error(f"Embedding lookup failed: {e}")
        return None, 0.0

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
        timestamp = datetime.now().strftime("%Y-%m-%d, %I:%M:%S %p")
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
    welcome_text = "Hello! I am your RoadUncle assistant. Ask me anything, or use /reset to clear history."
    await update.message.reply_text(welcome_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    if not user_message or not user_message.strip():
        return

    session_id = str(update.effective_chat.id)
    history = get_or_create_session(session_id)

    await context.bot.send_chat_action(chat_id=session_id, action="typing")

    try:
        matched_contexts = get_best_matches(user_message, threshold=0.38)
    
        # DEV LOG: Verify your array is actually pulling multiple records
        logger.info(f"DEBUG: Passing {len(matched_contexts)} database rows directly to Gemini context window.")

        if matched_contexts:
        # 2. Format each match as an explicit, distinct Option
            import json
            compiled_context = ""
            for idx, ctx in enumerate(matched_contexts, 1):
                compiled_context += f"\n[POSSIBLE DATABASE MATCH {idx}]\n"
                compiled_context += json.dumps(ctx, indent=2, ensure_ascii=False)
                compiled_context += "\n"
        
        # 3. Give Gemini explicit sorting and triage instructions
            dynamic_instruction = f"""{SOUL_INSTRUCTION}
        
            POTENTIAL OFFICIAL DOCUMENTATION MATCHES:
            {compiled_context}
        
            INSTRUCTION TO THE AI ASSISTANT:
            The user said: "{user_message}"
        
            You have been provided with up to 3 potential database matches above. Review them all before answering.
        
            - If the user's intent matches a specific option perfectly, use that option to answer.
            - If the user's query is broad or ambiguous (e.g., "get a new license disc" could mean replacing a lost one OR an annual renewal), do not just guess Match 1. Instead, distinguish between them cleanly in your reply. 
        
            Keep your tone helpful, professional, and well-structured for Telegram.
            """

        else:
            dynamic_instruction = f"""{SOUL_INSTRUCTION}
        
            INSTRUCTION: The user is asking a question that lies outside our strict documentation records. Inform them politely that you focus exclusively on vehicle registration processes, licensing disc renewals, and professional driving permits (PrDP), and prompt them to expand or modify their wording.
            """

        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=dynamic_instruction,
        )
        
        chat_session = model.start_chat(history=history)
        response = await chat_session.send_message_async(user_message)
        reply_text = response.text
        
        log_interaction(user_message, reply_text)
        sessions[session_id] = chat_session.history[-10:]
        try:
            await update.message.reply_text(reply_text, parse_mode="Markdown")
        except Exception as parse_error:
            logger.warning(f"Telegram formatting failed ({parse_error}). Sending as plain text.")
            await update.message.reply_text(reply_text) # Sends successfully without formatting rules
        
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
    if not TELEGRAM_BOT_TOKEN:
        logger.critical("Missing TELEGRAM_BOT_TOKEN environment variable!")
        return
    if not GEMINI_API_KEY:
        logger.critical("Missing GOOGLE_API_KEY environment variable!")
        return

    genai.configure(api_key=GEMINI_API_KEY)
    init_knowledge_base()

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(CommandHandler("sessions", list_sessions_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("RoadUncle Bot is polling inside container with Vector-RAG optimization...", flush=True)
    application.run_polling()

if __name__ == "__main__":
    main()
