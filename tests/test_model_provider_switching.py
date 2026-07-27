# Import necessary libraries
import pytest
from model_provider_switching import main

# Test function for the ollama flag
def test_main_ollama_flag():
    # Mock the argparse behavior to simulate command line arguments
    with pytest.raises(SystemExit) as excinfo:
        main(['--provider', 'ollama', '--cloud-model', 'model1'])
    assert excinfo.value.code == 0

# Test function for the openrouter flag
def test_main_openrouter_flag():
    # Mock the argparse behavior to simulate command line arguments
    with pytest.raises(SystemExit) as excinfo:
        main(['--provider', 'openrouter', '--cloud-model', 'model1'])
    assert excinfo.value.code == 0