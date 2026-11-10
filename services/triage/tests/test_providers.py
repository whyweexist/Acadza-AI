"""Provider-contract tests included for later execution; not run in this handoff."""
import pytest
from pydantic import ValidationError
from app.core.providers import (
    ActiveProvider, ProviderUpdate, choose_provider,
    clear_provider_override, current_provider, MODEL_DEFAULTS,
)


def test_provider_closed_enum():
    with pytest.raises(ValidationError):
        ProviderUpdate(provider='unknown', api_key='secret', cheap_model='fast', strong_model='strong')


def test_provider_key_never_serialized():
    p=ActiveProvider('gemini','highly-secret','https://generativelanguage.googleapis.com/v1beta/openai','gemini-2.5-flash','gemini-2.5-pro','session')
    assert 'highly-secret' not in str(p.public())
    assert p.public()['configured'] is True


def test_in_memory_provider_switch():
    try:
        updated=choose_provider(ProviderUpdate(provider='openrouter',api_key='temporary-example-secret',cheap_model='google/gemini-2.5-flash',strong_model='google/gemini-2.5-pro'))
        assert updated['provider']=='openrouter'
        assert current_provider().api_key=='temporary-example-secret'
        assert 'api_key' not in updated
        assert 'temporary-example-secret' not in str(updated)
    finally:
        clear_provider_override()


def test_reject_missing_credential(monkeypatch):
    import app.core.providers as module
    class NoKeys:
        llm_provider='gemini'
        openai_api_key=''
        gemini_api_key=''
        openrouter_api_key=''
        openai_base_url='https://api.openai.com/v1'
        llm_cheap_model=''
        llm_strong_model=''
    monkeypatch.setattr(module, 'settings', lambda:NoKeys())
    try:
        with pytest.raises(ValueError,match='API key'):
            choose_provider(ProviderUpdate(provider='gemini',cheap_model='gemini-2.5-flash',strong_model='gemini-2.5-pro'))
    finally:
        clear_provider_override()
