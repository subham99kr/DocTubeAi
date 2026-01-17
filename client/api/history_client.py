
import requests
from utils.config import BACKEND_URL

def load_history(session_id, token=None):
    """
    Fetches the full session state including chat history, 
    uploaded PDFs, and URL links.
    """
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    
    try:
        res = requests.get(f"{BACKEND_URL}/chats/history/{session_id}", headers=headers)
        res.raise_for_status()
        
        data = res.json()
        
        return {
            "history": data.get("history", []),
            "pdfs": data.get("pdfs_uploaded", []),
            "urls": data.get("url_links", []),
            "session_id": data.get("session_id")
        }
    except Exception as e:
        print(f"Error fetching history: {e}")
        return None
    


# {
#     "session_id": "uuid-string",
#     "history": [
#         {
#             "role": "user",
#             "content": "The user's message"
#         },
#         {
#             "role": "assistant",
#             "content": "The AI's response"
#         }
#     ],
#     "pdfs_uploaded": [
#         "filename1.pdf",
#         "filename2.pdf"
#     ],
#     "url_links": [
#         {
#             "url": "https://example.com",
#             "title": "Page Title",
#             "added_at": "timestamp" // This is your "updated_at" for links
#         },
#         {
#             "url": "https://example.com",
#             "title": "Page Title",
#             "added_at": "timestamp" // This is your "updated_at" for links
#         }
#     ]
# }