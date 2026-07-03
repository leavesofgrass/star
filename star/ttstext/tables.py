"""Markdown-table narration for TTS."""
from .._runtime import *  # noqa: F401,F403


# -- Table narration ---------------------------------------------------------

def _tables_to_narration(text: str, mode: str = "structured") -> str:
    """Convert markdown table syntax in *text* to TTS-friendly prose.

    mode="structured"  (default)
        Table with 3 columns: Name, Age, City.
        Row 1: Name is Alice, Age is 30, City is New York.
        Row 2: Name is Bob, Age is 25, City is Boston.

    mode="flat"
        Cells joined with period-space (consistent legacy behavior).

    mode="skip"
        Replace entire table with a one-line announcement.

    Must be called on raw markdown BEFORE other stripping so that pipe
    characters and separator rows are still present.
    """
    if mode not in ("structured", "flat", "skip"):
        mode = "structured"

    lines = text.split("\n")
    result: List[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        if "|" not in line or not line.strip().startswith("|"):
            result.append(line)
            i += 1
            continue

        # Gather the full table block.
        block: List[str] = []
        while i < len(lines) and "|" in lines[i] and lines[i].strip().startswith("|"):
            block.append(lines[i])
            i += 1

        if mode == "skip":
            raw = [
                c.strip() for c in block[0].strip().strip("|").split("|") if c.strip()
            ]
            n = len(raw)
            result.append(
                f"Table with {n} column{'s' if n != 1 else ''} \u2014 skipped."
            )
            result.append("")
            continue

        # Parse cells.
        parsed: List[List[str]] = [
            [c.strip() for c in bl.strip().strip("|").split("|")] for bl in block
        ]

        # Separate header from data rows (skip separator lines).
        header: List[str] = []
        data_rows: List[List[str]] = []
        for cells in parsed:
            if bool(cells) and all(re.match(r"^[-:]+$", c) for c in cells if c):
                continue  # separator row
            clean = [c for c in cells if c]
            if not header:
                header = clean
            else:
                data_rows.append(clean)

        if mode == "flat":
            for cells in [header] + data_rows:
                clean = [c for c in cells if c]
                if clean:
                    result.append(".  ".join(clean) + ".")
            result.append("")
            continue

        # structured mode
        ncols = len(header)
        result.append(
            f"Table with {ncols} column{'s' if ncols != 1 else ''}: {', '.join(header)}."
        )
        for ri, data in enumerate(data_rows, 1):
            if header:
                parts = [
                    f"{hdr} is {data[hi]}"
                    for hi, hdr in enumerate(header)
                    if hi < len(data) and data[hi]
                ]
                if parts:
                    result.append(f"Row {ri}: {', '.join(parts)}.")
            else:
                clean = [c for c in data if c]
                if clean:
                    result.append(f"Row {ri}: {', '.join(clean)}.")

        result.append("")

    return "\n".join(result)
