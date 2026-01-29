import pytest
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import GestorConfiguracio


class TestGestorConfiguracio:
    """Tests per a la classe GestorConfiguracio."""

    def test_carregar_config_sense_fitxer(self, mock_env):
        """Verifica que sense config.json retorna configuració per defecte."""
        config = GestorConfiguracio.carregar_config()

        assert "api_key" in config
        assert config["api_key"] == "test-api-key-12345"

    def test_carregar_config_amb_fitxer(self, mock_env):
        """Verifica que carrega correctament des de config.json."""
        config_data = {"custom_setting": "value123"}
        with open("config.json", "w") as f:
            json.dump(config_data, f)

        config = GestorConfiguracio.carregar_config()

        assert config["custom_setting"] == "value123"

    def test_desar_config(self, mock_env):
        """Verifica que es pot desar la configuració."""
        config_data = {"api_key": "nova-clau", "idioma": "cat"}

        GestorConfiguracio.desar_config(config_data)

        assert os.path.exists("config.json")
        with open("config.json", "r") as f:
            saved = json.load(f)
        assert saved["idioma"] == "cat"

    def test_enable_sound_per_defecte(self, mock_env):
        """Verifica que enable_sound es configura des de .env."""
        config = GestorConfiguracio.carregar_config()

        # mock_env configura ENABLE_SOUND=FALSE
        assert config["enable_sound"] == False

    def test_api_key_prioritat_config_json(self, mock_env):
        """Verifica que config.json té prioritat sobre .env per api_key."""
        config_data = {"api_key": "clau-del-json"}
        with open("config.json", "w") as f:
            json.dump(config_data, f)

        config = GestorConfiguracio.carregar_config()

        assert config["api_key"] == "clau-del-json"

    def test_config_json_encoding_utf8(self, mock_env):
        """Verifica que es guarda amb encoding UTF-8 per caràcters catalans."""
        config_data = {"descripció": "Configuració amb accents àéíóú"}

        GestorConfiguracio.desar_config(config_data)

        with open("config.json", "r", encoding="utf-8") as f:
            saved = json.load(f)
        assert "àéíóú" in saved["descripció"]
