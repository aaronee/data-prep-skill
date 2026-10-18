import json, os, random, subprocess, sys
PREP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "prep.py")
WORDS = "alpha beta gamma delta theta vega rho kappa sigma omega lambda zeta eta iota mu nu xi pi tau phi chi psi".split()


def words(n, rng):                       # unique-looking filler sentence ending in a period
    return " ".join(rng.choice(WORDS) + str(rng.randint(0, 999)) for _ in range(n)) + "."


def line(text, y, x=50, h=10, font="Times"):   # one item per word, like lit output
    out = []
    for w in text.split():
        out.append(dict(text=w, x=x, y=y, width=len(w) * 5, height=h, font_name=font))
        x += len(w) * 5 + 3
    return out


def head(text, y, h=16):
    return [dict(text=text, x=50, y=y, width=len(text) * 8, height=h, font_name="Arial-BoldMT")]


def page(n, items):
    return dict(page=n, height=800, width=600, text="x" * 100, text_items=items)


def run_prep(tmp, name, pages=None, text=None, extra=()):
    if pages is not None:
        path = os.path.join(tmp, name + ".json")
        with open(path, "w") as f:
            json.dump({"pages": pages}, f)
    else:
        path = os.path.join(tmp, name + ".md")
        with open(path, "w") as f:
            f.write(text)
    subprocess.run([sys.executable, PREP, path, "--outdir", tmp, *extra],
                   check=True, capture_output=True)
    base = os.path.join(tmp, name)

    def rd(suffix):
        with open(base + suffix) as f:
            return f.read()
    return dict(clean=rd(".clean.txt"),
                chunks=json.loads(rd(".chunks.json")),
                removed=[json.loads(l) for l in rd(".removed.jsonl").splitlines() if l],
                report=rd(".report.txt"))
