import pytest

from app.services.equation_extractor import EquationExtractor


def test_simple_equation_extraction():
    text = """The harmonic oscillator: m x'' + k x = 0
    Solution: x(t) = A cos(wt + phi), w = sqrt(k/m)
    """
    extractor = EquationExtractor()
    equations = extractor.extract_equations(text)

    assert len(equations) >= 1
    # At least one LaTeX-ish output should contain sqrt
    assert any('sqrt' in eq.latex or '\\sqrt' in eq.latex for eq in equations)
