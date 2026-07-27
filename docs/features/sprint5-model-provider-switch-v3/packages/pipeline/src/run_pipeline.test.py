# packages/pipeline/src/run_pipeline.test.py
import pytest
from run_pipeline import main

def test_provider_ollama(capsys):
    main(provider='ollama')
    assert 'Using Ollama model' in capsys.readouterr().out

def test_provider_openrouter(capsys):
    main(provider='openrouter')
    assert 'Using OpenRouter model' in capsys.readouterr().out

def test_no_provider(capsys):
    main()
    assert 'No provider specified or invalid provider' in capsys.readouterr().out