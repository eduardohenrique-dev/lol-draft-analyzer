"""
Tema visual da aplicação.

Direção de arte: "war room de transmissão" — fundo de ardósia profunda, lados
azul e vermelho com identidade forte (sem o azul/vermelho genéricos de UI), e
um dourado de destaque reservado APENAS para o vencedor. A ousadia fica
concentrada no header do confronto e no realce do vencedor; o resto é quieto e
disciplinado para o olho seguir o draft de cima para baixo.
"""

# --- Paleta -------------------------------------------------------------- #
BG          = "#0B0E14"   # fundo principal (ardósia quase preta)
PANEL       = "#141A24"   # painéis/cartões
PANEL_HI    = "#1D2530"   # hover / linhas alternadas
BORDER      = "#26303D"
TEXT        = "#E6EDF3"
TEXT_MUTED  = "#8B98A5"

BLUE        = "#3D7BFF"   # lado azul
BLUE_SOFT   = "#16233D"
RED         = "#FF4655"   # lado vermelho
RED_SOFT    = "#3A1620"
GOLD        = "#F0B232"   # destaque do vencedor

SIDE_COLORS = {"blue": BLUE, "red": RED}
SIDE_SOFT   = {"blue": BLUE_SOFT, "red": RED_SOFT}


def stylesheet() -> str:
    """QSS global aplicado ao QApplication."""
    return f"""
    QWidget {{
        background-color: {BG};
        color: {TEXT};
        font-family: "Segoe UI", "Inter", sans-serif;
        font-size: 13px;
    }}
    QFrame#Panel {{
        background-color: {PANEL};
        border: 1px solid {BORDER};
        border-radius: 10px;
    }}
    QLabel#H1 {{ font-size: 22px; font-weight: 800; letter-spacing: 0.5px; }}
    QLabel#H2 {{ font-size: 15px; font-weight: 700; color: {TEXT}; }}
    QLabel#Muted {{ color: {TEXT_MUTED}; }}
    QLabel#PhaseHeader {{
        color: {TEXT_MUTED}; font-size: 11px; font-weight: 700;
        letter-spacing: 2px; padding: 8px 0 2px 0;
    }}

    QTabWidget::pane {{ border: none; }}
    QTabBar::tab {{
        background: transparent; color: {TEXT_MUTED};
        padding: 10px 22px; font-weight: 700; letter-spacing: 1px;
        border-bottom: 2px solid transparent;
    }}
    QTabBar::tab:selected {{ color: {TEXT}; border-bottom: 2px solid {GOLD}; }}

    QComboBox, QDateEdit {{
        background: {PANEL}; border: 1px solid {BORDER};
        border-radius: 6px; padding: 6px 10px; min-height: 20px;
    }}
    QComboBox:hover, QDateEdit:hover {{ border-color: {BLUE}; }}
    QComboBox QAbstractItemView {{
        background: {PANEL}; selection-background-color: {BLUE_SOFT};
        border: 1px solid {BORDER};
    }}

    QTableView {{
        background: {PANEL}; gridline-color: {BORDER};
        border: 1px solid {BORDER}; border-radius: 10px;
        selection-background-color: {BLUE_SOFT}; selection-color: {TEXT};
        alternate-background-color: {PANEL_HI};
    }}
    QHeaderView::section {{
        background: {BG}; color: {TEXT_MUTED};
        padding: 8px; border: none; border-bottom: 2px solid {BORDER};
        font-weight: 700; letter-spacing: 0.5px;
    }}
    QHeaderView::section:hover {{ color: {TEXT}; }}

    QScrollBar:vertical {{ background: {BG}; width: 10px; margin: 0; }}
    QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 5px; min-height: 30px; }}
    QScrollBar::handle:vertical:hover {{ background: {TEXT_MUTED}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
    """
