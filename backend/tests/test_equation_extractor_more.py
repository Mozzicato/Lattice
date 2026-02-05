from app.services.equation_extractor import EquationExtractor


def test_various_equation_patterns():
    text = """Consider the following:
    F = -kx
    m x'' + k x = 0
    x(t) = A cos(w t + phi)
    w = sqrt(k/m)
    Integral: ∫_0^T f(t) dt
    Sum: ∑_{i=1}^{n} i
    Fraction inline: y = a/b + 1/2
    """
    extractor = EquationExtractor()
    equations = extractor.extract_equations(text)

    latex_list = [e.latex for e in equations]
    assert any('\\sqrt' in l or 'sqrt' in l for l in latex_list)
    assert any('\\sum' in l or 'sum' in l for l in latex_list)
    assert any('\\int' in l or 'int' in l for l in latex_list)
    assert any('\\frac' in l or 'frac' in l for l in latex_list)