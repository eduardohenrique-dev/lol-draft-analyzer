"""Regras do draft competitivo e consistência dos dados de exemplo."""
import unittest
from collections import Counter

import config
from src.mock.mock_data import build_mock_games


class SequenciaDoDraft(unittest.TestCase):
    def test_tem_20_acoes_10_bans_e_10_picks(self):
        tipos = Counter(passo["type"] for passo in config.DRAFT_SEQUENCE)
        self.assertEqual(len(config.DRAFT_SEQUENCE), 20)
        self.assertEqual(tipos["ban"], 10)
        self.assertEqual(tipos["pick"], 10)

    def test_cada_lado_tem_5_bans_e_5_picks(self):
        pares = Counter((p["side"], p["type"]) for p in config.DRAFT_SEQUENCE)
        for lado in ("blue", "red"):
            self.assertEqual(pares[(lado, "ban")], 5)
            self.assertEqual(pares[(lado, "pick")], 5)

    def test_slots_nao_se_repetem_por_lado_e_tipo(self):
        vistos = set()
        for p in config.DRAFT_SEQUENCE:
            chave = (p["side"], p["type"], p["slot"])
            self.assertNotIn(chave, vistos)
            vistos.add(chave)

    def test_pesos_cobrem_as_10_posicoes(self):
        self.assertEqual(set(config.PICK_PRIORITY_WEIGHT), set(range(1, 11)))
        self.assertEqual(set(config.BAN_PRIORITY_WEIGHT), set(range(1, 11)))

    def test_pesos_de_pick_decaem(self):
        pesos = [config.PICK_PRIORITY_WEIGHT[i] for i in range(1, 11)]
        self.assertEqual(pesos, sorted(pesos, reverse=True))


class DadosDeExemplo(unittest.TestCase):
    def test_todo_draft_tem_20_campeoes_distintos(self):
        for jogo in build_mock_games():
            campeoes = [a.champion for a in jogo.actions]
            self.assertEqual(len(campeoes), 20, jogo.game_id)
            self.assertEqual(len(set(campeoes)), 20, f"{jogo.game_id}: campeão repetido")

    def test_as_ligas_existem_na_configuracao(self):
        for jogo in build_mock_games():
            self.assertIn(jogo.league, config.LEAGUE_KEYS)

    def test_a_ordem_das_acoes_segue_a_sequencia_oficial(self):
        esperado = [(p["phase"], p["type"], p["side"], p["slot"]) for p in config.DRAFT_SEQUENCE]
        for jogo in build_mock_games():
            obtido = [(a.phase, a.action_type, a.side, a.slot) for a in jogo.actions]
            self.assertEqual(obtido, esperado, jogo.game_id)


if __name__ == "__main__":
    unittest.main()
