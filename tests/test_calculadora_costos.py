import pytest
import json
import os
import sys

# Afegir el directori pare al path per importar els mòduls
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import CalculadoraCostos


class TestCalculadoraCostos:
    """Tests per a la classe CalculadoraCostos."""

    def test_registrar_transaccio_crea_fitxer(self, temp_dir):
        """Verifica que registrar una transacció crea el fitxer d'historial."""
        os.chdir(temp_dir)
        calc = CalculadoraCostos()

        calc.registrar_transaccio("gpt-4o-mini", 100, 50, 0.000045)

        assert os.path.exists(calc.fitxer_historial)

    def test_registrar_transaccio_guarda_dades_correctes(self, temp_dir):
        """Verifica que les dades es guarden correctament."""
        os.chdir(temp_dir)
        calc = CalculadoraCostos()

        calc.registrar_transaccio("gpt-4o-mini", 1000, 500, 0.00045)

        historial = calc.carregar_historial()
        assert len(historial) == 1
        assert historial[0]["model"] == "gpt-4o-mini"
        assert historial[0]["tokens_input"] == 1000
        assert historial[0]["tokens_output"] == 500
        assert historial[0]["cost_usd"] == 0.00045

    def test_multiples_transaccions(self, temp_dir):
        """Verifica que es poden registrar múltiples transaccions."""
        os.chdir(temp_dir)
        calc = CalculadoraCostos()

        calc.registrar_transaccio("gpt-4o-mini", 100, 50, 0.00001)
        calc.registrar_transaccio("gpt-4o-mini", 200, 100, 0.00002)
        calc.registrar_transaccio("gpt-4o-mini", 300, 150, 0.00003)

        historial = calc.carregar_historial()
        assert len(historial) == 3

    def test_carregar_historial_buit(self, temp_dir):
        """Verifica que carregar un historial inexistent retorna llista buida."""
        os.chdir(temp_dir)
        calc = CalculadoraCostos()

        historial = calc.carregar_historial()
        assert historial == []

    def test_transaccio_inclou_data(self, temp_dir):
        """Verifica que cada transacció inclou la data."""
        os.chdir(temp_dir)
        calc = CalculadoraCostos()

        calc.registrar_transaccio("gpt-4o-mini", 100, 50, 0.00001)

        historial = calc.carregar_historial()
        assert "data" in historial[0]
        # Format: YYYY-MM-DD HH:MM:SS
        assert len(historial[0]["data"]) == 19


class TestCalculsCost:
    """Tests per verificar els càlculs de cost."""

    def test_calcul_cost_gpt4o_mini(self):
        """Verifica el càlcul de cost per gpt-4o-mini."""
        # Preus: input $0.15/1M, output $0.60/1M
        tokens_in = 1000
        tokens_out = 500

        cost_esperat = (tokens_in * 0.15 / 1e6) + (tokens_out * 0.60 / 1e6)
        # cost_esperat = 0.00015 + 0.0003 = 0.00045

        assert abs(cost_esperat - 0.00045) < 0.0000001

    def test_calcul_cost_gran_volum(self):
        """Verifica el càlcul amb un volum gran de tokens."""
        # 1 milió de tokens d'entrada, 500k de sortida
        tokens_in = 1_000_000
        tokens_out = 500_000

        cost_esperat = (tokens_in * 0.15 / 1e6) + (tokens_out * 0.60 / 1e6)
        # cost_esperat = 0.15 + 0.30 = 0.45 USD

        assert abs(cost_esperat - 0.45) < 0.0001
