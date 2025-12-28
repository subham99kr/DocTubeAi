import os, asyncio, asyncpg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("POSTGRES_DB_URL")
variable = "lalkdfsfdk"
async def get_rows():
    conn = await asyncpg.connect(DATABASE_URL)
    # await conn.execute(
    # "INSERT INTO public.users (userid, oauth) VALUES ($1, $2)",
    # "test_user_id2",
    # variable
    # )

    rows = await conn.fetch("SELECT oauth FROM users Where userid = $1;","test_user_id2")
    await conn.close()
    # for r in rows:
    print(rows)
    if rows:
        print("exists")
        print(rows[0]['oauth'])
    else:
        print("not exists")

if __name__ == "__main__":
    asyncio.run(get_rows())
