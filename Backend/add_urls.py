"""Add opportunities from official pages you choose: python add_urls.py urls.txt"""
import asyncio
import sys

from app import db, extract, tinyfish


async def main(path: str):
    urls = [
        line.strip() for line in open(path, encoding="utf-8")
        if line.strip().startswith("http")
    ]
    if not urls:
        print("No URLs found. Put one https:// link per line in", path)
        return

    db.init()
    texts = {}
    try:
        fetched = await tinyfish.fetch(urls)
        for page in fetched.get("results", []):
            texts[page.get("url")] = page.get("text") or page.get("content") or ""
    except Exception as exc:
        print("Page fetch failed (continuing without page text):", exc)

    gate = asyncio.Semaphore(3)

    async def one(url):
        async with gate:
            text = texts.get(url, "")
            try:
                opp = await asyncio.to_thread(extract.extract, url, text)
                db.upsert_opportunity(opp, text)
                print("OK  ", (opp["deadline"] or "no deadline").ljust(11), "|", opp["title"][:60])
            except Exception as exc:
                print("FAIL", url, "-", exc)

    await asyncio.gather(*(one(u) for u in urls))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python add_urls.py urls.txt")
    asyncio.run(main(sys.argv[1]))
