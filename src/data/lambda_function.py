"""
AWS Lambda Wrapper para Data Pipeline

Este arquivo permite que o scheduler.py seja executado em um Lambda function
disparado por EventBridge.

Configuração AWS:
1. Criar uma função Lambda com Python 3.11+
2. Fazer upload deste arquivo como lambda_function.py
3. Configurar EventBridge para disparar a função em um schedule
"""

import json
import sys
from pathlib import Path

# Configurar path para importar módulos do projeto
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.data.scheduler import lambda_handler as pipeline_handler


def lambda_handler(event, context):
    """
    Entry point da função Lambda.
    
    Configuração do EventBridge no AWS Console:
    
    1. CloudWatch Events → Create Rule
    2. Name: daily-data-pipeline
    3. Schedule: cron(0 18 * * ? *)  # 18:00 UTC todos os dias
    4. Add Target: Lambda function
    5. Select: esta função Lambda
    
    Ou via AWS CLI:
    ```
    aws events put-rule \
        --name daily-data-pipeline \
        --schedule-expression "cron(0 18 * * ? *)" \
        --state ENABLED
    
    aws events put-targets \
        --rule daily-data-pipeline \
        --targets "Id"="1","Arn"="arn:aws:lambda:..."
    ```
    
    Args:
        event: Evento do EventBridge
        context: Contexto Lambda
    
    Returns:
        Response Lambda
    """
    print(f"Event received: {json.dumps(event)}")
    print(f"Context: {context}")
    
    # Chama o handler do pipeline
    response = pipeline_handler(event, context)
    
    print(f"Pipeline response: {json.dumps(response)}")
    return response


if __name__ == "__main__":
    # Para testes locais
    test_event = {
        "source": "aws.events",
        "detail-type": "Scheduled Event",
        "detail": {
            "days_back": 7
        },
        "time": "2026-04-19T18:00:00Z"
    }
    
    class MockContext:
        function_name = "daily-data-pipeline"
        invoked_function_arn = "arn:aws:lambda:us-east-1:123456789:function:daily-data-pipeline"
        memory_limit_in_mb = 128
        aws_request_id = "test-request-id"
    
    result = lambda_handler(test_event, MockContext())
    print(f"Final result: {result}")
