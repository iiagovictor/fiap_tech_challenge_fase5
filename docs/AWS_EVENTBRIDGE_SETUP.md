# AWS EventBridge Integration Guide

## Visão Geral

O pipeline de dados pode ser executado através do AWS EventBridge, que dispara a função Lambda em horários agendados ou através de eventos customizados.

## Arquitetura

```
AWS EventBridge (CloudWatch Events)
         ↓ (trigger scheduled)
   AWS Lambda Function
         ↓
   data/scheduler.py → lambda_handler()
         ↓
   ingest.py + process.py
         ↓
   S3 / EBS (data/raw, data/processed)
```

## Pré-requisitos

- AWS Account com permissões para Lambda, EventBridge e CloudWatch
- AWS CLI configurado
- Python 3.11+
- Docker (para build de dependências)

## 1. Preparar o Código

### 1.1 Estrutura de Diretórios para Deploy

```bash
# Criar diretório de build
mkdir -p lambda_package
cd lambda_package

# Copiar o código do projeto
cp -r ../src src
cp -r ../configs configs
cp pyproject.toml .

# Instalar dependências
pip install -r requirements.txt -t .

# Adicionar o lambda_function.py no diretório raiz
cp src/data/lambda_function.py lambda_handler.py
```

### 1.2 Arquivo requirements.txt

```
yfinance>=0.2.40
pandas>=2.1.0
pyarrow>=15.0.0
pandera>=0.20.0
pyyaml>=6.0.1
apscheduler>=3.10.0
boto3>=1.34.0
```

### 1.3 Build do ZIP para Lambda

```bash
# Compactar o pacote
cd lambda_package
zip -r ../lambda_function.zip . -x "*.git*" "*.pyc" "__pycache__/*"
cd ..

# Verificar tamanho (deve ser < 50MB para upload direto)
ls -lh lambda_function.zip
```

## 2. Criar a Função Lambda

### 2.1 Via AWS Console

1. Acessar **Lambda** → **Create function**
2. Configuração:
   - **Function name**: `daily-data-pipeline`
   - **Runtime**: Python 3.11
   - **Architecture**: x86_64 ou ARM64
   - **Role**: Criar nova role com permissões abaixo

3. Permissions (criar inline policy):
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::your-bucket-name/*",
                "arn:aws:s3:::your-bucket-name"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:*:*:*"
        }
    ]
}
```

4. Upload do código:
   - Ir para **Code** → **Upload from** → **ZIP file**
   - Selecionar `lambda_function.zip`

5. Configurações:
   - **Memory**: 512 MB (mínimo recomendado)
   - **Timeout**: 5 minutos (300 segundos)
   - **Ephemeral storage**: 10 GB (para downloads de dados)

### 2.2 Via AWS CLI

```bash
# Criar função Lambda
aws lambda create-function \
    --function-name daily-data-pipeline \
    --runtime python3.11 \
    --role arn:aws:iam::YOUR_ACCOUNT_ID:role/lambda-role \
    --handler lambda_handler.lambda_handler \
    --zip-file fileb://lambda_function.zip \
    --timeout 300 \
    --memory-size 512 \
    --ephemeral-storage Size=10240

# Atualizar código após mudanças
aws lambda update-function-code \
    --function-name daily-data-pipeline \
    --zip-file fileb://lambda_function.zip
```

### 2.3 Via CloudFormation

```yaml
Resources:
  DataPipelineFunction:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: daily-data-pipeline
      Runtime: python3.11
      Handler: lambda_handler.lambda_handler
      Code:
        S3Bucket: your-artifact-bucket
        S3Key: lambda_function.zip
      Timeout: 300
      MemorySize: 512
      EphemeralStorage:
        Size: 10240
      Role: !GetAtt LambdaExecutionRole.Arn

  LambdaExecutionRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: lambda.amazonaws.com
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
      Policies:
        - PolicyName: S3Access
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action: s3:*
                Resource:
                  - !Sub 'arn:aws:s3:::${DataBucket}'
                  - !Sub 'arn:aws:s3:::${DataBucket}/*'

  DataBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: fiap-data-bucket
```

## 3. Configurar EventBridge

### 3.1 Criar Rule de Schedule via Console

1. Acessar **EventBridge** → **Rules** → **Create rule**
2. Configuração:
   - **Name**: `daily-data-pipeline`
   - **Description**: Executa pipeline de dados diariamente
   - **Rule type**: Schedule
   - **Schedule pattern**: `cron(0 18 * * ? *)` (18:00 UTC todos os dias)

3. Select targets:
   - **Target type**: AWS service
   - **AWS service**: Lambda function
   - **Function**: daily-data-pipeline
   - **Dead letter queue**: (opcional) SQS queue

4. Criar rule

### 3.2 Criar Rule via AWS CLI

```bash
# Criar EventBridge rule
aws events put-rule \
    --name daily-data-pipeline \
    --description "Daily data pipeline execution" \
    --schedule-expression "cron(0 18 * * ? *)" \
    --state ENABLED \
    --region us-east-1

# Adicionar Lambda como target
aws events put-targets \
    --rule daily-data-pipeline \
    --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:YOUR_ACCOUNT_ID:function:daily-data-pipeline" \
    --region us-east-1

# Dar permissão ao EventBridge de invocar Lambda
aws lambda add-permission \
    --function-name daily-data-pipeline \
    --statement-id AllowExecutionFromEventBridge \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com \
    --source-arn arn:aws:events:us-east-1:YOUR_ACCOUNT_ID:rule/daily-data-pipeline
```

### 3.3 Horários Suportados (Cron Expression)

```
# Sintaxe: cron(minute hour day month ? day-of-week)

# Exemplos:
cron(0 18 * * ? *)              # 18:00 UTC todos os dias
cron(0 9 * * MON-FRI ? *)       # 09:00 UTC de seg-sex (segunda-feira)
cron(0 0 1 * ? *)               # 00:00 UTC no 1º dia do mês
cron(0 */6 * * ? *)             # A cada 6 horas
cron(0 18,22 * * ? *)           # 18:00 e 22:00 UTC diariamente

# Timezones
# EventBridge usa UTC por padrão
# Para timezone local, usar: cron(0 22 * * ? *) em America/Sao_Paulo = 19:00 BRT
```

## 4. Monitorar Execuções

### 4.1 CloudWatch Logs

```bash
# Ver logs da função
aws logs tail /aws/lambda/daily-data-pipeline --follow

# Ver eventos do EventBridge
aws logs tail /aws/events/daily-data-pipeline --follow
```

### 4.2 Console AWS

1. Lambda → Functions → daily-data-pipeline
2. Monitor → View logs in CloudWatch
3. Ver detalhes de cada invocação

## 5. Testes

### 5.1 Teste Local

```bash
# Usar modo test-event do scheduler
python -m src.data.scheduler test-event
```

### 5.2 Teste Lambda via CLI

```bash
# Invocar função Lambda
aws lambda invoke \
    --function-name daily-data-pipeline \
    --payload '{"source":"aws.events","detail":{"days_back":7}}' \
    response.json

# Ver resposta
cat response.json
```

### 5.3 Teste EventBridge

```bash
# Simular evento
aws events put-events \
    --entries '[
        {
            "Source": "aws.events",
            "DetailType": "Scheduled Event",
            "Detail": "{\"days_back\": 7}",
            "Resources": []
        }
    ]'
```

## 6. Tratamento de Erros

### 6.1 Configurar Dead Letter Queue (DLQ)

```bash
# Criar SQS queue para DLQ
aws sqs create-queue --queue-name daily-data-pipeline-dlq

# Adicionar DLQ ao EventBridge target
aws events put-targets \
    --rule daily-data-pipeline \
    --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:YOUR_ACCOUNT_ID:function:daily-data-pipeline","DeadLetterConfig"={"Arn":"arn:aws:sqs:us-east-1:YOUR_ACCOUNT_ID:daily-data-pipeline-dlq"}
```

### 6.2 Alertas CloudWatch

```bash
# Criar alarme para falhas de Lambda
aws cloudwatch put-metric-alarm \
    --alarm-name daily-data-pipeline-failures \
    --alarm-description "Alert on pipeline failures" \
    --metric-name Errors \
    --namespace AWS/Lambda \
    --statistic Sum \
    --period 300 \
    --evaluation-periods 1 \
    --threshold 1 \
    --comparison-operator GreaterThanOrEqualToThreshold \
    --dimensions Name=FunctionName,Value=daily-data-pipeline \
    --alarm-actions arn:aws:sns:us-east-1:YOUR_ACCOUNT_ID:AlertTopic
```

## 7. Variáveis de Ambiente Lambda

```bash
aws lambda update-function-configuration \
    --function-name daily-data-pipeline \
    --environment "Variables={
        PYTHONUNBUFFERED=1,
        LOG_LEVEL=INFO,
        DAYS_BACK=7,
        AWS_REGION=us-east-1
    }"
```

## 8. Estrutura de Resposta

### Sucesso

```json
{
    "statusCode": 200,
    "body": {
        "status": "success",
        "event_source": "eventbridge",
        "timestamp": "2026-04-19T18:00:05.123456",
        "steps": {
            "fetch": {
                "status": "success",
                "days_back": 7,
                "timestamp": "2026-04-19T18:00:01.123456"
            },
            "process": {
                "status": "success",
                "timestamp": "2026-04-19T18:00:04.123456"
            }
        },
        "message": "Pipeline executado com sucesso"
    }
}
```

### Erro

```json
{
    "statusCode": 500,
    "body": {
        "status": "error",
        "message": "Descrição do erro",
        "error_type": "RuntimeError"
    }
}
```

## 9. Costs

Estimativa mensal:

| Serviço | Uso | Custo |
|---------|-----|-------|
| Lambda | ~720 invocações/mês (1/dia × 30), 300s cada | ~$15.30 |
| EventBridge | ~1440 chamadas/mês (2/dia × 30) | ~$0.36 |
| CloudWatch Logs | ~100MB/mês | ~$5.00 |
| S3 | ~1GB dados | ~$0.025 |
| **Total** | | ~**$20.70/mês** |

## 10. Troubleshooting

### Lambda timeout
- Aumentar timeout em Lambda configuration
- Otimizar código para não fazer múltiplas requisições

### "Permission Denied"
```bash
# Verificar role permissions
aws iam get-role-policy --role-name lambda-role --policy-name inline-policy

# Re-adicionar se necessário
aws lambda add-permission \
    --function-name daily-data-pipeline \
    --statement-id AllowEventBridge \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com
```

### Dados não atualizando
- Verificar logs do Lambda em CloudWatch
- Validar S3 bucket permissions
- Verificar formato do evento EventBridge

## Referências

- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [EventBridge Documentation](https://docs.aws.amazon.com/eventbridge/)
- [CloudWatch Events](https://docs.aws.amazon.com/AmazonCloudWatch/latest/events/)
