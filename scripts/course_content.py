"""
Course structure and lesson text for the synthetic dataset.

Three courses, five topics each. Every topic becomes one module with two
lessons and one topic quiz. Question text comes from scripts/question_bank.py.
"""

COURSES = [
    {
        "title": "Algebra Fundamentals",
        "description": "Build a solid base in algebra: equations, exponents, factoring, inequalities and functions.",
        "teacher": "teacher@skillsync.com",
        "topics": ["Linear Equations", "Exponents", "Factoring", "Inequalities", "Functions"],
    },
    {
        "title": "Python Programming Basics",
        "description": "Learn core Python: operators, loops, lists, functions and strings, with hands-on code reading.",
        "teacher": "teacher@skillsync.com",
        "topics": ["Variables & Operators", "Loops", "Lists", "Functions in Python", "Strings"],
    },
    {
        "title": "Statistics Essentials",
        "description": "Understand data: averages, spread, probability and how to reason about uncertainty.",
        "teacher": "priya.nair@skillsync.com",
        "topics": ["Mean", "Median", "Mode", "Probability", "Spread & Variance"],
    },
]

# (lesson title, content, minutes)
LESSONS = {
    "Linear Equations": [
        ("Solving One-Step and Two-Step Equations", "A linear equation has the variable to the first power. To solve, undo operations in reverse order: first add or subtract, then multiply or divide.\n\nExample: 3x + 5 = 20 → subtract 5 → 3x = 15 → divide by 3 → x = 5.", 12),
        ("Variables on Both Sides", "When x appears on both sides, collect the x-terms on one side first.\n\nExample: 5x + 4 = 3x + 20 → subtract 3x → 2x + 4 = 20 → subtract 4 → 2x = 16 → x = 8. Always check by substituting back.", 15),
    ],
    "Exponents": [
        ("Powers and Basic Rules", "a^n means multiply a by itself n times. So 2^4 = 2 × 2 × 2 × 2 = 16.\n\nProduct rule: x^a · x^b = x^(a+b). Quotient rule: x^a ÷ x^b = x^(a−b).", 10),
        ("Power of a Power", "(x^a)^b = x^(a·b). Combine this with the product and quotient rules to simplify.\n\nExample: (x^3)^2 ÷ x^4 = x^6 ÷ x^4 = x^2.", 12),
    ],
    "Factoring": [
        ("Factoring Trinomials", "To factor x² + bx + c, find two numbers that multiply to c and add to b.\n\nExample: x² + 7x + 12 → numbers 3 and 4 → (x + 3)(x + 4).", 14),
        ("Difference of Squares and Roots", "x² − k² = (x − k)(x + k). Once an expression is factored, set each factor to zero to find the roots.\n\nExample: x² − 9 = (x − 3)(x + 3), so x = 3 or x = −3.", 14),
    ],
    "Inequalities": [
        ("Solving Basic Inequalities", "Solve inequalities like equations: whatever you do to one side, do to the other.\n\nExample: x + 4 > 9 → x > 5. The solution is a range of values, not a single number.", 10),
        ("Flipping the Sign", "When you multiply or divide both sides by a negative number, the inequality sign flips.\n\nExample: −2x < 6 → divide by −2 → x > −3. Forgetting to flip is the most common mistake.", 12),
    ],
    "Functions": [
        ("Function Notation", "f(x) = 2x + 3 is a rule: put in x, get out 2x + 3. To find f(4), replace x with 4: f(4) = 2(4) + 3 = 11.", 10),
        ("Composing Functions", "f(g(x)) means apply g first, then f to the result. If f(x) = 2x + 1 and g(x) = x², then f(g(3)) = f(9) = 19. Order matters: g(f(3)) = 49.", 15),
    ],
    "Variables & Operators": [
        ("Variables and Data Types", "A variable stores a value: age = 21. Common types are int (whole numbers), float (decimals), str (text), bool (True/False), list, tuple and dict.\n\nUse type(x) to see a value's type.", 10),
        ("Arithmetic Operators", "+ − * are as usual. / gives a float, // is floor division (7 // 2 = 3), % is the remainder (7 % 2 = 1) and ** is power (2 ** 3 = 8).", 12),
    ],
    "Loops": [
        ("For Loops and range()", "for i in range(5): runs the body with i = 0, 1, 2, 3, 4. range(a, b, step) starts at a, stops before b, and moves by step.\n\nAccumulate with total += i.", 12),
        ("Nested Loops and Conditions", "A loop inside a loop runs the inner body once for every outer step. Add if statements to count only the cases you care about. Trace small examples by hand before running code.", 15),
    ],
    "Lists": [
        ("Indexing and Slicing", "Lists are ordered. nums[0] is the first item and nums[-1] the last. nums[a:b] returns items from index a up to, but not including, b.", 10),
        ("List Comprehensions", "[n * 2 for n in nums if n % 2 == 0] builds a new list: take each n, keep it only if the condition is true, and apply the expression. It replaces a short loop with one line.", 14),
    ],
    "Functions in Python": [
        ("Defining and Calling Functions", "def f(x): return x * 2 defines a function; f(5) calls it and gives 10. Use default values like def f(a, b=2) so callers can skip arguments.", 12),
        ("Recursion", "A recursive function calls itself on a smaller problem and needs a base case to stop. Factorial: f(n) = n * f(n − 1) with f(1) = 1. Fibonacci: f(n) = f(n−1) + f(n−2).", 16),
    ],
    "Strings": [
        ("String Basics", "Strings are sequences of characters. len(s) gives the length, s.upper() and s.lower() change case, and s[::-1] reverses the string.", 10),
        ("Slicing, Splitting and Joining", "s[a:b] slices like lists. s.split() breaks text into words; '-'.join(words) glues them back together with a separator. capitalize() uppercases the first letter.", 13),
    ],
    "Mean": [
        ("The Arithmetic Mean", "Mean = sum of values ÷ number of values. For 4, 6, 8, 10 the mean is 28 ÷ 4 = 7. The mean is pulled toward extreme values.", 10),
        ("Weighted and Combined Means", "To combine groups, weight each group's mean by its size: (n1·m1 + n2·m2) ÷ (n1 + n2). Averaging the two means directly is only right when the groups are the same size.", 14),
    ],
    "Median": [
        ("Finding the Median", "Sort the data. With an odd count, the median is the middle value. With an even count, it is the average of the two middle values.", 10),
        ("Median vs Mean", "The median resists outliers. Adding one extreme value can move the mean a lot but shifts the median only to a neighbouring value.", 12),
    ],
    "Mode": [
        ("The Mode", "The mode is the most frequent value. A data set can have one mode, several modes (ties) or none if every value is unique.", 8),
        ("Combining Measures", "Mean, median and mode describe the centre in different ways. Compare them: if they differ a lot, the data is probably skewed.", 12),
    ],
    "Probability": [
        ("Basic Probability", "P(event) = favourable outcomes ÷ total outcomes. For a fair die, P(even) = 3/6 = 1/2. Probabilities range from 0 to 1.", 10),
        ("Dependent Events", "Without replacement, probabilities change after each draw. P(both red) from 3 red and 4 blue = 3/7 × 2/6 = 1/7. Multiply along the path.", 15),
    ],
    "Spread & Variance": [
        ("Range and Variance", "Range = max − min. Variance is the average squared distance from the mean; standard deviation is its square root and is in the same units as the data.", 14),
        ("Scaling Data", "Multiplying every value by k multiplies the standard deviation by k and the variance by k². Adding a constant changes the mean but not the spread.", 12),
    ],
}
