"""
Daily Data Pipeline Scheduler

Agenda e executa a ingestão incremental de dados OHLCV e processamento
em horários pré-definidos (ex: 18:00 todos os dias).

Suporta dois modos:
1. Local: Scheduler contínuo com APScheduler
2. EventBridge/Lambda: Recebe eventos do AWS EventBridge
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from datetime import datetime, time
from typing import Any, Dict

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# Importa os módulos de pipeline
sys.path.insert(0, str(Path(__file__).parent.parent))
from data.ingest import main as fetch_data
from features.process import main as process_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("scheduler")


def daily_pipeline(event_source: str = "local", event_data: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Executa o pipeline diário completo:
    1. Ingestão incremental (últimos 7 dias)
    2. Processamento e validação
    
    Args:
        event_source: Origem do evento ('local', 'eventbridge', 'lambda')
        event_data: Dados do evento (opcional)
    
    Returns:
        Dict com status, mensagem e detalhes da execução
    """
    result = {
        "status": "success",
        "event_source": event_source,
        "timestamp": datetime.now().isoformat(),
        "steps": {},
        "message": ""
    }
    
    log.info("=" * 80)
    log.info("INICIANDO PIPELINE DIÁRIO DE COTAÇÕES")
    log.info(f"Origem: {event_source.upper()}")
    if event_data:
        log.info(f"Event Data: {json.dumps(event_data, indent=2, default=str)}")
    log.info("=" * 80)
    
    try:
        # Step 1: Ingestão incremental
        log.info("[1/2] Iniciando ingestão de dados...")
        days_back = 7
        
        # Permite configurar dias_back via evento
        if event_data and "days_back" in event_data:
            days_back = int(event_data["days_back"])
            log.info(f"Usando days_back={days_back} do evento")
        
        fetch_data(mode="incremental", days_back=days_back)
        result["steps"]["fetch"] = {
            "status": "success",
            "days_back": days_back,
            "timestamp": datetime.now().isoformat()
        }
        log.info("[1/2] ✓ Ingestão concluída com sucesso")
        
        # Step 2: Processamento
        log.info("[2/2] Iniciando processamento e validação...")
        process_data()
        result["steps"]["process"] = {
            "status": "success",
            "timestamp": datetime.now().isoformat()
        }
        log.info("[2/2] ✓ Processamento concluído com sucesso")
        
        result["message"] = "Pipeline executado com sucesso"
        log.info("=" * 80)
        log.info("✓ PIPELINE DIÁRIO CONCLUÍDO COM SUCESSO")
        log.info("=" * 80)
        
    except Exception as e:
        result["status"] = "error"
        result["message"] = str(e)
        result["error_details"] = {
            "type": type(e).__name__,
            "message": str(e)
        }
        
        log.error("=" * 80)
        log.error("✗ ERRO NO PIPELINE DIÁRIO")
        log.error("=" * 80)
        log.exception(e)
    
    return result


def start_scheduler(hour: int = 18, minute: int = 0) -> None:
    """
    Inicia o scheduler que executa a pipeline diariamente.
    
    Args:
        hour: Hora do dia (0-23) para executar o pipeline. Default: 18 (6 PM)
        minute: Minuto (0-59). Default: 0
    """
    scheduler = BackgroundScheduler()
    
    # Cria um wrapper que chama daily_pipeline com event_source local
    def scheduled_job():
        daily_pipeline(event_source="local")
    
    # Agenda para executar diariamente na hora especificada
    trigger = CronTrigger(hour=hour, minute=minute)
    scheduler.add_job(
        scheduled_job,
        trigger=trigger,
        id="daily_data_pipeline",
        name="Daily Data Pipeline",
        replace_existing=True,
    )
    
    scheduler.start()
    
    log.info("=" * 80)
    log.info("SCHEDULER INICIADO")
    log.info("=" * 80)
    log.info("Próxima execução agendada para: 18:00 (todos os dias)")
    log.info("Para parar o scheduler, pressione Ctrl+C")
    log.info("=" * 80)
    
    try:
        # Mantém o scheduler rodando
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Encerrando scheduler...")
        scheduler.shutdown()
        log.info("Scheduler encerrado")


def run_once() -> None:
    """Executa o pipeline uma vez imediatamente (útil para testes)."""
    log.info("Executando pipeline uma única vez...")
    result = daily_pipeline(event_source="local")
    log.info(f"Resultado: {json.dumps(result, indent=2, default=str)}")
    return result


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handler AWS Lambda para processar eventos do EventBridge.
    
    Invocado por EventBridge (CloudWatch Events).
    
    Exemplo de evento EventBridge:
    {
        "source": "aws.events",
        "detail-type": "Scheduled Event",
        "detail": {
            "days_back": 7
        },
        "time": "2026-04-19T18:00:00Z"
    }
    
    Args:
        event: Evento do EventBridge
        context: Contexto do Lambda
    
    Returns:
        Resposta JSON com status da execução
    """
    log.info("=" * 80)
    log.info("LAMBDA HANDLER ACIONADO")
    log.info("=" * 80)
    log.info(f"Event: {json.dumps(event, indent=2, default=str)}")
    
    try:
        # Extrai dados do evento
        event_detail = event.get("detail", {})
        
        # Executa pipeline
        result = daily_pipeline(event_source="eventbridge", event_data=event_detail)
        
        # Formata resposta Lambda
        response = {
            "statusCode": 200 if result["status"] == "success" else 400,
            "body": json.dumps(result, default=str)
        }
        
        log.info(f"Lambda response: {response}")
        return response
        
    except Exception as e:
        log.error(f"Lambda execution error: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({
                "status": "error",
                "message": str(e),
                "error_type": type(e).__name__
            })
        }


def eventbridge_event_handler(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handler genérico para eventos do EventBridge (sem contexto Lambda).
    Útil para testes locais de eventos EventBridge.
    
    Args:
        event: Evento do EventBridge
    
    Returns:
        Resultado da execução
    """
    log.info("Processando evento EventBridge")
    log.info(f"Evento: {json.dumps(event, indent=2, default=str)}")
    
    event_detail = event.get("detail", {})
    return daily_pipeline(event_source="eventbridge", event_data=event_detail)


if __name__ == "__main__":
    # Argumentos de linha de comando
    mode = sys.argv[1] if len(sys.argv) > 1 else "scheduler"
    
    if mode == "once":
        # Executa pipeline uma única vez
        result = run_once()
        sys.exit(0 if result["status"] == "success" else 1)
    
    elif mode == "test-event":
        # Testa com um evento EventBridge simulado
        test_event = {
            "source": "aws.events",
            "detail-type": "Scheduled Event",
            "detail": {
                "days_back": 7
            },
            "time": "2026-04-19T18:00:00Z"
        }
        result = eventbridge_event_handler(test_event)
        log.info(f"Event handler result: {json.dumps(result, indent=2, default=str)}")
        sys.exit(0 if result["status"] == "success" else 1)
    
    elif mode == "lambda":
        # Modo Lambda (espera chamadas)
        log.info("Lambda handler em espera...")
        # Em produção, o Lambda runtime chamará lambda_handler automaticamente
        
    else:
        # Modo padrão: scheduler contínuo
        hour = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 18
        minute = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 0
        
        start_scheduler(hour=hour, minute=minute)
