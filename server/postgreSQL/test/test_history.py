import asyncio
import os
import selectors
import json # For clean printing at the end
from dotenv import load_dotenv
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

load_dotenv()
DB_URL = os.getenv("POSTGRES_DB_URL") 

async def run_test():
    # This will be our storage object
    chat_history_obj = []

    async with AsyncConnectionPool(conninfo=DB_URL, open=False) as pool:
        await pool.open()
        saver = AsyncPostgresSaver(pool)
        
        session_id = "1234567" 
        config = {"configurable": {"thread_id": session_id}}

        try:
            checkpoint_tuple = await saver.aget_tuple(config)

            if not checkpoint_tuple:
                print("❌ No history found.")
                return

            # Get raw messages from the binary checkpoint
            messages = checkpoint_tuple.checkpoint.get("channel_values", {}).get("messages", [])
            
            # --- POPULATING THE OBJECT ---
            for msg in messages:
                # Filter for non-empty Human and AI messages only
                if msg.type in ['human', 'ai'] and msg.content.strip():
                    chat_history_obj.append({
                        "role": "user" if msg.type == "human" else "assistant",
                        "content": msg.content.strip()
                    })

        except Exception as e:
            print(f"🔴 Error: {e}")
            return

    # --- FINAL STEP: WORK WITH THE OBJECT ---
    print(f"✅ Successfully stored {len(chat_history_obj)} messages in 'chat_history_obj'\n")
    
    # Printing the actual variable so you can see the structure
    print("--- RAW OBJECT OUTPUT ---")
    print(json.dumps(chat_history_obj, indent=4))
    
    return chat_history_obj

if __name__ == "__main__":
    if not DB_URL:
        print("❌ POSTGRES_DB_URL not found in .env file")
    else:
        asyncio.run(
            run_test(), 
            loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector())
        )