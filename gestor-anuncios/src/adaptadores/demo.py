"""Adaptador de DEMONSTRAÇÃO: anúncios SIMULADOS de uma loja fictícia de carros.

Nada aqui acessa a internet. As placas, as plataformas ("AutoFeira", "CarroJá",
"Vitrine Motors") e os valores de referência são fictícios. Com a mesma semente,
os dados são sempre os mesmos, o que permite testar e reproduzir a demonstração.

Cada veículo recebe um "perfil" (vende bem, parado, caro, atrai mas não converte,
vendido no meio do período...) que define o ritmo de visualizações e contatos.
Os contadores são acumulados e calculados a partir do tempo desde a publicação,
então coletar em datas diferentes simula a passagem do tempo.
"""
from __future__ import annotations

import math
import random
import string
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from adaptadores.base import AdaptadorPlataforma
from modelos import AnuncioColetado

PLATAFORMAS_DEMO = ("AutoFeira", "CarroJá", "Vitrine Motors")
INICIO_PADRAO = datetime(2026, 9, 1, 9, 0, 0)
ANO_ATUAL = 2026

# (marca, modelo, versão, ano, valor de referência simulado em R$)
CATALOGO = [
    ("Chevrolet", "Onix", "LT 1.0", 2020, 66200), ("Chevrolet", "Onix", "LT 1.0", 2021, 71500),
    ("Chevrolet", "Onix", "Premier 1.0 Turbo", 2022, 89900), ("Chevrolet", "Tracker", "LT 1.0 Turbo", 2021, 98700),
    ("Chevrolet", "S10", "LTZ 2.8 Diesel", 2019, 159800), ("Hyundai", "HB20", "Comfort 1.0", 2019, 59800),
    ("Hyundai", "HB20", "Comfort 1.0", 2020, 63400), ("Hyundai", "HB20", "Platinum 1.0 Turbo", 2022, 84300),
    ("Hyundai", "Creta", "Limited 1.0 Turbo", 2022, 118500), ("Fiat", "Argo", "Drive 1.0", 2021, 64900),
    ("Fiat", "Argo", "Drive 1.0", 2022, 69800), ("Fiat", "Mobi", "Like 1.0", 2020, 45600),
    ("Fiat", "Toro", "Freedom 1.3 Turbo", 2022, 124900), ("Fiat", "Strada", "Volcano 1.3", 2023, 102300),
    ("Volkswagen", "Gol", "1.0", 2019, 46900), ("Volkswagen", "Polo", "Comfortline 200 TSI", 2021, 86500),
    ("Volkswagen", "Polo", "Comfortline 200 TSI", 2022, 92400), ("Volkswagen", "T-Cross", "Highline 250 TSI", 2021, 119800),
    ("Volkswagen", "Nivus", "Highline 200 TSI", 2022, 113700), ("Volkswagen", "Saveiro", "Robust 1.6", 2020, 67900),
    ("Toyota", "Corolla", "XEi 2.0", 2020, 112400), ("Toyota", "Corolla", "XEi 2.0", 2021, 121900),
    ("Toyota", "Yaris", "XL 1.5", 2021, 82600), ("Toyota", "Hilux", "SRV 2.8 Diesel", 2020, 214500),
    ("Honda", "Civic", "EXL 2.0", 2019, 109600), ("Honda", "City", "EXL 1.5", 2022, 104800),
    ("Honda", "HR-V", "EXL 1.8", 2020, 108900), ("Honda", "Fit", "EX 1.5", 2019, 74300),
    ("Jeep", "Renegade", "Longitude 1.8", 2020, 89600), ("Jeep", "Compass", "Longitude 2.0", 2021, 139700),
    ("Jeep", "Compass", "Longitude 1.3 Turbo", 2022, 151300), ("Renault", "Kwid", "Zen 1.0", 2021, 44800),
    ("Renault", "Sandero", "Zen 1.0", 2020, 52700), ("Renault", "Duster", "Iconic 1.3 Turbo", 2022, 106200),
    ("Nissan", "Kicks", "SV 1.6", 2021, 96400), ("Nissan", "Versa", "Advance 1.6", 2022, 93800),
    ("Ford", "Ka", "SE 1.0", 2018, 44200), ("Ford", "EcoSport", "Freestyle 1.5", 2019, 71900),
    ("Ford", "Ranger", "XLT 3.2 Diesel", 2019, 168500), ("Peugeot", "208", "Active 1.6", 2022, 78900),
]

# Quantos veículos de cada perfil (soma = 40).
PERFIS = {
    "bem": 9, "parado": 7, "caro": 5, "nao_converte": 4, "vendido": 4, "divergente": 3, "barato": 3, "novo": 4,
    "pausado": 1,
}

# Ritmo por dia: (visualizações, contatos) somando todas as plataformas.
RITMO = {
    "bem": (22, 0.75), "parado": (5, 0.04), "caro": (16, 0.36), "nao_converte": (42, 0.08),
    "vendido": (26, 0.9), "divergente": (20, 0.6), "barato": (30, 0.9), "novo": (18, 0.25),
    "pausado": (10, 0.2),
}

# O carro de perfil "pausado" tem os anúncios pausados pela loja a partir deste dia.
DIA_PAUSA = 35


@dataclass
class _Veiculo:
    placa: str
    marca: str
    modelo: str
    versao: str
    ano: int
    km: int
    fipe: float
    perfil: str
    publicado_em: datetime
    plataformas: list[str]
    precos: dict[str, float]
    fipe_informada: bool
    vendido_em: Optional[datetime] = None
    pesos: dict[str, float] = field(default_factory=dict)


def _placa(rng: random.Random, usadas: set[str]) -> str:
    while True:
        letras = "".join(rng.choice(string.ascii_uppercase) for _ in range(3))
        meio = rng.choice(string.ascii_uppercase) if rng.random() < 0.75 else str(rng.randint(0, 9))
        placa = f"{letras}{rng.randint(0, 9)}{meio}{rng.randint(0, 99):02d}"
        if placa not in usadas:
            usadas.add(placa)
            return placa


def _arredondar_preco(valor: float) -> float:
    """Preço "de loja": termina em 900 (ex.: 68.900)."""
    return float(max(1000, int(valor // 1000) * 1000 - 100))


def montar_estoque(semente: int = 42, inicio: datetime = INICIO_PADRAO) -> list[_Veiculo]:
    rng = random.Random(semente)
    perfis = [p for p, n in PERFIS.items() for _ in range(n)]
    rng.shuffle(perfis)
    usadas: set[str] = set()
    estoque = []
    for (marca, modelo, versao, ano, fipe), perfil in zip(CATALOGO, perfis):
        idade = max(1, ANO_ATUAL - ano)
        km = int(idade * 15000 * rng.uniform(0.6, 1.3) / 100) * 100

        if perfil == "novo":
            publicado = inicio + timedelta(days=rng.randint(36, 44))
        elif perfil in ("parado", "caro"):
            publicado = inicio - timedelta(days=rng.randint(8, 20))
        else:
            publicado = inicio - timedelta(days=rng.randint(0, 12))

        quantas = 2 if perfil in ("vendido", "divergente") else rng.choice([1, 2, 2, 3])
        plataformas = rng.sample(list(PLATAFORMAS_DEMO), quantas)

        fator = {"caro": rng.uniform(1.24, 1.32), "barato": rng.uniform(0.78, 0.82)}.get(perfil, rng.uniform(0.98, 1.06))
        base = _arredondar_preco(fipe * fator)
        precos = {p: base for p in plataformas}
        if perfil == "divergente":
            precos[plataformas[1]] = _arredondar_preco(base * rng.uniform(1.035, 1.06) + 1000)

        veiculo = _Veiculo(
            placa=_placa(rng, usadas), marca=marca, modelo=modelo, versao=versao, ano=ano, km=km,
            fipe=float(fipe), perfil=perfil, publicado_em=publicado, plataformas=plataformas, precos=precos,
            # Nem toda plataforma informa a FIPE: ~1 em cada 6 carros fica sem referência pronta.
            fipe_informada=rng.random() > 0.17,
            vendido_em=inicio + timedelta(days=rng.randint(18, 30)) if perfil == "vendido" else None,
        )
        pesos = [rng.uniform(0.6, 1.4) for _ in plataformas]
        veiculo.pesos = {p: w / sum(pesos) for p, w in zip(plataformas, pesos)}
        estoque.append(veiculo)
    return estoque


def _acumulado(ritmo_dia: float, dias: float) -> int:
    # Oscilação semanal leve; a derivada fica sempre positiva, então nunca diminui.
    return int(ritmo_dia * (dias + 0.4 * math.sin(dias * 2 * math.pi / 7)))


class AdaptadorDemo(AdaptadorPlataforma):
    def __init__(self, nome: str, estoque: list[_Veiculo], inicio: datetime = INICIO_PADRAO):
        self.nome = nome
        self._estoque = estoque
        self._inicio = inicio

    def coletar(self, agora: datetime) -> list[AnuncioColetado]:
        anuncios = []
        for v in self._estoque:
            if self.nome not in v.plataformas or v.publicado_em > agora:
                continue
            vendido_aqui = v.vendido_em is not None and agora >= v.vendido_em and self.nome == v.plataformas[0]
            fim = v.vendido_em if vendido_aqui else agora
            dias = max(0.0, (fim - v.publicado_em).total_seconds() / 86400)
            visitas_dia, contatos_dia = RITMO[v.perfil]
            peso = v.pesos[self.nome]

            preco = v.precos[self.nome]
            # Os parados tiveram uma pequena redução depois de 3 semanas (insuficiente).
            if v.perfil == "parado" and agora >= self._inicio + timedelta(days=21):
                preco = _arredondar_preco(preco * 0.97)

            anuncios.append(
                AnuncioColetado(
                    plataforma=self.nome,
                    anuncio_id=f"{self.nome[:2].upper()}-{v.placa}",
                    placa=v.placa, marca=v.marca, modelo=v.modelo, versao=v.versao, ano=v.ano, km=v.km,
                    preco=preco, preco_referencia=v.fipe if v.fipe_informada else None,
                    visualizacoes=_acumulado(visitas_dia * peso, dias),
                    contatos=_acumulado(contatos_dia * peso, dias),
                    status="vendido" if vendido_aqui else (
                        "pausado" if v.perfil == "pausado" and agora >= self._inicio + timedelta(days=DIA_PAUSA)
                        else "ativo"
                    ),
                    publicado_em=v.publicado_em,
                    url=f"https://exemplo.invalid/{self.nome.lower().replace(' ', '-')}/{v.placa.lower()}",
                )
            )
        return anuncios


def criar_adaptadores_demo(semente: int = 42, inicio: datetime = INICIO_PADRAO) -> list[AdaptadorDemo]:
    """Um adaptador por plataforma fictícia, todos sobre o mesmo estoque simulado."""
    estoque = montar_estoque(semente, inicio)
    return [AdaptadorDemo(nome, estoque, inicio) for nome in PLATAFORMAS_DEMO]
