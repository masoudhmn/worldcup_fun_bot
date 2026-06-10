import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DATABASE_URL = "mysql+asyncmy://root:Msd1213@localhost:45278/worldcup_bot"

async def check_connection():
    engine = create_async_engine(DATABASE_URL, echo=False)

    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            print("Connection OK:", result.scalar())
    except Exception as e:
        print("Connection failed:")
        print(e)
    finally:
        await engine.dispose()

asyncio.run(check_connection())