import pytest

from app.services.question_bank.latex_import import LatexParseError, parse_multi_environment


class TestParseMultiEnvironment:
    def test_parses_prompt_and_choices(self):
        latex = r"""
        \begin{multi}{T6}
         Период функции  $\cos\frac{k\pi}{l}x$ при $k=8, \, l=16$ равен
         \item* 4
         \item  верный ответ отсутствует
         \item 2
         \item 8
         \item  1/4
        \end{multi}
        """

        result = parse_multi_environment(latex)

        assert result.latex_id == "T6"
        assert "cos" in result.prompt
        assert result.choices == ["4", "верный ответ отсутствует", "2", "8", "1/4"]
        assert result.correct_indices == [0]

    def test_multiple_correct_choices(self):
        latex = r"""
        \begin{multi}{Q1}
         Какие из чисел четные?
         \item* 2
         \item 3
         \item* 4
         \item 5
        \end{multi}
        """

        result = parse_multi_environment(latex)

        assert result.correct_indices == [0, 2]

    def test_missing_multi_block_raises(self):
        with pytest.raises(LatexParseError):
            parse_multi_environment("just some text, no multi block")

    def test_no_items_raises(self):
        latex = r"\begin{multi}{Q1} just a prompt \end{multi}"
        with pytest.raises(LatexParseError):
            parse_multi_environment(latex)

    def test_no_correct_choice_raises(self):
        latex = r"""
        \begin{multi}{Q1}
         Prompt
         \item A
         \item B
        \end{multi}
        """
        with pytest.raises(LatexParseError):
            parse_multi_environment(latex)

    def test_empty_prompt_raises(self):
        latex = r"""
        \begin{multi}{Q1}
         \item* A
         \item B
        \end{multi}
        """
        with pytest.raises(LatexParseError):
            parse_multi_environment(latex)
