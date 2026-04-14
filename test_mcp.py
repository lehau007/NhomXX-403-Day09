import asyncio
import json
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def run():
    try:
        async with sse_client('http://127.0.0.1:8081/sse') as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                res = await session.call_tool('check_access_permission', {'access_level': 3, 'requester_role': 'engineer'})
                print(json.dumps(json.loads(res.content[0].text), indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(run())
