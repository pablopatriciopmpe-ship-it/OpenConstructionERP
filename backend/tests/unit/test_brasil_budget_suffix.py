from types import SimpleNamespace

from app.core.demo_projects import _seed_text


def test_brasil_generates_localized_budget_suffix(monkeypatch):
    monkeypatch.setenv('OE_PRODUCT_DEFAULTS', 'brasil')
    assert _seed_text(SimpleNamespace(locale='en'), 'budget_suffix') == '- Orçamento-base'


def test_other_profile_preserves_original_wording(monkeypatch):
    monkeypatch.setenv('OE_PRODUCT_DEFAULTS', 'off')
    assert _seed_text(SimpleNamespace(locale='en'), 'budget_suffix') == '- Budget'
