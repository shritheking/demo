import asyncio
import httpx

async def test():
    async with httpx.AsyncClient() as client:
        try:
            files = {"document": ("test.txt", b"hello", "text/plain")}
            data = {"chat_id": 12345678, "caption": "Test"}
            # Dummy URL, we just want to see if httpx throws an error when constructing the request
            req = client.build_request("POST", "https://httpbin.org/post", data=data, files=files)
            print("Successfully built request!")
        except Exception as e:
            print(f"Error building request: {type(e).__name__}: {e}")

asyncio.run(test())
