"""
Parses the LaTeX/XML question bulk-upload format (PV-A-1's "Вопросы будут
предоставляться в формате LaTeX / XML"): an XML document with one <question>
element per question, each carrying type/mark/penalty/category metadata and
either a <latex> body (single/multiple choice, see .latex_import) or a plain
<text>/<answer> pair (free-response "text" questions).

Example:
    <questions>
      <question type="multiple" mark_out_of="1" penalty="0" category="линейная алгебра/матрицы">
        <latex><![CDATA[
          \\begin{multi}{T6}
           Период функции $\\cos\\frac{k\\pi}{l}x$ равен
           \\item* 4
           \\item 8
          \\end{multi}
        ]]></latex>
      </question>
      <question type="text" mark_out_of="1" penalty="0" category="линейная алгебра">
        <text>Чему равен определитель единичной матрицы 3x3?</text>
        <answer>1</answer>
      </question>
    </questions>
"""
from dataclasses import dataclass
from xml.etree import ElementTree as ET

from .latex_import import LatexParseError, parse_multi_environment

VALID_QUESTION_TYPES = {"single", "multiple", "text"}


class QuestionImportError(Exception):
    pass


@dataclass
class ImportedQuestion:
    text: str
    problem: str
    answer: dict
    question_type: str
    mark_out_of: int
    penalty: int
    category_path: list[str]


def _parse_int(value: str | None, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(float(value))
    except ValueError:
        raise QuestionImportError(f"Invalid integer value: {value!r}")


def _category_path(question_el: ET.Element) -> list[str]:
    raw = question_el.get("category", "")
    path = [part.strip() for part in raw.split("/") if part.strip()]
    if not path:
        raise QuestionImportError("Each <question> requires a non-empty category attribute")
    return path


def _parse_text_question(question_el: ET.Element, *, mark_out_of: int, penalty: int) -> ImportedQuestion:
    text_el = question_el.find("text")
    answer_el = question_el.find("answer")
    if text_el is None or not (text_el.text or "").strip():
        raise QuestionImportError("text-type question requires a non-empty <text>")
    if answer_el is None or not (answer_el.text or "").strip():
        raise QuestionImportError("text-type question requires a non-empty <answer>")

    prompt = text_el.text.strip()
    return ImportedQuestion(
        text=prompt,
        problem=prompt,
        answer={"correct_text": answer_el.text.strip()},
        question_type="text",
        mark_out_of=mark_out_of,
        penalty=penalty,
        category_path=_category_path(question_el),
    )


def _parse_choice_question(
    question_el: ET.Element, *, question_type: str, mark_out_of: int, penalty: int
) -> ImportedQuestion:
    latex_el = question_el.find("latex")
    if latex_el is None or not (latex_el.text or "").strip():
        raise QuestionImportError(f"{question_type}-type question requires a non-empty <latex> body")

    try:
        parsed = parse_multi_environment(latex_el.text)
    except LatexParseError as exc:
        raise QuestionImportError(str(exc)) from exc

    if question_type == "single" and len(parsed.correct_indices) != 1:
        raise QuestionImportError(r"single-choice question must mark exactly one \item* as correct")

    return ImportedQuestion(
        text=parsed.prompt,
        problem=parsed.prompt,
        answer={"choices": parsed.choices, "correct": parsed.correct_indices},
        question_type=question_type,
        mark_out_of=mark_out_of,
        penalty=penalty,
        category_path=_category_path(question_el),
    )


def parse_questions_xml(xml_content: str | bytes) -> list[ImportedQuestion]:
    # xml.etree expands DOCTYPE-declared internal entities (billion-laughs DoS) and
    # would otherwise need a hardened parser (e.g. defusedxml) to be fully safe
    # against untrusted input; rejecting any DOCTYPE outright avoids that class of
    # attack without adding a dependency. Uploads are teacher-authenticated but not
    # otherwise trusted.
    needle = b"<!doctype" if isinstance(xml_content, bytes) else "<!doctype"
    haystack = xml_content.lower()
    if needle in haystack:
        raise QuestionImportError("DOCTYPE declarations are not allowed in uploaded XML")

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as exc:
        raise QuestionImportError(f"Invalid XML: {exc}") from exc

    question_elements = root.findall("question") if root.tag != "question" else [root]
    if not question_elements:
        raise QuestionImportError("No <question> elements found")

    questions: list[ImportedQuestion] = []
    for question_el in question_elements:
        question_type = question_el.get("type", "single")
        if question_type not in VALID_QUESTION_TYPES:
            raise QuestionImportError(
                f"Unknown question type {question_type!r}; expected one of {sorted(VALID_QUESTION_TYPES)}"
            )
        mark_out_of = _parse_int(question_el.get("mark_out_of"), default=1)
        penalty = _parse_int(question_el.get("penalty"), default=0)

        if question_type == "text":
            questions.append(_parse_text_question(question_el, mark_out_of=mark_out_of, penalty=penalty))
        else:
            questions.append(
                _parse_choice_question(
                    question_el, question_type=question_type, mark_out_of=mark_out_of, penalty=penalty
                )
            )

    return questions
