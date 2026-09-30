"""Motor de estatísticas: o Prio Score é recalculado à mão e comparado."""
import tempfile
import unittest
from pathlib import Path

import config
from src.backend.database import Database
from src.backend.stats_engine import StatsEngine
from src.mock.mock_data import build_mock_games


class MotorDeEstatisticas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pasta = tempfile.TemporaryDirectory()
        cls.db = Database(Path(cls.pasta.name) / "teste.sqlite3")
        cls.jogos = build_mock_games()
        cls.db.save_games(cls.jogos)
        cls.engine = StatsEngine(cls.db)

    @classmethod
    def tearDownClass(cls):
        cls.pasta.cleanup()

    def test_salvou_todos_os_jogos(self):
        self.assertEqual(self.db.count_games(), len(self.jogos))

    def test_picks_e_bans_somam_o_esperado(self):
        tabela = self.engine.compute()
        self.assertEqual(int(tabela["picks"].sum()), 10 * len(self.jogos))
        self.assertEqual(int(tabela["bans"].sum()), 10 * len(self.jogos))

    def test_prio_score_confere_com_a_conta_feita_a_mao(self):
        tabela = self.engine.compute().set_index("champion")
        bruto: dict[str, float] = {}
        for jogo in self.jogos:
            for a in jogo.actions:
                pesos = config.PICK_PRIORITY_WEIGHT if a.action_type == "pick" else config.BAN_PRIORITY_WEIGHT
                bruto[a.champion] = bruto.get(a.champion, 0.0) + pesos[a.global_order]
        for campeao, soma in bruto.items():
            esperado = 100 * soma / len(self.jogos)
            # o motor arredonda em 1 casa decimal: o erro máximo é 0,05
            self.assertAlmostEqual(tabela.loc[campeao, "prio_score"], esperado, delta=0.051, msg=campeao)

    def test_presenca_e_picks_mais_bans_sobre_o_total(self):
        tabela = self.engine.compute()
        for _, linha in tabela.iterrows():
            esperado = (linha["picks"] + linha["bans"]) / len(self.jogos) * 100
            self.assertAlmostEqual(linha["presence_pct"], esperado, delta=0.051, msg=linha["champion"])

    def test_filtro_por_liga_considera_so_os_jogos_dela(self):
        da_liga = [j for j in self.jogos if j.league == "LCK"]
        tabela = self.engine.compute(leagues=["LCK"])
        self.assertEqual(int(tabela["picks"].sum()), 10 * len(da_liga))

    def test_win_rate_so_conta_jogos_em_que_o_campeao_foi_escolhido(self):
        tabela = self.engine.compute()
        for _, linha in tabela.iterrows():
            if linha["picks"] == 0:
                self.assertEqual(linha["win_rate_pct"], 0.0)
            else:
                self.assertEqual(linha["wins"] + linha["losses"], linha["picks"])

    def test_banco_vazio_devolve_tabela_vazia(self):
        with tempfile.TemporaryDirectory() as pasta:
            vazio = StatsEngine(Database(Path(pasta) / "vazio.sqlite3"))
            self.assertTrue(vazio.compute().empty)


if __name__ == "__main__":
    unittest.main()
