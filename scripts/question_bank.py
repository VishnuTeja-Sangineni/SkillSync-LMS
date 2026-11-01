"""
Question generators for the synthetic course content.

Every generator returns (text, options, correct_index) and COMPUTES its own
correct answer (code questions are really executed), so the answer key is
always right. Generators are deterministic for a given random.Random instance.

Each topic has one generator that takes (rng, difficulty) where difficulty is
"easy", "medium" or "hard".
"""

import random
from collections import Counter
from fractions import Fraction
from statistics import median

DIFFICULTIES = ("easy", "medium", "hard")

# ── helpers ───────────────────────────────────────────────────────────

_SAFE_BUILTINS = {
    "range": range, "len": len, "sum": sum, "int": int, "float": float, "str": str,
    "list": list, "min": min, "max": max, "sorted": sorted, "abs": abs,
    "round": round, "enumerate": enumerate, "zip": zip,
}


def _run(code: str):
    """Execute generated code (never user input) and return its `result` variable."""
    g = {"__builtins__": _SAFE_BUILTINS}
    exec(code, g)
    return g["result"]


def _finish(rng, correct: str, distractors, n_wrong: int = 3):
    """Dedupe distractors, keep 3, shuffle, and return (options, correct_index)."""
    pool = []
    for d in distractors:
        d = str(d)
        if d != correct and d not in pool:
            pool.append(d)
    if len(pool) < n_wrong:
        raise ValueError(f"Not enough distinct distractors for {correct!r}: {pool}")
    options = [correct] + pool[:n_wrong]
    rng.shuffle(options)
    return options, options.index(correct)


def _num(rng, correct, distractors, fmt="{}", step=1):
    """Numeric options: pad with nearby values if there are too few distractors."""
    shown = {fmt.format(correct)}
    pool = []
    for d in list(distractors):
        s = fmt.format(d)
        if s not in shown:
            shown.add(s)
            pool.append(s)
    k = 1
    while len(pool) < 3 and k < 50:
        for cand in (correct + k * step, correct - k * step):
            s = fmt.format(cand)
            if s not in shown and len(pool) < 3:
                shown.add(s)
                pool.append(s)
        k += 1
    return _finish(rng, fmt.format(correct), pool)


def _code_q(prompt: str, code: str) -> str:
    return f"{prompt}\n\n```python\n{code}\n```"


def _xp(n: int) -> str:
    return "x" if n == 1 else f"x^{n}"


def _signed(n: int, first=False) -> str:
    """Format +n / -n for building expressions like 'x + 3' or 'x - 3'."""
    return f"{n}" if first and n >= 0 else (f"+ {n}" if n >= 0 else f"- {abs(n)}")


WORDS = ["python", "garden", "planet", "bridge", "castle", "window", "market",
         "silver", "forest", "rocket", "pencil", "orange", "yellow", "winter"]

# ── ALGEBRA ───────────────────────────────────────────────────────────

def linear_equations(rng, diff):
    x = rng.randint(1, 9)
    if diff == "easy":
        a, b = rng.randint(2, 5), rng.randint(1, 9)
        c = a * x + b
        text, wrong = f"Solve for x: {a}x + {b} = {c}", [x + 1, x - 1, c - b, x + 2]
    elif diff == "medium":
        a, b = rng.randint(2, 9), rng.randint(1, 15)
        c = a * x - b
        text, wrong = f"Solve for x: {a}x - {b} = {c}", [x - 1, x + 1, c - b, c + b]
    else:
        a = rng.randint(3, 9)
        c2, b = rng.randint(1, a - 1), rng.randint(1, 12)
        d = (a - c2) * x + b
        text, wrong = f"Solve for x: {a}x + {b} = {c2}x + {d}", [x + 1, x - 1, -x, d - b]
    o, i = _num(rng, x, wrong, "x = {}")
    return text, o, i


def exponents(rng, diff):
    if diff == "easy":
        b, n = rng.randint(2, 5), rng.randint(2, 4)
        o, i = _num(rng, b ** n, [b * n, b ** (n - 1), b ** (n + 1), n ** b])
        return f"What is {b}^{n}?", o, i
    if diff == "medium":
        a, b = rng.sample(range(2, 8), 2)
        o, i = _finish(rng, _xp(a + b), [_xp(a * b), _xp(abs(a - b)), _xp(a + b + 1), _xp(a * b + 1)])
        return f"Simplify: x^{a} · x^{b}", o, i
    a, b = rng.randint(2, 4), rng.randint(2, 4)
    c = rng.randint(1, a * b - 1)
    ans = a * b - c
    wrong = [_xp(a * b + c), _xp(a * b), _xp(a * b * c), _xp(ans + 1), _xp(ans + 2), _xp(ans * 2), _xp(ans + 3)]
    if a + b - c >= 1:
        wrong.insert(0, _xp(a + b - c))
    o, i = _finish(rng, _xp(ans), wrong)
    return f"Simplify: (x^{a})^{b} ÷ x^{c}", o, i


def factoring(rng, diff):
    if diff == "easy":
        p, q = rng.sample(range(1, 7), 2)
        correct = f"(x + {p})(x + {q})"
        wrong = [f"(x + {p})(x - {q})", f"(x - {p})(x - {q})", f"(x - {p})(x + {q})", f"(x + {p * q})(x + 1)"]
        return f"Factor: x^2 + {p + q}x + {p * q}", *_finish(rng, correct, wrong)
    if diff == "medium":
        k = rng.randint(2, 9)
        correct = f"(x - {k})(x + {k})"
        wrong = [f"(x - {k})^2", f"(x + {k})^2", f"(x - {k * k})(x + 1)", f"(x - {k})(x - {k + 1})"]
        return f"Factor: x^2 - {k * k}", *_finish(rng, correct, wrong)
    while True:
        p, q = rng.randint(-8, 8), rng.randint(-8, 8)
        if p != 0 and q != 0 and p != q and p != -q:
            break
    s, pr = p + q, p * q
    poly = f"x^2 {'-' if s > 0 else '+'} {abs(s)}x {'+' if pr >= 0 else '-'} {abs(pr)} = 0"

    def roots(u, v):
        a, b = sorted((u, v))
        return f"x = {a} and x = {b}"

    wrong = [roots(-p, -q), roots(p, -q), roots(-p, q)]
    return f"Find the roots of: {poly}", *_finish(rng, roots(p, q), wrong)


def inequalities(rng, diff):
    if diff == "easy":
        b, k = rng.randint(2, 9), rng.randint(1, 10)
        c = k + b
        wrong = [f"x < {k}", f"x > {c + b}", f"x < {c + b}", f"x > {c}"]
        return f"Solve: x + {b} > {c}", *_finish(rng, f"x > {k}", wrong)
    if diff == "medium":
        a, k = rng.randint(2, 6), rng.randint(2, 9)
        c = a * k
        wrong = [f"x ≥ {k}", f"x ≤ {c}", f"x ≥ {c}", f"x < {k}"]
        return f"Solve: {a}x ≤ {c}", *_finish(rng, f"x ≤ {k}", wrong)
    a, b, k = rng.randint(2, 5), rng.randint(1, 10), rng.randint(1, 8)
    c = -a * k + b
    wrong = [f"x < {k}", f"x > -{k}", f"x < -{k}"]
    return f"Solve: -{a}x + {b} < {c}", *_finish(rng, f"x > {k}", wrong)


def functions(rng, diff):
    if diff == "easy":
        a, b, k = rng.randint(2, 6), rng.randint(-5, 9), rng.randint(2, 7)
        if b == 0:
            b = 3
        ans = a * k + b
        fx = f"{a}x {'+' if b > 0 else '-'} {abs(b)}"
        o, i = _num(rng, ans, [a * k - b, a * (k + b), a + k + b, k + b])
        return f"If f(x) = {fx}, what is f({k})?", o, i
    if diff == "medium":
        b, c, k = rng.randint(1, 5), rng.randint(-6, 6), rng.choice([-3, -2, 2, 3, 4])
        ans = k * k + b * k + c
        fx = f"x^2 + {b}x {'+' if c >= 0 else '-'} {abs(c)}"
        o, i = _num(rng, ans, [k * k - b * k + c, (k + b) ** 2 + c, k + b + c, 2 * k + b * k + c])
        return f"If f(x) = {fx}, what is f({k})?", o, i
    a, b, c, k = rng.randint(2, 4), rng.randint(1, 6), rng.randint(1, 5), rng.randint(2, 4)
    ans = a * (k * k + c) + b
    o, i = _num(rng, ans, [(a * k + b) ** 2 + c, (a * k + b) * (k * k + c), a * k * k + c + b])
    return f"If f(x) = {a}x + {b} and g(x) = x^2 + {c}, what is f(g({k}))?", o, i

# ── PYTHON ────────────────────────────────────────────────────────────

def py_variables(rng, diff):
    if diff == "easy":
        literals = [
            (str(rng.randint(1, 99)), "int"), (str(round(rng.uniform(1, 9), 2)), "float"),
            (f'"{rng.choice(WORDS)}"', "str"), (rng.choice(["True", "False"]), "bool"),
            (f"[{rng.randint(1, 9)}, {rng.randint(1, 9)}]", "list"),
            (f"({rng.randint(1, 9)}, {rng.randint(1, 9)})", "tuple"),
            (f'{{"k": {rng.randint(1, 9)}}}', "dict"),
        ]
        lit, tname = rng.choice(literals)
        wrong = [t for _, t in literals if t != tname]
        o, i = _finish(rng, tname, wrong)
        return f"What is the type of the value `{lit}` in Python?", o, i
    if diff == "medium":
        a, b = rng.randint(10, 60), rng.randint(3, 9)
        op = rng.choice(["//", "%", "**"])
        if op == "**":
            b = rng.randint(2, 4)
            a = rng.randint(2, 6)
        code = f"a = {a}\nb = {b}\nresult = a {op} b"
        ans = _run(code)
        o, i = _num(rng, ans, [ans + 1, ans - 1, a * b, a - b])
        return _code_q("What is the value of `result`?", code), o, i
    a, b, c = rng.randint(20, 90), rng.randint(3, 9), rng.randint(2, 5)
    code = f"x = {a}\ny = {b}\nresult = x // y + x % y * {c}"
    ans = _run(code)
    o, i = _num(rng, ans, [x - 1 for x in [ans]] + [x + 2 for x in [ans]] + [a // b, a % b * c])
    return _code_q("What is the value of `result`?", code), o, i


def py_loops(rng, diff):
    if diff == "easy":
        n = rng.randint(3, 8)
        code = f"total = 0\nfor i in range({n}):\n    total += i\nresult = total"
    elif diff == "medium":
        a, b, s = rng.randint(0, 4), rng.randint(15, 30), rng.randint(2, 4)
        code = f"result = sum(range({a}, {b}, {s}))"
    else:
        n, m = rng.randint(4, 7), rng.randint(2, 3)
        code = (f"count = 0\nfor i in range(1, {n}):\n    for j in range(i, {n}):\n"
                f"        if (i + j) % {m} == 0:\n            count += 1\nresult = count")
    ans = _run(code)
    o, i = _num(rng, ans, [ans + 1, ans - 1, ans * 2, ans + 2])
    return _code_q("What is the value of `result` after this code runs?", code), o, i


def py_lists(rng, diff):
    if diff == "easy":
        nums = [rng.randint(1, 20) for _ in range(5)]
        code = f"nums = {nums}\nresult = nums[0] + nums[-1]"
        ans = _run(code)
        o, i = _num(rng, ans, [nums[0] + nums[1], nums[-1] + nums[-2], nums[0] * nums[-1], ans + 1])
        return _code_q("What is the value of `result`?", code), o, i
    if diff == "medium":
        nums = rng.sample(range(1, 30), 6)
        a = rng.randint(0, 2)
        b = rng.randint(a + 2, 5)
        code = f"nums = {nums}\nresult = nums[{a}:{b}]"
        ans = _run(code)
        wrong = [nums[a:b + 1], nums[max(a - 1, 0):b] if a else nums[a + 1:b + 1], nums[a + 1:b], nums[a:b][::-1]]
        o, i = _finish(rng, str(ans), [str(w) for w in wrong])
        return _code_q("What is the value of `result`?", code), o, i
    while True:
        nums = [rng.randint(1, 20) for _ in range(8)]
        m, k = rng.choice([2, 3]), rng.randint(2, 4)
        code = f"nums = {nums}\nresult = [n * {k} for n in nums if n % {m} == 0]"
        ans = _run(code)
        if 1 <= len(ans) <= 4:
            break
    alts = [f"[n * {k} for n in nums if n % {m} != 0]", f"[n + {k} for n in nums if n % {m} == 0]",
            f"[n for n in nums if n % {m} == 0]", f"[n * {k} for n in nums]"]
    wrong = [str(_run(f"nums = {nums}\nresult = {a}")) for a in alts]
    o, i = _finish(rng, str(ans), wrong)
    return _code_q("What is the value of `result`?", code), o, i


def py_functions(rng, diff):
    if diff == "easy":
        k, b, n = rng.randint(2, 5), rng.randint(1, 9), rng.randint(2, 8)
        code = f"def f(x):\n    return x * {k} + {b}\n\nresult = f({n})"
        ans = _run(code)
        o, i = _num(rng, ans, [n * k, n + k + b, (n + b) * k, ans + k])
    elif diff == "medium":
        d, x, y, z = rng.randint(2, 5), rng.randint(2, 6), rng.randint(2, 6), rng.randint(2, 6)
        code = f"def f(a, b={d}):\n    return a * b\n\nresult = f({x}) + f({y}, {z})"
        ans = _run(code)
        o, i = _num(rng, ans, [x * z + y * z, x * d + y * d, x + y + d + z, ans + d])
    else:
        if rng.random() < 0.5:
            n = rng.randint(3, 6)
            code = (f"def f(n):\n    if n <= 1:\n        return 1\n    return n * f(n - 1)\n\nresult = f({n})")
        else:
            n = rng.randint(5, 9)
            code = (f"def f(n):\n    if n < 2:\n        return n\n    return f(n - 1) + f(n - 2)\n\nresult = f({n})")
        ans = _run(code)
        o, i = _num(rng, ans, [ans + 1, ans - 1, ans * 2, ans // 2 + 1])
    return _code_q("What is the value of `result`?", code), o, i


def py_strings(rng, diff):
    if diff == "easy":
        w = rng.choice(WORDS)
        code = f's = "{w}"\nresult = s.upper()'
        ans = _run(code)
        wrong = [w, w.title(), w[::-1], w.upper()[::-1]]
        o, i = _finish(rng, ans, wrong)
    elif diff == "medium":
        w = rng.choice(WORDS)
        a = rng.randint(0, 2)
        b = rng.randint(a + 2, len(w) - 1)
        code = f's = "{w}"\nresult = s[{a}:{b}]'
        ans = _run(code)
        wrong = [w[a:b + 1], w[a + 1:b], w[a + 1:b + 1], w[b:], w[:a + 1] + "-"]
        o, i = _finish(rng, ans, wrong)
    else:
        words = rng.sample(WORDS, 4)
        code = (f'text = "{" ".join(words)}"\nparts = text.split()\n'
                f'result = "-".join(p.capitalize() for p in parts[::-1])')
        ans = _run(code)
        wrong = ["-".join(p.capitalize() for p in words), "-".join(words[::-1]),
                 " ".join(p.capitalize() for p in words[::-1])]
        o, i = _finish(rng, ans, wrong)
    return _code_q("What is the value of `result`?", code), o, i

# ── STATISTICS ────────────────────────────────────────────────────────

def _fix_sum(rng, vals, n_total, lo, hi):
    """Append values so the total count is n_total and the sum divides evenly."""
    vals = list(vals)
    while len(vals) < n_total - 1:
        vals.append(rng.randint(lo, hi))
    for _ in range(200):
        last = rng.randint(lo, hi)
        if (sum(vals) + last) % n_total == 0:
            return vals + [last]
    return vals + [lo + (-sum(vals) - lo) % n_total]


def st_mean(rng, diff):
    if diff == "easy":
        data = _fix_sum(rng, [], 4, 2, 14)
        ans = sum(data) // 4
        o, i = _num(rng, ans, [ans + 1, ans - 1, sum(data), max(data)])
        return f"What is the mean of {data}?", o, i
    if diff == "medium":
        data = _fix_sum(rng, [], 6, 10, 50)
        ans = sum(data) // 6
        o, i = _num(rng, ans, [ans + 2, ans - 2, int(median(data)), sum(data) // 5])
        return f"What is the mean of {data}?", o, i
    n1, n2 = rng.sample([10, 20, 30, 40], 2)
    a1, a2 = rng.sample(range(50, 91), 2)
    comb = (n1 * a1 + n2 * a2) / (n1 + n2)
    wrong = [(a1 + a2) / 2, (n2 * a1 + n1 * a2) / (n1 + n2), a1, a2]
    o, i = _num(rng, round(comb, 1), [round(w, 1) for w in wrong], "{:.1f}", 0.5)
    return (f"Class A has {n1} students with a mean score of {a1}. Class B has {n2} students "
            f"with a mean score of {a2}. What is the combined mean score?"), o, i


def st_median(rng, diff):
    if diff == "easy":
        data = rng.sample(range(1, 30), 5)
        s = sorted(data)
        o, i = _num(rng, s[2], [s[1], s[3], data[0] if data[0] != s[2] else s[0], round(sum(data) / 5)], "{:g}")
        return f"What is the median of {data}?", o, i
    if diff == "medium":
        data = rng.sample(range(1, 40), 6)
        s = sorted(data)
        ans = (s[2] + s[3]) / 2
        o, i = _num(rng, ans, [s[2], s[3], round(sum(data) / 6, 1)], "{:g}", 0.5)
        return f"What is the median of {data}?", o, i
    data = rng.sample(range(1, 40), 5)
    k = rng.randint(1, 45)
    while k in data:
        k = rng.randint(1, 45)
    new = sorted(data + [k])
    ans = median(new)
    o, i = _num(rng, ans, [median(data), k, round(sum(new) / 6, 1)], "{:g}", 0.5)
    return f"The data set {data} gets a new value, {k}. What is the new median?", o, i


def _unique_mode_data(rng, n=9):
    while True:
        data = [rng.randint(1, 8) for _ in range(n)]
        top = Counter(data).most_common(2)
        if len(top) > 1 and top[0][1] > top[1][1] >= 2:
            return data


def st_mode(rng, diff):
    if diff == "easy":
        data = _unique_mode_data(rng, 8)
        ans = Counter(data).most_common(1)[0][0]
        others = [v for v in set(data) if v != ans]
        o, i = _num(rng, ans, others, "{}")
        return f"What is the mode of {data}?", o, i
    if diff == "medium":
        data = _unique_mode_data(rng, 9)
        mode = Counter(data).most_common(1)[0][0]
        med = median(data)
        ans = mode + med
        o, i = _num(rng, ans, [mode, med, mode * med, ans + 1], "{:g}", 1)
        return f"For the data {data}, what is the mode plus the median?", o, i
    while True:
        data = [rng.randint(1, 7) for _ in range(9)]
        c = Counter(data)
        (m1, c1), (m2, c2) = c.most_common(2)
        if c1 == c2 + 1 and c2 >= 2:
            break
    data2 = data + [m2]
    cnt = Counter(data2)
    top = max(cnt.values())
    modes = sorted(v for v, k in cnt.items() if k == top)
    fmt = lambda ms: f"{ms[0]} only" if len(ms) == 1 else f"{ms[0]} and {ms[1]}"
    correct = fmt(modes)
    vals = sorted(set(data))
    pool = [fmt([v]) for v in vals] + [fmt(sorted([a, b])) for a in vals for b in vals if a < b]
    rng.shuffle(pool)
    pool += [fmt([v]) for v in range(1, 8)] + [fmt([a, b]) for a in range(1, 8) for b in range(a + 1, 8)]
    o, i = _finish(rng, correct, pool)
    return f"The data set {data} gets a new value, {m2}. Which value(s) are now the mode?", o, i


def st_probability(rng, diff):
    if diff == "easy":
        events = {"an even number": 3, "a number greater than 4": 2,
                  "a prime number": 3, "a multiple of 3": 2, "a number less than 3": 2}
        name, cnt = rng.choice(list(events.items()))
        ans = Fraction(cnt, 6)
        pool = [Fraction(k, 6) for k in range(1, 6)] + [Fraction(1, 3), Fraction(2, 3)]
        o, i = _finish(rng, str(ans), [str(p) for p in pool])
        return f"A fair six-sided die is rolled once. What is the probability of rolling {name}?", o, i
    if diff == "medium":
        s = rng.randint(4, 10)
        cnt = sum(1 for a in range(1, 7) for b in range(1, 7) if a + b == s)
        ans = Fraction(cnt, 36)
        pool = [Fraction(cnt + 1, 36), Fraction(max(cnt - 1, 1), 36), Fraction(cnt, 12), Fraction(1, 6), Fraction(1, s)]
        o, i = _finish(rng, str(ans), [str(p) for p in pool])
        return f"Two fair dice are rolled. What is the probability that the sum is {s}?", o, i
    r, b = rng.randint(3, 6), rng.randint(3, 6)
    n = r + b
    ans = Fraction(r, n) * Fraction(r - 1, n - 1)
    pool = [Fraction(r, n) ** 2, Fraction(b, n) * Fraction(b - 1, n - 1),
            2 * Fraction(r, n) * Fraction(b, n - 1), 1 - Fraction(b, n) * Fraction(b - 1, n - 1)]
    o, i = _finish(rng, str(ans), [str(p) for p in pool])
    return (f"A bag has {r} red and {b} blue marbles. Two marbles are drawn without replacement. "
            f"What is the probability that both are red?"), o, i


def st_variance(rng, diff):
    if diff == "easy":
        data = rng.sample(range(2, 50), 6)
        ans = max(data) - min(data)
        o, i = _num(rng, ans, [max(data), min(data), max(data) + min(data), round(sum(data) / 6)])
        return f"What is the range of {data}?", o, i
    if diff == "medium":
        data = _fix_sum(rng, [], 5, 2, 12)
        mean = sum(data) // 5
        ss = sum((x - mean) ** 2 for x in data)
        ans = round(ss / 5, 2)
        o, i = _num(rng, ans, [round(ss / 4, 2), ss, round((ss / 5) ** 0.5, 2), mean], "{:g}", 0.5)
        return f"What is the population variance of {data}?", o, i
    s, k = rng.randint(2, 6), rng.randint(2, 5)
    o, i = _num(rng, k * s, [k * k * s, s, s + k, k * s * s])
    return (f"A data set has a variance of {s * s}. Every value is multiplied by {k}. "
            f"What is the new standard deviation?"), o, i


GENERATORS = {
    "Linear Equations": linear_equations, "Exponents": exponents, "Factoring": factoring,
    "Inequalities": inequalities, "Functions": functions,
    "Variables & Operators": py_variables, "Loops": py_loops, "Lists": py_lists,
    "Functions in Python": py_functions, "Strings": py_strings,
    "Mean": st_mean, "Median": st_median, "Mode": st_mode,
    "Probability": st_probability, "Spread & Variance": st_variance,
}


def generate_topic_questions(rng: random.Random, topic: str, per_difficulty: int = 4):
    """Return a list of dicts for one topic: per_difficulty questions at each level, unique text."""
    gen = GENERATORS[topic]
    out, seen = [], set()
    for diff in DIFFICULTIES:
        made, attempts = 0, 0
        while made < per_difficulty:
            attempts += 1
            if attempts > 500:
                raise RuntimeError(f"Could not generate enough unique {diff} questions for {topic}")
            text, options, idx = gen(rng, diff)
            if text in seen:
                continue
            seen.add(text)
            out.append({"topic": topic, "difficulty": diff, "text": text,
                        "options": options, "correct_index": idx})
            made += 1
    return out
