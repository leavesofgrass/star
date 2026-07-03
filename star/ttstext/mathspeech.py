# ---------------------------------------------------------------------------
# Math expression normalization
# ---------------------------------------------------------------------------
"""LaTeX / math-notation to spoken-English normalization for TTS."""
from .._runtime import *  # noqa: F401,F403


def _normalize_math_inline(text: str) -> str:
    """Convert LaTeX math notation to spoken English for TTS.

    Applied to plain text before it reaches the speech engine.
    Handles the most common patterns in academic/STEM writing.
    """
    # Strip display/inline delimiters (order matters: $$ before $)
    text = re.sub(r"\$\$(.+?)\$\$", r" \1 ", text, flags=re.DOTALL)
    text = re.sub(r"\$(.+?)\$", r" \1 ", text)
    text = re.sub(r"\\\[(.+?)\\\]", r" \1 ", text, flags=re.DOTALL)
    text = re.sub(r"\\\((.+?)\\\)", r" \1 ", text)

    # Statistical accents
    text = re.sub(r"\\bar\{(\w+)\}", r"\1-bar", text)
    text = re.sub(r"\\hat\{(\w+)\}", r"\1-hat", text)
    text = re.sub(r"\\tilde\{(\w+)\}", r"\1-tilde", text)
    text = re.sub(r"\\overline\{([^}]+)\}", r"\1 bar", text)

    # Fractions and roots
    text = re.sub(r"\\frac\{([^}]+)\}\{([^}]+)\}", r"\1 over \2", text)
    text = re.sub(r"\\sqrt\[([^\]]+)\]\{([^}]+)\}", r"\1-th root of \2", text)
    text = re.sub(r"\\sqrt\{([^}]+)\}", r"square root of \1", text)

    # Superscripts / powers
    text = re.sub(r"\^\{-1\}", " inverse", text)
    text = re.sub(r"\^\{2\}|\^2(?=\W)", " squared", text)
    text = re.sub(r"\^\{3\}|\^3(?=\W)", " cubed", text)
    text = re.sub(r"\^\{([^}]+)\}", r" to the \1", text)
    text = re.sub(r"\^(\w)", r" to the \1", text)

    # Subscripts
    text = re.sub(r"_\{(\w)(\w+)\}", r" sub \1 \2", text)
    text = re.sub(r"_\{(\w+)\}", r" sub \1", text)
    text = re.sub(r"_(\w)", r" sub \1", text)

    # Greek letters
    greek = {
        "alpha": "alpha",
        "beta": "beta",
        "gamma": "gamma",
        "delta": "delta",
        "epsilon": "epsilon",
        "zeta": "zeta",
        "eta": "eta",
        "theta": "theta",
        "lambda": "lambda",
        "mu": "mu",
        "nu": "nu",
        "xi": "xi",
        "pi": "pi",
        "rho": "rho",
        "sigma": "sigma",
        "tau": "tau",
        "phi": "phi",
        "chi": "chi",
        "psi": "psi",
        "omega": "omega",
        "Gamma": "Gamma",
        "Delta": "Delta",
        "Theta": "Theta",
        "Lambda": "Lambda",
        "Pi": "Pi",
        "Sigma": "Sigma",
        "Phi": "Phi",
        "Psi": "Psi",
        "Omega": "Omega",
    }
    for cmd, spoken in greek.items():
        text = text.replace(f"\\{cmd}", f" {spoken} ")

    # Trig and common functions (order: longer names first to avoid partial matches)
    trig = [
        ("arcsin", "arcsine"),
        ("arccos", "arccosine"),
        ("arctan", "arctangent"),
        ("sin", "sine"),
        ("cos", "cosine"),
        ("tan", "tangent"),
        ("cot", "cotangent"),
        ("sec", "secant"),
        ("csc", "cosecant"),
        ("ln", "natural log"),
        ("log", "log"),
        ("exp", "e to the power"),
        ("lim", "limit"),
        ("sum", "sum"),
    ]
    for cmd, spoken in trig:
        text = re.sub(rf"\\{cmd}\b", f" {spoken} ", text)

    # Operators and symbols
    ops = [
        (r"\\times\b", " times "),
        (r"×", " times "),
        (r"\\div\b", " divided by "),
        (r"÷", " divided by "),
        (r"\\pm\b", " plus or minus "),
        (r"\\neq\b", " not equal to "),
        (r"\\leq\b|\\le\b", " less than or equal to "),
        (r"≤", " less than or equal to "),
        (r"\\geq\b|\\ge\b", " greater than or equal to "),
        (r"≥", " greater than or equal to "),
        (r"\\approx\b", " approximately equal to "),
        (r"≈", " approximately equal to "),
        (r"\\infty\b", " infinity "),
        (r"∞", " infinity "),
        (r"\\rightarrow\b|\\to\b", " approaches "),
        (r"→", " approaches "),
        (r"\\leftarrow\b", " from "),
        (r"←", " from "),
        (r"\\nabla\b", " gradient of "),
        (r"\\partial\b", " partial "),
        (r"\\prod\b", " product "),
        (r"\\int\b", " integral "),
    ]
    for pattern, replacement in ops:
        text = re.sub(pattern, replacement, text)

    # Clean up residual LaTeX commands and braces
    text = re.sub(r"\\[a-zA-Z]+", " ", text)
    text = re.sub(r"[{}]", "", text)
    text = re.sub(r"  +", " ", text)
    return text.strip()
