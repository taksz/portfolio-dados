"""Modo automático: repete a coleta em intervalo fixo usando a biblioteca `schedule`."""
from __future__ import annotations

import logging
import time
from typing import Callable, Optional

import schedule

log = logging.getLogger("rastreador")


def rodar(
    tarefa: Callable[[], object],
    intervalo_segundos: float,
    execucoes: Optional[int] = None,
    dormir: Callable[[float], None] = time.sleep,
) -> int:
    """Executa `tarefa` agora e depois a cada `intervalo_segundos`.

    `execucoes` limita o total (útil em testes/demonstrações); com None roda até Ctrl+C.
    Retorna quantas execuções foram feitas.
    """
    agendador = schedule.Scheduler()
    feitas = 0

    def disparo() -> None:
        nonlocal feitas
        tarefa()
        feitas += 1

    agendador.every(intervalo_segundos).seconds.do(disparo)
    log.info("Agendador iniciado: coleta a cada %g segundo(s). Ctrl+C para parar.", intervalo_segundos)
    disparo()
    try:
        while execucoes is None or feitas < execucoes:
            dormir(max(0.1, min(agendador.idle_seconds or 1, 30)))
            agendador.run_pending()
    except KeyboardInterrupt:
        log.info("Agendador interrompido pelo usuário.")
    return feitas
