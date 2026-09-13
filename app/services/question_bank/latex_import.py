"""
Parses this school's `\\begin{multi}{ID} ... \\end{multi}` LaTeX convention for
single/multiple-choice questions (confirmed by the Admin PDF's question editor):

    \\begin{multi}{T6}
     Период функции  $\\cos\\frac{k\\pi}{l}x$ при $k=8, \\, l=16$ равен
     \\item* 4
     \\item  верный ответ отсутствует
     \\item 2
     \\item 8
     \\item  1/4
    \\end{multi}

The first line (up to the first \\item) is the question prompt — LaTeX math
segments ($...$) are kept verbatim, not evaluated. Each \\item is one choice;
\\item* (with an asterisk) marks a correct choice — multiple \\item* entries are
how a "multiple" (multi-select) question is authored.
"""
import re
from dataclasses import dataclass

_MULTI_RE = re.compile(r"\\begin\{multi\}\{(?P<id>[^}]*)\}(?P<body>.*?)\\end\{multi\}", re.DOTALL)
_ITEM_RE = re.compile(r"\\item(?P<star>\*)?[ \t]*(?P<text>.*?)(?=\\item|\Z)", re.DOTALL)


class LatexParseError(Exception):
    pass


@dataclass
class ParsedMultiQuestion:
    latex_id: str
    prompt: str
    choices: list[str]
    correct_indices: list[int]


def parse_multi_environment(latex: str) -> ParsedMultiQuestion:
    match = _MULTI_RE.search(latex or "")
    if not match:
        raise LatexParseError(r"No \begin{multi}{...} ... \end{multi} block found")

    latex_id = match.group("id").strip()
    body = match.group("body")

    first_item = re.search(r"\\item", body)
    if not first_item:
        raise LatexParseError(r"No \item entries found in \begin{multi} block")

    prompt = body[: first_item.start()].strip()
    if not prompt:
        raise LatexParseError(r"Empty question prompt before the first \item")

    choices: list[str] = []
    correct_indices: list[int] = []
    for item_match in _ITEM_RE.finditer(body[first_item.start():]):
        text = " ".join(item_match.group("text").split())
        if not text:
            continue
        if item_match.group("star"):
            correct_indices.append(len(choices))
        choices.append(text)

    if not choices:
        raise LatexParseError(r"No answer choices parsed from \item entries")
    if not correct_indices:
        raise LatexParseError(r"No correct choice marked (expected at least one \item*)")

    return ParsedMultiQuestion(
        latex_id=latex_id, prompt=prompt, choices=choices, correct_indices=correct_indices
    )
