# we just need to run this code once to setup all the tables required for checkpoints. 

import os
from dotenv import load_dotenv
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import connect
from psycopg.rows import dict_row

load_dotenv()
DB_URI = os.getenv("POSTGRES_DB_URL")

def checkpoint_setup():
    with connect(DB_URI, autocommit=True, row_factory=dict_row) as conn:
        checkpointer = PostgresSaver(conn)
        print("Creating tables...")
        checkpointer.setup()
        print("✅ Tables created successfully.")

# if __name__ == "__main__":
#     checkpoint_setup()