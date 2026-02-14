from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from xml.etree import ElementTree as ET


@dataclass
class ParsedQuestion:
    text: str
    answer: dict[str, Any]
    question_type: str = "multiple_choice"
    problem: str = ""
    mark_out_of: int = 1
    penalty: int = 0
    is_active: bool = True


def parse_questions_from_tex(content: str) -> list[ParsedQuestion]:
    blocks = re.findall(r"\\begin\{multi\}\{[^}]*\}(.*?)\\end\{multi\}", content, flags=re.DOTALL)
    questions: list[ParsedQuestion] = []

    for block in blocks:
        cleaned = block.strip()
        item_match = re.search(r"\\item\*?", cleaned)
        if item_match is None:
            continue

        question_text = cleaned[: item_match.start()].strip()
        question_text = re.sub(r"\s+", " ", question_text)
        if not question_text:
            continue

        answers: list[str] = []
        correct_answers: list[str] = []
        for match in re.finditer(r"\\item(\*)?\s*(.*?)(?=(\\item\*?|$))", cleaned[item_match.start() :], flags=re.DOTALL):
            answer_text = re.sub(r"\s+", " ", match.group(2).strip())
            if not answer_text:
                continue
            answers.append(answer_text)
            if match.group(1) == "*":
                correct_answers.append(answer_text)

        if not answers:
            continue

        questions.append(
            ParsedQuestion(
                text=question_text,
                answer={"options": answers, "correct": correct_answers},
                question_type="multiple_choice",
            )
        )

    return questions


def parse_questions_from_moodle_xml(content: str) -> list[ParsedQuestion]:
    root = ET.fromstring(content)
    questions: list[ParsedQuestion] = []

    for question_el in root.findall("question"):
        if question_el.get("type") == "category":
            continue

        text_node = question_el.find("./questiontext/text")
        question_text = (text_node.text or "").strip() if text_node is not None else ""
        if not question_text:
            continue

        answers: list[str] = []
        correct_answers: list[str] = []
        for answer_el in question_el.findall("answer"):
            answer_text_node = answer_el.find("text")
            answer_text = (answer_text_node.text or "").strip() if answer_text_node is not None else ""
            if not answer_text:
                continue
            answers.append(answer_text)
            try:
                fraction = float(answer_el.get("fraction", "0"))
            except ValueError:
                fraction = 0.0
            if fraction > 0:
                correct_answers.append(answer_text)

        if not answers:
            continue

        questions.append(
            ParsedQuestion(
                text=question_text,
                answer={"options": answers, "correct": correct_answers},
                question_type="multiple_choice",
            )
        )

    return questions