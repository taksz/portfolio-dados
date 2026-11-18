"""Motor de regras: classifica cada veículo do estoque e sugere ajuste de preço.

A unidade é o VEÍCULO (placa), somando os anúncios dele em todas as plataformas.
Visualizações e contatos chegam acumulados; aqui se calcula quanto entrou na
janela recente (padrão: últimos 7 dias).

Situações, da mais urgente para a menos:
    vendido       vendeu em alguma plataforma: remover os anúncios que sobraram
    fora_do_ar    nenhum anúncio ativo, sem registro de venda: confirmar o que houve
    nao_converte  muitas visitas e quase nenhum contato (preço, fotos ou descrição)
    parado        anunciado há muito tempo e quase sem contatos
    preco_alto    bem acima da referência (FIPE ou mediana de carros parecidos)
    divergente    o mesmo carro com preços diferentes entre plataformas
    preco_baixo   bem abaixo da referência (pode estar deixando dinheiro na mesa)
    bem           recebendo contatos com preço dentro da faixa
    novo          anunciado há pouco tempo, ainda sem dados para julgar
    normal        nada a destacar
"""
from __future__ import annotations

import math
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from statistics import median
from typing import Optional, Union

SITUACOES = (
    "vendido", "fora_do_ar", "nao_converte", "parado", "preco_alto", "divergente", "preco_baixo", "bem", "novo", "normal",
)

ROTULOS = {
    "vendido": "Vendido",
    "fora_do_ar": "Fora do ar",
    "parado": "Parado",
    "nao_converte": "Atrai mas não converte",
    "preco_alto": "Preço acima da referência",
    "divergente": "Preço divergente",
    "preco_baixo": "Preço abaixo da referência",
    "bem": "Performando bem",
    "novo": "Novo",
    "normal": "Normal",
}

# Situações em que faz sentido sugerir redução de preço.
PEDEM_REDUCAO = {"parado", "nao_converte", "preco_alto"}

Data = Union[str, datetime]


@dataclass
class Config:
    dias_parado: int = 30          # a partir de quantos dias anunciado pode ser "parado"
    janela_dias: int = 7           # janela para contar visitas e contatos recentes
    contatos_min: int = 2          # contatos na janela para não ser "parado" / ser "bem"
    visitas_altas: int = 150       # visitas na janela consideradas altas
    conversao_baixa: float = 0.01  # contatos/visitas abaixo disso = "não converte"
    acima_ref: float = 0.20        # +20% da referência = preço alto
    abaixo_ref: float = 0.15       # -15% da referência = preço baixo
    divergencia: float = 0.02      # diferença entre plataformas tolerada (2%)
    piso: float = 0.90             # sugestão nunca abaixo de 90% da referência
    km_ano: int = 15000            # km esperada por ano de uso


@dataclass
class Diagnostico:
    placa: str
    situacao: str
    sinais: list[str] = field(default_factory=list)
    sugestao: Optional[float] = None
    referencia: Optional[float] = None
    origem_referencia: Optional[str] = None  # "FIPE" | "mediana" | None
    motivo: str = ""
    preco_atual: Optional[float] = None
    precos: dict[str, float] = field(default_factory=dict)  # preço por plataforma (anúncios ativos)
    dias_anunciado: int = 0
    contatos_janela: int = 0
    visitas_janela: int = 0
    remover_de: list[str] = field(default_factory=list)
    vendido_em: Optional[str] = None


def _dt(valor: Data) -> datetime:
    return valor if isinstance(valor, datetime) else datetime.fromisoformat(valor)


def _referencia_base(veiculo: dict, estoque: list[dict]) -> tuple[Optional[float], Optional[str]]:
    if veiculo.get("preco_referencia"):
        return float(veiculo["preco_referencia"]), "FIPE"
    parecidos = [
        e["preco_atual"] for e in estoque
        if e["placa"] != veiculo["placa"] and e.get("preco_atual")
        and e["marca"] == veiculo["marca"] and e["modelo"] == veiculo["modelo"]
        and abs(int(e["ano"]) - int(veiculo["ano"])) <= 1
    ]
    if len(parecidos) >= 2:
        return float(median(parecidos)), "mediana"
    return None, None


def _ajuste_km(veiculo: dict, agora: datetime, cfg: Config) -> float:
    """Cada 10% de km acima do esperado para a idade tira 1% da referência (e vice-versa), até ±10%."""
    idade = max(1, agora.year - int(veiculo["ano"]))
    esperado = idade * cfg.km_ano
    desvio = (int(veiculo["km"]) - esperado) / esperado
    return max(-0.10, min(0.10, -desvio * 0.10))


def referencia_ajustada(veiculo: dict, estoque: list[dict], agora: datetime, cfg: Config = Config()) -> Optional[float]:
    base, _ = _referencia_base(veiculo, estoque)
    return None if base is None else base * (1 + _ajuste_km(veiculo, agora, cfg))


def _variacao_na_janela(serie: list[dict], campo: str, publicado: datetime, agora: datetime, cfg: Config) -> int:
    """Quanto o contador acumulado `campo` subiu nos últimos `janela_dias`."""
    inicio = agora - timedelta(days=cfg.janela_dias)
    atual = serie[-1][campo]
    anteriores = [s for s in serie if _dt(s["coletado_em"]) <= inicio]
    if anteriores:
        base = anteriores[-1]
        # Se a coleta anterior é mais antiga que a janela, a diferença cobre mais dias: proporcionaliza.
        intervalo = (_dt(serie[-1]["coletado_em"]) - _dt(base["coletado_em"])).total_seconds() / 86400
        fator = min(1.0, cfg.janela_dias / intervalo) if intervalo > 0 else 1.0
        return max(0, int((atual - base[campo]) * fator))
    if publicado >= inicio:
        return atual  # publicado dentro da janela: tudo é recente
    # Sem coleta antiga o bastante: estima pela média diária desde a publicação.
    dias = max(1.0, (_dt(serie[-1]["coletado_em"]) - publicado).total_seconds() / 86400)
    return int(atual * min(1.0, cfg.janela_dias / dias))


def _arredondar(valor: float) -> float:
    return float(math.floor(valor / 100) * 100)


def _sugestao(preco: float, referencia: Optional[float], cfg: Config) -> Optional[float]:
    if referencia:
        alvo = _arredondar(max(min(preco * 0.93, referencia * 1.03), referencia * cfg.piso))
        # O piso é arredondado para cima: a sugestão nunca fica abaixo de 90% da referência.
        alvo = max(alvo, float(math.ceil(referencia * cfg.piso / 100) * 100))
    else:
        alvo = _arredondar(preco * 0.95)
    return alvo if alvo < preco else None


def _reais(valor: float) -> str:
    return "R$ " + f"{valor:,.0f}".replace(",", ".")


def avaliar(
    veiculo: dict, snapshots: list[dict], anuncios: list[dict], estoque: list[dict], agora: datetime,
    cfg: Config = Config(),
) -> Diagnostico:
    placa = veiculo["placa"]
    publicacao = {(a["plataforma"], a["anuncio_id"]): _dt(a["publicado_em"]) for a in anuncios}

    series: dict[tuple, list[dict]] = defaultdict(list)
    for s in sorted(snapshots, key=lambda s: _dt(s["coletado_em"])):
        if _dt(s["coletado_em"]) <= agora:
            series[(s["plataforma"], s["anuncio_id"])].append(s)

    publicados = [publicacao[k] for k in series if k in publicacao] or [agora]
    dias = max(0, (agora - min(publicados)).days)
    ultimos = {k: serie[-1] for k, serie in series.items()}
    precos_ativos = [u["preco"] for u in ultimos.values() if u["status"] == "ativo"]
    ativos: dict[str, float] = {}  # menor preço ativo por plataforma (pode haver anúncio duplicado)
    for (plataforma, _), u in ultimos.items():
        if u["status"] == "ativo":
            ativos[plataforma] = min(u["preco"], ativos.get(plataforma, u["preco"]))
    vendidos = sorted(k[0] for k, u in ultimos.items() if u["status"] == "vendido")

    contatos = visitas = 0
    for k, serie in series.items():
        pub = publicacao.get(k, _dt(serie[0]["coletado_em"]))
        contatos += _variacao_na_janela(serie, "contatos", pub, agora, cfg)
        visitas += _variacao_na_janela(serie, "visualizacoes", pub, agora, cfg)

    ref_base, origem = _referencia_base(veiculo, estoque)
    referencia = None if ref_base is None else ref_base * (1 + _ajuste_km(veiculo, agora, cfg))
    preco = min(ativos.values()) if ativos else None
    d = Diagnostico(
        placa=placa, situacao="normal", referencia=referencia, origem_referencia=origem, preco_atual=preco,
        precos=dict(sorted(ativos.items())), dias_anunciado=dias, contatos_janela=contatos, visitas_janela=visitas,
    )

    if vendidos:
        d.situacao, d.vendido_em = "vendido", vendidos[0]
        d.remover_de = sorted(ativos)
        d.motivo = f"Vendido em {d.vendido_em}." + (
            f" Remover de: {', '.join(d.remover_de)}." if d.remover_de else ""
        )
        return d
    if not ativos:
        d.situacao = "fora_do_ar"
        d.motivo = "Nenhum anúncio ativo e nenhum registro de venda: confirme se o carro foi vendido."
        return d

    detectadas = set()
    motivos = []
    if dias >= cfg.dias_parado and contatos < cfg.contatos_min:
        detectadas.add("parado")
        motivos.append(f"{dias} dias anunciado e {contatos} contato(s) nos últimos {cfg.janela_dias} dias")
    if visitas >= cfg.visitas_altas and contatos / visitas < cfg.conversao_baixa:
        detectadas.add("nao_converte")
        motivos.append(f"{visitas} visitas e só {contatos} contato(s) em {cfg.janela_dias} dias")
    if referencia:
        diferenca = preco / referencia - 1
        if diferenca > cfg.acima_ref:
            detectadas.add("preco_alto")
        elif diferenca < -cfg.abaixo_ref:
            detectadas.add("preco_baixo")
        if diferenca > cfg.acima_ref or diferenca < -cfg.abaixo_ref:
            motivos.append(f"preço {diferenca:+.0%} em relação à referência ({origem}, ajustada pela km)")
    if len(precos_ativos) > 1 and (max(precos_ativos) - preco) / preco > cfg.divergencia:
        detectadas.add("divergente")
        motivos.append("preços diferentes entre plataformas: " + ", ".join(f"{p} {_reais(v)}" for p, v in d.precos.items()))
    if contatos >= cfg.contatos_min and "preco_alto" not in detectadas:
        detectadas.add("bem")
    if dias < cfg.dias_parado:
        detectadas.add("novo")

    ordem = [s for s in SITUACOES if s in detectadas] or ["normal"]
    d.situacao = ordem[0]
    d.sinais = [s for s in ordem[1:] if s not in ("bem", "novo")]

    if PEDEM_REDUCAO & {d.situacao, *d.sinais}:
        d.sugestao = _sugestao(preco, referencia, cfg)
    if d.situacao == "bem":
        motivos.append(f"{contatos} contato(s) nos últimos {cfg.janela_dias} dias")
    elif d.situacao == "novo":
        motivos.append(f"anunciado há {dias} dia(s)")
    texto = "; ".join(motivos) or "nada a destacar"
    d.motivo = texto[0].upper() + texto[1:] + "."
    if d.sugestao:
        d.motivo += f" Sugestão: {_reais(d.sugestao)}."
    return d


def avaliar_todos(conn: sqlite3.Connection, agora: datetime, cfg: Config = Config()) -> list[Diagnostico]:
    """Avalia todo o estoque gravado no banco. Ordena do mais urgente para o menos."""
    import banco

    veiculos = [dict(v) for v in banco.listar_veiculos(conn)]
    snaps_por_placa: dict[str, list[dict]] = defaultdict(list)
    for s in banco.todos_snapshots(conn):
        snaps_por_placa[s["placa"]].append(dict(s))
    anuncios_por_placa: dict[str, list[dict]] = defaultdict(list)
    for a in banco.todos_anuncios(conn):
        anuncios_por_placa[a["placa"]].append(dict(a))

    # Preço atual (menor preço ativo) de cada carro, para a mediana de parecidos.
    estoque = []
    for v in veiculos:
        ultimos = {}
        for s in snaps_por_placa[v["placa"]]:
            if _dt(s["coletado_em"]) <= agora:
                ultimos[(s["plataforma"], s["anuncio_id"])] = s
        ativos = [s["preco"] for s in ultimos.values() if s["status"] == "ativo"]
        estoque.append({**v, "preco_atual": min(ativos) if ativos else None})

    diagnosticos = [
        avaliar(v, snaps_por_placa[v["placa"]], anuncios_por_placa[v["placa"]], estoque, agora, cfg) for v in veiculos
    ]
    return sorted(diagnosticos, key=lambda d: (SITUACOES.index(d.situacao), d.placa))
