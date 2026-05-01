# Plano de Adequação à LGPD
## FIAP Tech Challenge Fase 5 - Stock Prediction Platform

**Data:** Janeiro 2025  
**Versão:** 1.0.0  
**Responsável:** FIAP Tech Challenge Team

---

## 1. Resumo Executivo

Este documento apresenta o plano de adequação do sistema de predição de ações à Lei Geral de Proteção de Dados (LGPD - Lei nº 13.709/2018), garantindo conformidade legal e proteção de dados pessoais.

**Status Atual:** ✅ Conformidade Parcial  
**Riscos Identificados:** Baixo (sistema utiliza principalmente dados públicos de mercado)

---

## 2. Escopo de Aplicação da LGPD

### 2.1 Dados Tratados

| Tipo de Dado | Classificação LGPD | Fonte | Tratamento |
|--------------|-------------------|-------|-----------|
| Preços de ações | **Não PII** | Yahoo Finance (público) | Análise preditiva |
| Indicadores técnicos | **Não PII** | Calculado | Machine Learning |
| Logs de API | **Possível PII** | Sistema interno | Monitoramento |
| Queries do usuário | **Possível PII** | Entrada LLM | Análise de linguagem |

### 2.2 Base Legal

**Art. 7º, Inciso VII da LGPD:**  
Tratamento baseado em **interesse legítimo** do controlador ou de terceiros, para fins de:
- Pesquisa acadêmica (FIAP Tech Challenge)
- Análise de dados públicos de mercado
- Melhoria de serviços de IA

**Justificativa:** O sistema processa majoritariamente dados públicos de mercado financeiro, sem identificação de titulares de dados.

---

## 3. Análise de Riscos

### 3.1 Dados Pessoais Potencialmente Coletados

Embora o sistema **não exija** dados pessoais para operar, podem ser inadvertidamente coletados:

1. **Logs de Acesso:**
   - Endereço IP
   - User-Agent (navegador)
   - Timestamps de requisições

2. **Queries do LLM Agent:**
   - Usuário pode incluir informações pessoais na pergunta
   - Exemplo: "Meu CPF é 123.456.789-00, devo comprar ITUB4?"

3. **Emails em Feedback (futuro):**
   - Se sistema de feedback for implementado

### 3.2 Matriz de Riscos

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| Vazamento de logs com IPs | Baixa | Médio | Criptografia, acesso restrito |
| PII em queries do LLM | Média | Alto | Detecção automática (Presidio) |
| Retenção excessiva de dados | Baixa | Baixo | Política de retenção (2 anos) |
| Acesso não autorizado a logs | Baixa | Médio | IAM, autenticação |

---

## 4. Medidas de Conformidade Implementadas

### 4.1 Princípios da LGPD (Art. 6º)

| Princípio | Implementação |
|-----------|--------------|
| **Finalidade** | Dados usados apenas para predição de ações e pesquisa |
| **Adequação** | Tratamento compatível com finalidades declaradas |
| **Necessidade** | Coleta mínima de dados (apenas dados de mercado) |
| **Transparência** | Model Card e System Card publicados |
| **Segurança** | TLS, IAM, criptografia em repouso |
| **Prevenção** | Guardrails para evitar coleta não intencional de PII |
| **Não discriminação** | Modelo não utiliza dados demográficos |

### 4.2 Direitos dos Titulares (Art. 18)

| Direito | Como Exercer | Prazo de Atendimento |
|---------|-------------|---------------------|
| **Confirmação de tratamento** | Email para contato | 15 dias |
| **Acesso aos dados** | Consulta via API (futura) | 15 dias |
| **Correção** | Solicitação via email | 15 dias |
| **Eliminação** | Remoção de logs sob demanda | 5 dias |
| **Portabilidade** | Exportação em JSON (futura) | 15 dias |
| **Revogação de consentimento** | N/A (não há consentimento, base legal é interesse legítimo) | - |

**Ponto de Contato (DPO):**  
Email: dpo@fiap-tech-challenge.example.com (fictício para demo)

### 4.3 Segurança da Informação (Art. 46)

**Medidas Técnicas:**
1. **Criptografia:**
   - TLS 1.3 para dados em trânsito
   - AES-256 para dados em repouso (S3, EBS)

2. **Controle de Acesso:**
   - AWS IAM com princípio de menor privilégio
   - MFA obrigatório para admins
   - Segregação de ambientes (dev/staging/prod)

3. **Detecção de PII:**
   - Microsoft Presidio para identificação automática
   - Anonymização antes de logging (`src/security/pii_detection.py`)

4. **Monitoramento:**
   - Logs auditáveis (CloudWatch)
   - Alertas de acesso não autorizado
   - Detecção de anomalias

**Medidas Organizacionais:**
1. Treinamento de equipe em LGPD
2. Política de resposta a incidentes
3. Backups criptografados com retenção de 30 dias

### 4.4 Anonimização e Pseudonimização

**Implementado:**
- Anonimização de PII detectado em queries (Presidio)
- Logs de acesso sem associação direta a identidade pessoal

**Hash de IPs:**
```python
# Exemplo de pseudonimização de IPs em logs
import hashlib

def hash_ip(ip: str) -> str:
    return hashlib.sha256(ip.encode()).hexdigest()[:16]
```

---

## 5. Política de Retenção de Dados

| Tipo de Dado | Retenção | Justificativa |
|--------------|----------|---------------|
| Dados de mercado (OHLCV) | **Indefinida** | Dados públicos, não sujeitos a exclusão |
| Logs de acesso | **90 dias** | Auditoria e troubleshooting |
| Modelos treinados | **2 anos** | Reprodutibilidade, regulatórios |
| Métricas agregadas | **Indefinida** | Não contêm PII |
| Queries do LLM | **7 dias** | Debug, excluídas após validação |

**Processo de Exclusão:**
```bash
# Script automatizado (cron job mensal)
make cleanup-old-logs
```

---

## 6. Resposta a Incidentes (Art. 48)

### 6.1 Plano de Resposta

1. **Detecção (0-1h):**
   - Alertas automáticos (Prometheus, CloudWatch)
   - Notificação para equipe de segurança

2. **Contenção (1-4h):**
   - Isolar componentes afetados
   - Bloquear acesso externo (Security Groups)

3. **Investigação (4-24h):**
   - Análise de logs
   - Identificação de dados expostos
   - Quantificação de titulares afetados

4. **Notificação (até 72h, se necessário):**
   - ANPD (Autoridade Nacional de Proteção de Dados)
   - Titulares afetados (se houver risco relevante)

5. **Remediação (1-7 dias):**
   - Correção de vulnerabilidades
   - Atualização de documentação
   - Comunicação de lições aprendidas

### 6.2 Matriz de Gravidade

| Severidade | Descrição | Ação |
|-----------|-----------|------|
| **Crítica** | Vazamento de >1000 registros com PII | Notificar ANPD em 72h |
| **Alta** | Acesso não autorizado a logs | Investigar e remediar |
| **Média** | Detecção de PII não anonymizado em logs | Limpar logs, revisar filtros |
| **Baixa** | Tentativa de prompt injection | Log e monitorar |

---

## 7. Transferência Internacional de Dados (Art. 33)

**Cenário:** Se LLM hospedado fora do Brasil (ex: OpenAI nos EUA)

**Medidas:**
1. **Cláusulas Contratuais Padrão:** Incluir DPA (Data Processing Agreement)
2. **Anonimização Prévia:** Remover PII antes de enviar para LLM externo
3. **Certificações:** Verificar ISO 27001, SOC 2 do provedor
4. **Escolha de Provedor:** Preferir AWS São Paulo (sa-east-1) para dados sensíveis

**Alternativa Cloud-Agnostic:**
- Ollama (local): Sem transferência internacional ✅
- AWS Bedrock (sa-east-1): Dados permanecem no Brasil ✅

---

## 8. Documentação e Transparência

### 8.1 Documentos Públicos

- ✅ **Model Card** (`docs/MODEL_CARD.md`)
- ✅ **System Card** (`docs/SYSTEM_CARD.md`)
- ✅ **LGPD Plan** (`docs/LGPD_PLAN.md`) - este documento
- ✅ **Privacy Policy** (futuro, para site público)

### 8.2 Registro de Atividades de Tratamento

Manter registro atualizado conforme Art. 37:
- Controlador: FIAP Tech Challenge Team
- Finalidade: Predição de preços de ações, pesquisa acadêmica
- Categorias de dados: Dados públicos de mercado + logs técnicos
- Medidas de segurança: Ver seção 4.3

---

## 9. Checklist de Conformidade

- [x] Base legal identificada (Art. 7º, VII - interesse legítimo)
- [x] Medidas de segurança implementadas (criptografia, IAM)
- [x] Detecção de PII automatizada (Presidio)
- [x] Política de retenção definida (2 anos)
- [x] Model Card e System Card publicados
- [x] Plano de resposta a incidentes documentado
- [ ] DPO designado (pendente para produção)
- [ ] Treinamento de equipe em LGPD (pendente)
- [ ] Política de privacidade publicada (pendente para site público)
- [ ] Contrato com fornecedores de LLM revisado (se aplicável)

---

## 10. Próximos Passos

### Curto Prazo (3 meses)
1. Designar DPO (Data Protection Officer)
2. Conduzir treinamento de LGPD para equipe
3. Publicar Privacy Policy no site
4. Implementar portal de exercício de direitos

### Médio Prazo (6 meses)
1. Auditoria externa de conformidade
2. Revisão anual de processos
3. Atualização de contratos com fornecedores
4. Simulação de resposta a incidentes

### Longo Prazo (12 meses)
1. Certificação ISO 27001
2. Implementar Privacy by Design em novos features
3. Expandir detecção de PII para outros idiomas
4. Automação completa de retenção e exclusão

---

## 11. Conclusão

O sistema apresenta **baixo risco de não conformidade com a LGPD**, pois:
1. Processa principalmente dados públicos (não PII)
2. Implementa detecção e anonimização de PII
3. Possui medidas de segurança robustas
4. Respeita princípios de finalidade, necessidade e transparência

**Recomendações:**
- Manter monitoramento contínuo de PII em logs
- Revisar política de retenção semestralmente
- Atualizar documentação ao adicionar novos datasets
- Considerar certificação ISO 27701 (Privacy Information Management)

---

**Aprovado por:** [Nome do Responsável]  
**Data:** Janeiro 2025  
**Próxima Revisão:** Julho 2025
