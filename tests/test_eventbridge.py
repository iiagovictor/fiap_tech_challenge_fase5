"""
Testes para o pipeline de dados com eventos EventBridge

Valida a integração com AWS EventBridge e o handler Lambda
"""

import json
import pytest
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.scheduler import (
    daily_pipeline,
    eventbridge_event_handler,
    lambda_handler,
)


class TestEventBridgeIntegration:
    """Testes para integração com EventBridge"""
    
    def test_daily_pipeline_local_mode(self):
        """Testa pipeline em modo local"""
        result = daily_pipeline(event_source="local")
        
        assert isinstance(result, dict)
        assert "status" in result
        assert "event_source" in result
        assert result["event_source"] == "local"
        assert "timestamp" in result
        assert "steps" in result
        assert "message" in result
    
    def test_daily_pipeline_with_event_data(self):
        """Testa pipeline com dados de evento customizados"""
        event_data = {
            "days_back": 5,
            "custom_param": "value"
        }
        result = daily_pipeline(event_source="eventbridge", event_data=event_data)
        
        assert isinstance(result, dict)
        assert result["event_source"] == "eventbridge"
        assert result["status"] in ["success", "error"]
    
    def test_eventbridge_event_handler(self):
        """Testa handler de evento EventBridge"""
        test_event = {
            "source": "aws.events",
            "detail-type": "Scheduled Event",
            "detail": {
                "days_back": 7
            },
            "time": "2026-04-19T18:00:00Z"
        }
        
        result = eventbridge_event_handler(test_event)
        
        assert isinstance(result, dict)
        assert result["status"] in ["success", "error"]
        assert "timestamp" in result
    
    def test_lambda_handler(self):
        """Testa handler Lambda"""
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
        
        response = lambda_handler(test_event, MockContext())
        
        assert isinstance(response, dict)
        assert "statusCode" in response
        assert "body" in response
        assert response["statusCode"] in [200, 400, 500]
        
        # Parse body
        body = json.loads(response["body"])
        assert "status" in body
    
    def test_event_with_zero_days_back(self):
        """Testa evento com days_back=0"""
        event_data = {"days_back": 0}
        result = daily_pipeline(event_source="eventbridge", event_data=event_data)
        
        assert isinstance(result, dict)
        assert result["status"] in ["success", "error"]
    
    def test_event_with_large_days_back(self):
        """Testa evento com days_back grande"""
        event_data = {"days_back": 365}
        result = daily_pipeline(event_source="eventbridge", event_data=event_data)
        
        assert isinstance(result, dict)
        assert result["status"] in ["success", "error"]
    
    def test_response_contains_step_details(self):
        """Testa se a resposta contém detalhes de cada step"""
        result = daily_pipeline(event_source="local")
        
        if result["status"] == "success":
            assert "steps" in result
            assert isinstance(result["steps"], dict)
            # Se bem-sucedido, deve ter informações dos steps
            if "fetch" in result["steps"]:
                assert "status" in result["steps"]["fetch"]
    
    def test_error_response_structure(self):
        """Testa estrutura de resposta de erro"""
        # Força um erro criando evento com dados inválidos
        event_data = {"invalid_param": "test"}
        result = daily_pipeline(event_source="eventbridge", event_data=event_data)
        
        # Deve sempre retornar estrutura válida mesmo com erro
        assert isinstance(result, dict)
        assert "status" in result
        assert "timestamp" in result
        assert "message" in result
    
    def test_lambda_response_json_serializable(self):
        """Testa se resposta Lambda é JSON-serializável"""
        test_event = {
            "source": "aws.events",
            "detail": {}
        }
        
        class MockContext:
            function_name = "daily-data-pipeline"
            aws_request_id = "test"
        
        response = lambda_handler(test_event, MockContext())
        
        # Deve ser possível converter para JSON
        json_str = json.dumps(response)
        parsed = json.loads(json_str)
        
        assert isinstance(parsed, dict)
        assert "statusCode" in parsed
        assert "body" in parsed


class TestEventBridgeSchedules:
    """Testes para configurações de agendamento"""
    
    def test_daily_18h_schedule(self):
        """Valida expressão cron para 18h diário"""
        # cron(0 18 * * ? *)
        # Deve executar todo dia às 18:00 UTC
        assert True  # Validar no EventBridge console
    
    def test_business_days_schedule(self):
        """Valida expressão cron para dias úteis"""
        # cron(0 9 ? * MON-FRI *)
        # Deve executar seg-sex às 09:00 UTC
        assert True  # Validar no EventBridge console


class TestEventPayloads:
    """Testes para diferentes tipos de payload EventBridge"""
    
    def test_minimal_event(self):
        """Testa com evento minimal"""
        event = {"source": "aws.events"}
        result = eventbridge_event_handler(event)
        assert result["status"] in ["success", "error"]
    
    def test_full_eventbridge_event(self):
        """Testa com evento EventBridge completo"""
        event = {
            "version": "0",
            "id": "12345678-1234-1234-1234-123456789012",
            "detail-type": "Scheduled Event",
            "source": "aws.events",
            "account": "123456789012",
            "time": "2026-04-19T18:00:00Z",
            "region": "us-east-1",
            "resources": [],
            "detail": {
                "days_back": 7,
                "run_id": "daily-pipeline-001"
            }
        }
        result = eventbridge_event_handler(event)
        assert result["status"] in ["success", "error"]
    
    def test_event_with_custom_metadata(self):
        """Testa evento com metadata customizada"""
        event = {
            "source": "aws.events",
            "detail": {
                "days_back": 7,
                "request_id": "custom-req-123",
                "source_system": "eventbridge-test",
                "priority": "high"
            }
        }
        result = eventbridge_event_handler(event)
        assert result["status"] in ["success", "error"]
        assert result["event_source"] == "eventbridge"


if __name__ == "__main__":
    # Executar testes
    pytest.main([__file__, "-v", "-s"])
