import pathlib

def read(p): return pathlib.Path(p).read_text(encoding="utf-8").replace("\r\n", "\n")
def write(p, t): pathlib.Path(p).write_text(t, encoding="utf-8", newline="\n")

s = read("Backend/app/main.py")

assert "import time\n" in s, "run the live-search patch first"
s = s.replace("import time\nfrom contextlib", "import time\nfrom datetime import date\nfrom contextlib", 1)

old = '''        if any(host == h or host.endswith("." + h) for h in skip_hosts):
            continue
'''
new = '''        if any(host == h or host.endswith("." + h) for h in skip_hosts):
            continue

        # Skip job boards and company career portals (full-time jobs, not student programmes).
        if host.startswith(("careers.", "jobs.")) or any(
            word in host for word in ("glassdoor.", "indeed.", "greenhouse.io", "lever.co", "workday")
        ):
            continue
'''
assert old in s, "skip_hosts block not found"
s = s.replace(old, new)

old = '''    return queries[:6]
'''
new = '''    queries.append("summer research internship 2027 applications open IIT IISc IISER undergraduate")
    queries.append("fellowship for Indian undergraduate students 2027 apply deadline")
    return queries[:7]
'''
assert old in s, "build_queries return not found"
s = s.replace(old, new, 1)

old = "ranked = await asyncio.to_thread(matcher.rank, profile_text, rows, 12)"
assert old in s, "rank call not found"
s = s.replace(old, "ranked = await asyncio.to_thread(matcher.rank, profile_text, rows, 30)")

old = '''        url = opportunity.get("url") or ""
        organization = urlparse(url).netloc.replace("www.", "")
'''
new = '''        url = opportunity.get("url") or ""
        organization = urlparse(url).netloc.replace("www.", "")

        due = opportunity.get("deadline")
        title_text = opportunity.get("title") or ""
        if due and due < date.today().isoformat():
            continue  # deadline already passed
        if not due and any(year in title_text for year in ("2024", "2025", "2026")):
            continue  # old edition with no future deadline
'''
assert old in s, "output loop block not found"
s = s.replace(old, new)

assert s.rstrip().endswith("return output"), "unexpected end of file"
s = s.rstrip()[: -len("return output")] + "return output[:12]\n"
write("Backend/app/main.py", s)
print("quality patch applied")
