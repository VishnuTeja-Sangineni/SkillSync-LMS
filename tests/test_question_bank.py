"""Independent checks that generated questions are valid and their answer keys are correct."""
import random
import re

import pytest

from scripts.question_bank import DIFFICULTIES, GENERATORS, generate_topic_questions

PYTHON_TOPICS = ["Variables & Operators", "Loops", "Lists", "Functions in Python", "Strings"]


@pytest.mark.parametrize("topic", list(GENERATORS))
@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_generators_produce_valid_questions(topic, difficulty):
    for seed in range(200):
        text, options, idx = GENERATORS[topic](random.Random(seed), difficulty)
        assert len(options) == 4 and len(set(options)) == 4, (seed, options)
        assert 0 <= idx < 4
        assert text.strip()


@pytest.mark.parametrize("topic", PYTHON_TOPICS)
def test_python_answer_keys_match_real_execution(topic):
    """Re-run the code shown in each question and compare with the marked answer."""
    checked = 0
    for diff in DIFFICULTIES:
        for seed in range(60):
            text, options, idx = GENERATORS[topic](random.Random(seed), diff)
            code = re.search(r"```python\n(.*?)\n```", text, re.S)
            if not code:
                continue  # e.g. the "what is the type of..." question has no code block
            env = {}
            exec(code.group(1), env)
            assert options[idx] == str(env["result"]), (topic, diff, seed)
            checked += 1
    assert checked > 20


def test_linear_equation_answers_are_solutions():
    for diff in DIFFICULTIES:
        for seed in range(100):
            text, options, idx = GENERATORS["Linear Equations"](random.Random(seed), diff)
            eq = text.split(": ", 1)[1]
            left, right = (re.sub(r"(\d)x", r"\1*x", side) for side in eq.split("="))
            x = int(options[idx].split("=")[1])
            assert eval(left, {"x": x}) == eval(right, {"x": x}), text
            # and no other integer in range is a solution
            sols = [v for v in range(-60, 61) if eval(left, {"x": v}) == eval(right, {"x": v})]
            assert sols == [x], text


def test_topic_bank_has_balanced_unique_questions():
    qs = generate_topic_questions(random.Random(3), "Probability")
    assert len(qs) == 12
    assert len({q["text"] for q in qs}) == 12
    for d in DIFFICULTIES:
        assert sum(q["difficulty"] == d for q in qs) == 4
