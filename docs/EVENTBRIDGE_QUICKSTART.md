# Quick Start - EventBridge Integration

## 🎯 Objetivo

Integrar o pipeline de dados com AWS EventBridge para execução automática na nuvem.

## ⚡ Quick Start (5 minutos)

### 1. Testar Localmente

```bash
# Simular evento EventBridge
make test-event

# Saída esperada:
# ✓ PIPELINE DIÁRIO CONCLUÍDO COM SUCESSO
```

### 2. Build da Função Lambda

```bash
# Empacotar código + dependências
make lambda-build

# Verifica tamanho do ZIP
ls -lh lambda_function.zip
```

### 3. Fazer Deploy

```bash
# Requisitos:
# - AWS CLI configurado (aws configure)
# - Função Lambda "daily-data-pipeline" já criada
# - Permissões necessárias

make lambda-deploy

# ✓ Deploy concluído
```

### 4. Testar Lambda

```bash
# Invocar função via CLI
make lambda-invoke

# Ver logs em tempo real
make lambda-logs
```

## 📋 Pré-requisitos

### AWS Setup

1. **Criar Função Lambda**
   ```bash
   aws lambda create-function \
       --function-name daily-data-pipeline \
       --runtime python3.11 \
       --role arn:aws:iam::YOUR_ACCOUNT_ID:role/lambda-role \
       --handler lambda_handler.lambda_handler \
       --memory-size 512 \
       --timeout 300
   ```

2. **Criar EventBridge Rule**
   ```bash
   # 18:00 UTC todos os dias
   aws events put-rule \
       --name daily-data-pipeline \
       --schedule-expression "cron(0 18 * * ? *)" \
       --state ENABLED
   ```

3. **Conectar Lambda ao EventBridge**
   ```bash
   aws events put-targets \
       --rule daily-data-pipeline \
       --targets Id=1,Arn=arn:aws:lambda:REGION:ACCOUNT_ID:function:daily-data-pipeline
   
   aws lambda add-permission \
       --function-name daily-data-pipeline \
       --statement-id AllowEventBridgeInvoke \
       --action lambda:InvokeFunction \
       --principal events.amazonaws.com
   ```

## 🔍 Monitoração

### CloudWatch Logs
```bash
# Logs em tempo real
aws logs tail /aws/lambda/daily-data-pipeline --follow
```

### Configurar Alertas
```bash
# Enviar email quando falhar
aws cloudwatch put-metric-alarm \
    --alarm-name daily-data-pipeline-failures \
    --metric-name Errors \
    --namespace AWS/Lambda \
    --statistic Sum \
    --threshold 1 \
    --alarm-actions arn:aws:sns:REGION:ACCOUNT_ID:AlertTopic
```

## 💰 Custos Estimados

| Serviço | Uso/Mês | Custo |
|---------|---------|-------|
| Lambda | 720 invocações × 300s | $15.30 |
| EventBridge | 720 eventos | $0.36 |
| CloudWatch Logs | ~100MB | $5.00 |
| **Total** | | **~$20.66** |

## 🧪 Testes

### Teste Local de Evento
```bash
python -m src.data.scheduler test-event
```

### Teste Completo
```bash
# Executar suite de testes
pytest tests/test_eventbridge.py -v
```

### Simular Execução Lambda
```bash
# Chamar função Lambda
make lambda-invoke
```

## 📝 Arquivos Principais

| Arquivo | Descrição |
|---------|-----------|
| `src/data/scheduler.py` | Logic principal com `lambda_handler()` |
| `src/data/lambda_function.py` | Entry point do Lambda |
| `src/data/ingest.py` | Busca incremental de dados |
| `src/features/process.py` | Processamento e validação |

## 🚀 Deployment Options

### Option A: Manual
```bash
make lambda-build
make lambda-deploy
```

### Option B: CI/CD (GitHub Actions)
```yaml
# .github/workflows/deploy-lambda.yml
- name: Deploy to Lambda
  run: |
    make lambda-build
    make lambda-deploy
```

### Option C: Infrastructure as Code
```bash
# CloudFormation / Terraform
terraform apply
```

## ❓ FAQ

**P: Qual é a diferença entre scheduler local e EventBridge?**
A: 
- Local: Roda na máquina/servidor. Custos: 0. Setup: Simples.
- EventBridge: Roda na AWS. Custos: ~$20/mês. Setup: Complexo. Escalabilidade: Infinita.

**P: Posso alterar o horário de execução?**
R: Sim, via EventBridge rule:
```bash
aws events put-rule \
    --name daily-data-pipeline \
    --schedule-expression "cron(0 15 * * ? *)"  # 15:00 UTC
```

**P: Como debug um erro na Lambda?**
R: Ver CloudWatch logs:
```bash
make lambda-logs
```

**P: Posso testar sem fazer deploy?**
R: Sim:
```bash
make test-event
```

## 🔗 Referências

- [AWS_EVENTBRIDGE_SETUP.md](AWS_EVENTBRIDGE_SETUP.md) - Setup detalhado
- [DATA_PIPELINE.md](DATA_PIPELINE.md) - Documentação completa
- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [EventBridge Documentation](https://docs.aws.amazon.com/eventbridge/)

## 📞 Suporte

Para problemas:
1. Verificar logs: `make lambda-logs`
2. Testar localmente: `make test-event`
3. Validar EventBridge rule: console.aws.amazon.com/events
4. Verificar IAM permissions
