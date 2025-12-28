import asyncio
from modules.ask_query import ask_with_graph

async def test():
    res = await ask_with_graph({"users_query": "hi", "session_id": "test", "oauthID": "test"})
    print(res)

asyncio.run(test())