import pytest

from app.services.question_bank.question_import import QuestionImportError, parse_questions_xml

MULTI_XML = r"""
<questions>
  <question type="multiple" mark_out_of="1" penalty="0" category="линейная алгебра/матрицы">
    <latex><![CDATA[
      \begin{multi}{T6}
       Период функции $\cos\frac{k\pi}{l}x$ равен
       \item* 4
       \item 8
      \end{multi}
    ]]></latex>
  </question>
</questions>
"""

TEXT_XML = r"""
<questions>
  <question type="text" mark_out_of="2" penalty="0" category="линейная алгебра">
    <text>Чему равен определитель единичной матрицы 3x3?</text>
    <answer>1</answer>
  </question>
</questions>
"""


class TestParseQuestionsXml:
    def test_parses_multiple_choice_question(self):
        [question] = parse_questions_xml(MULTI_XML)

        assert question.question_type == "multiple"
        assert question.category_path == ["линейная алгебра", "матрицы"]
        assert question.mark_out_of == 1
        assert question.penalty == 0
        assert question.answer == {"choices": ["4", "8"], "correct": [0]}
        assert "cos" in question.text

    def test_parses_text_question(self):
        [question] = parse_questions_xml(TEXT_XML)

        assert question.question_type == "text"
        assert question.category_path == ["линейная алгебра"]
        assert question.mark_out_of == 2
        assert question.answer == {"correct_text": "1"}

    def test_parses_multiple_questions_in_one_document(self):
        xml = r"""
        <questions>
          <question type="text" mark_out_of="1" penalty="0" category="A">
            <text>Q1</text>
            <answer>1</answer>
          </question>
          <question type="text" mark_out_of="1" penalty="0" category="B">
            <text>Q2</text>
            <answer>2</answer>
          </question>
        </questions>
        """
        questions = parse_questions_xml(xml)
        assert len(questions) == 2

    def test_single_type_requires_exactly_one_correct_choice(self):
        xml = r"""
        <questions>
          <question type="single" category="Topic">
            <latex><![CDATA[
              \begin{multi}{Q1}
               Prompt
               \item* A
               \item* B
              \end{multi}
            ]]></latex>
          </question>
        </questions>
        """
        with pytest.raises(QuestionImportError):
            parse_questions_xml(xml)

    def test_missing_category_raises(self):
        xml = r"""
        <questions>
          <question type="text">
            <text>Q</text>
            <answer>A</answer>
          </question>
        </questions>
        """
        with pytest.raises(QuestionImportError):
            parse_questions_xml(xml)

    def test_unknown_type_raises(self):
        xml = '<questions><question type="essay" category="Topic"></question></questions>'
        with pytest.raises(QuestionImportError):
            parse_questions_xml(xml)

    def test_invalid_xml_raises(self):
        with pytest.raises(QuestionImportError):
            parse_questions_xml("<questions><question>")

    def test_empty_document_raises(self):
        with pytest.raises(QuestionImportError):
            parse_questions_xml("<questions></questions>")

    def test_doctype_is_rejected(self):
        xml = '<?xml version="1.0"?><!DOCTYPE questions [<!ENTITY x "y">]><questions></questions>'
        with pytest.raises(QuestionImportError):
            parse_questions_xml(xml)

    def test_text_question_missing_answer_raises(self):
        xml = r"""
        <questions>
          <question type="text" category="Topic">
            <text>Q</text>
          </question>
        </questions>
        """
        with pytest.raises(QuestionImportError):
            parse_questions_xml(xml)
