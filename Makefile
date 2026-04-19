.PHONY: help install fetch process fetch-daily scheduler scheduler-once scheduler-daemon test clean test-event lambda-build lambda-deploy lambda-invoke lambda-logs

help:
	@echo "FIAP Tech Challenge - Fase 5"
	@echo ""
	@echo "Targets disponíveis:"
	@echo ""
	@echo "--- Execução Local ---"
	@echo "  make install           - Instala dependências do projeto"
	@echo "  make fetch             - Busca dados históricos (definidos em model_config.yaml)"
	@echo "  make process           - Processa dados brutos e gera features"
	@echo "  make fetch-daily       - Busca dados incrementais dos últimos 7 dias"
	@echo "  make pipeline          - Executa fetch-daily + process (uma única vez)"
	@echo ""
	@echo "--- Scheduler Local ---"
	@echo "  make scheduler         - Inicia scheduler contínuo (18:00 diários)"
	@echo "  make scheduler-once    - Executa pipeline uma única vez (para testes)"
	@echo "  make scheduler-daemon  - Inicia scheduler em background (nohup)"
	@echo ""
	@echo "--- EventBridge/Lambda ---"
	@echo "  make test-event        - Testa com evento EventBridge simulado"
	@echo "  make lambda-build      - Build do pacote para Lambda"
	@echo "  make lambda-deploy     - Deploy da função Lambda no AWS"
	@echo "  make lambda-invoke     - Invoca função Lambda via CLI"
	@echo "  make lambda-logs       - Mostra logs em tempo real"
	@echo ""
	@echo "--- Testes & Limpeza ---"
	@echo "  make test              - Executa testes unitários"
	@echo "  make clean             - Remove arquivos temporários e cache"

install:
	pip install -e .

fetch:
	python -m src.data.ingest historical

fetch-daily:
	python -m src.data.ingest incremental 7

process:
	python -m src.features.process

pipeline:
	python -m src.data.ingest incremental 7 && python -m src.features.process

scheduler:
	@echo "Iniciando scheduler de pipeline diário (18:00 UTC)..."
	python -m src.data.scheduler

scheduler-once:
	@echo "Executando pipeline uma única vez..."
	python -m src.data.scheduler once

scheduler-daemon:
	@echo "Iniciando scheduler em background..."
	nohup python -m src.data.scheduler > logs/scheduler.log 2>&1 &
	@echo "Scheduler iniciado. Verifique logs/scheduler.log"

test-event:
	@echo "Testando com evento EventBridge simulado..."
	python -m src.data.scheduler test-event

lambda-build:
	@echo "Buildando pacote Lambda..."
	@rm -rf lambda_build lambda_package lambda_function.zip
	@mkdir -p lambda_build
	@cp -r src lambda_build/
	@cp -r configs lambda_build/
	@cp pyproject.toml lambda_build/
	@pip install -r <(grep -v "^#" pyproject.toml | tail -n +1) -t lambda_build/ --quiet
	@cd lambda_build && zip -r ../lambda_function.zip . -q && cd ..
	@du -h lambda_function.zip
	@echo "✓ Lambda package criado: lambda_function.zip"

lambda-deploy: lambda-build
	@echo "Fazendo deploy da função Lambda..."
	@aws lambda update-function-code \
		--function-name daily-data-pipeline \
		--zip-file fileb://lambda_function.zip \
		--region us-east-1
	@echo "✓ Deploy concluído"

lambda-invoke:
	@echo "Invocando função Lambda..."
	@aws lambda invoke \
		--function-name daily-data-pipeline \
		--payload '{"source":"aws.events","detail":{"days_back":7}}' \
		--region us-east-1 \
		response.json
	@cat response.json
	@rm response.json

lambda-logs:
	@aws logs tail /aws/lambda/daily-data-pipeline --follow --region us-east-1

test:
	pytest tests/ -v

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage htmlcov lambda_build lambda_package lambda_function.zip
	@echo "Limpeza concluída"
