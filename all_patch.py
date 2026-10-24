import pathlib

def read(p): return pathlib.Path(p).read_text(encoding="utf-8").replace("\r\n", "\n")
def write(p, t): pathlib.Path(p).write_text(t, encoding="utf-8", newline="\n")

def step(s, name, marker, old, new, count=1):
    if marker in s:
        print("skip (already applied):", name)
        return s
    assert old in s, "NOT FOUND: " + name
    print("applied:", name)
    return s.replace(old, new, count)

s = read("Backend/app/main.py")

s = step(s, "imports", "import time\n", "import re\nfrom contextlib",
         "import re\nimport time\nfrom datetime import date\nfrom contextlib")

s = step(s, "multi-query discovery", "def build_queries",
'''async def run_discovery(query: str) -> dict:
    search_results = (await tinyfish.search(query))[:5]
''',
'''def build_queries(chosen: list[str]) -> list[str]:
    """One broad query plus topic-specific queries for each chosen interest."""
    queries = [DEFAULT_QUERY]
    for key in chosen:
        topic = INTEREST_WORDS[key][0]
        queries.append(f"{topic} research internship 2027 undergraduate students India")
        queries.append(f"{topic} scholarship fellowship 2027 students India")
    queries.append("summer research internship 2027 applications open IIT IISc IISER undergraduate")
    queries.append("fellowship for Indian undergraduate students 2027 apply deadline")
    return queries[:7]


async def run_discovery(query, per_query: int = 5) -> dict:
    queries = [query] if isinstance(query, str) else list(query)
    batches = await asyncio.gather(
        *(tinyfish.search(q) for q in queries), return_exceptions=True
    )

    search_results = []
    errors = []
    for q, batch in zip(queries, batches):
        if isinstance(batch, Exception):
            logger.warning("TinyFish search failed for %r: %s", q, batch)
            errors.append(batch)
            continue
        search_results.extend(batch[:per_query])

    if errors and not search_results:
        raise errors[0]
''')

s = step(s, "refresh uses interest queries", "recently_searched",
'''    rows = db.all_opportunities()

    if refresh or not rows:
        try:
            result = await run_discovery(DEFAULT_QUERY)
''',
'''    rows = db.all_opportunities()

    chosen = [
        key for key in interests.split(",")
        if key in INTEREST_WORDS
    ]

    recently_searched = (time.time() - STATE.get("last_discovery", 0)) < 600

    if (refresh and not recently_searched) or not rows:
        try:
            STATE["last_discovery"] = time.time()
            result = await run_discovery(build_queries(chosen))
''')

s = step(s, "skip job boards", "greenhouse.io",
'''        if any(host == h or host.endswith("." + h) for h in skip_hosts):
            continue
''',
'''        if any(host == h or host.endswith("." + h) for h in skip_hosts):
            continue

        # Skip job boards and company career portals (full-time jobs, not student programmes).
        if host.startswith(("careers.", "jobs.")) or any(
            word in host for word in ("glassdoor.", "indeed.", "greenhouse.io", "lever.co", "workday")
        ):
            continue
''')

s = step(s, "rank 30", "rows, 30)",
         "matcher.rank, profile_text, rows, 12)", "matcher.rank, profile_text, rows, 30)")

s = step(s, "drop expired / old editions", "deadline already passed",
'''        url = opportunity.get("url") or ""
        organization = urlparse(url).netloc.replace("www.", "")
''',
'''        url = opportunity.get("url") or ""
        organization = urlparse(url).netloc.replace("www.", "")

        due = opportunity.get("deadline")
        title_text = opportunity.get("title") or ""
        if due and due < date.today().isoformat():
            continue  # deadline already passed
        if not due and any(year in title_text for year in ("2024", "2025", "2026")):
            continue  # old edition with no future deadline
''')

if "return output[:12]" not in s:
    assert s.rstrip().endswith("return output"), "NOT FOUND: end of file"
    s = s.rstrip()[: -len("return output")] + "return output[:12]\n"
    print("applied: cap output at 12")
write("Backend/app/main.py", s)

j = read("Frontend/script.js")
if "refresh=true" not in j:
    old = '"/api/opportunities?interests=" +'
    assert old in j, "NOT FOUND: frontend endpoint"
    j = j.replace(old, '"/api/opportunities?refresh=true&interests=" +')
    print("applied: frontend refresh=true")
j = j.replace('setStatus("Searching for opportunities...");',
              'setStatus("Searching the live web with TinyFish (30-90 seconds)...");', 1)
write("Frontend/script.js", j)
print("DONE")
