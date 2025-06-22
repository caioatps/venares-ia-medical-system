# VENARES IA - Sistema Médico Inteligente Completo

## 🚀 Sistema Médico com IA Avançada

**VENARES IA** combina a sabedoria de Venus (estrogênio/libido) com a força de Ares (testosterona/vitalidade) para análise hormonal personalizada com Inteligência Artificial.

### 📋 Funcionalidades Principais

#### 🔬 **Análise Clínica Inteligente**
- Geração automática de condutas médicas com IA
- Análise de prioridades do paciente (energia, libido, emagrecimento, etc.)
- Cálculo de dosagens personalizadas
- Avaliação de riscos cardiovasculares, metabólicos e hormonais
- Monitoramento de evolução do tratamento

#### 🧬 **8 IAs Especializadas**
1. **BioimpedanceAnalyzer**: Análise de composição corporal
2. **HormonalSymptomAnalyzer**: Correlação sintomas-hormônios
3. **DosagePrescriptionAnalyzer**: Cálculos de dosagem personalizada
4. **MonitoringEvolutionAnalyzer**: Acompanhamento de progressão
5. **NutritionalAnalyzer**: Otimização nutricional hormonal
6. **CardiovascularRiskAnalyzer**: Avaliação de risco cardiovascular
7. **VoiceAnalysisAI**: Análise de voz com contexto emocional
8. **IntelligentPrescriptionAI**: Geração automática de prescrições

#### 💊 **Base de Dados Médica Completa**
- **15+ Medicamentos Injetáveis**: L-Carnitina, Glutationa, NAD+, etc.
- **5 Protocolos Especializados**: Ansiedade/Depressão, Imunidade, Emagrecimento
- **Interações Medicamentosas**: Banco de dados com contraindicações
- **Referências Laboratoriais**: Valores normais por categoria
- **Protocolos de Segurança**: Pré, durante e pós-infusão

#### 👥 **Gestão de Pacientes Avançada**
- Cadastro completo com prioridades médicas
- Sistema de grupos personalizados
- Busca avançada por riscos, idade, gênero
- Acompanhamento de evolução com gráficos
- Sistema de pontuação 0-10 para tratamentos
- Alertas automáticos para casos de baixa pontuação

#### 🎨 **Interface Mitológica**
- **Tema Venus**: Rosa/dourado com elementos femininos
- **Tema Ares**: Vermelho/âmbar com elementos masculinos
- Animações suaves para redução de estresse
- Modo escuro/claro com transições automáticas
- Microanimações para experiência intuitiva

### 🏗️ **Arquitetura Técnica**

#### **Frontend**
- **React 18** + TypeScript
- **Shadcn/ui** + Radix UI
- **Tailwind CSS** com temas personalizados
- **TanStack Query** para gerenciamento de estado
- **Wouter** para roteamento
- **React Hook Form** + Zod para validação

#### **Backend**
- **Node.js** + Express + TypeScript
- **Passport.js** para autenticação
- **PostgreSQL** com Drizzle ORM
- **OpenAI GPT-4** para análise clínica
- **Anthropic Claude** para análises especializadas
- **WebSocket** para atualizações em tempo real

#### **Banco de Dados**
- **PostgreSQL** com Neon serverless
- **27 Tabelas** especializadas
- **Drizzle ORM** com type safety
- **Migrações automatizadas**

### 📊 **Schema do Banco de Dados**

#### **Tabelas Principais**
- `users`: Perfis médicos com CRM
- `patients`: Dados demográficos completos
- `patient_priorities`: Prioridades ordenadas (1ª, 2ª, 3ª)
- `anamnesis_sessions`: Histórico detalhado
- `bioimpedance_data`: Composição corporal
- `lab_results`: Resultados laboratoriais
- `clinical_cases`: Casos analisados por IA
- `suggested_conducts`: Recomendações de tratamento
- `treatment_outcomes`: Resultados de acompanhamento

#### **Base de Dados Médica**
- `medications`: Medicamentos injetáveis
- `medical_protocols`: Protocolos especializados
- `drug_interactions`: Interações medicamentosas
- `lab_references`: Valores de referência
- `safety_protocols`: Protocolos de segurança

#### **Conteúdo Educacional**
- `instructional_videos`: Vídeos educacionais
- `scientific_articles`: Artigos científicos
- `clinical_cases_library`: Biblioteca de casos
- `educational_courses`: Cursos especializados

### 🔧 **Configuração e Deploy**

#### **Variáveis de Ambiente**
```bash
DATABASE_URL=postgresql://...
SESSION_SECRET=your_secret_key
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
VITE_GITHUB_PERSONAL_ACCESS_TOKEN=ghp_...
```

#### **Instalação Local**
```bash
npm install
npm run db:push
npm run dev
```

#### **Deploy Replit**
- Workflow configurado para `npm run dev`
- PostgreSQL automático
- Vite + Express na porta 5000
- Sessões persistentes

### 🔐 **Segurança**

#### **Autenticação**
- Passport.js com estratégia local
- Hash de senhas com scrypt
- Sessões PostgreSQL seguras
- Validação de CRM médico

#### **Dados Médicos**
- Validação Zod em todas as entradas
- Sanitização de dados sensíveis
- Logs de auditoria
- Controle de acesso por usuário

### 📈 **Protocolos Clínicos Validados**

#### **Protocolos Hormonais**
- **Energia**: NAD+ + Testosterona
- **Libido**: Testosterona + Gestrinona
- **Emagrecimento**: Oxandrolona + NAD+
- **Pele/Cabelo**: Nestorone + Oxandrolona

#### **Dosagens por Idade**
- **20-30 anos**: G6E2 (Gestrinona 6mg + Estradiol 2mg)
- **30-40 anos**: G6E3 (Gestrinona 6mg + Estradiol 3mg)
- **40-50 anos**: G6E4 (Gestrinona 6mg + Estradiol 4mg)

#### **Casos Clínicos Validados**
- **Lipedema**: Protocolo multimodal 90 dias
- **MOSH**: Hipogonadismo masculino
- **Menopausa + Bipolar**: Reposição hormonal cuidadosa
- **Tirzepatida**: Emagrecimento 15-20% eficácia

### 🌟 **Diferencias Competitivos**

#### **IA Médica Avançada**
- Condutas baseadas em 38+ casos clínicos reais
- Análise de prioridades específicas do paciente
- Cálculos de dosagem personalizados
- Avaliação de riscos multifatorial

#### **Interface Humanizada**
- Temas mitológicos para engajamento
- Animações anti-estresse
- Fluxo intuitivo para médicos
- Feedback visual constante

#### **Integração Completa**
- GitHub para versionamento
- OpenAI + Anthropic para análises
- PostgreSQL para dados médicos
- Replit para deploy instantâneo

### 📞 **Suporte e Desenvolvimento**

#### **Sistema de Suporte**
- Bug reports com priorização
- Solicitações de funcionalidades
- Suporte técnico especializado
- Feedback por email

#### **Controle de Versão**
- GitHub integration completa
- Pull requests automatizados
- Documentação versionada
- Backup automático

### 🎯 **Próximos Desenvolvimentos**

#### **Funcionalidades Planejadas**
- Análise de imagens médicas
- Integração com laboratórios
- Telemedicina integrada
- Mobile app nativo
- Relatórios automatizados

#### **Melhorias Técnicas**
- Cache Redis para performance
- Microservices architecture
- Kubernetes deployment
- Monitoring avançado
- Testes automatizados

---

## 💡 **Como Usar**

### **1. Cadastro**
- Registre-se com CRM válido
- Complete perfil médico
- Configure preferências

### **2. Pacientes**
- Cadastre pacientes completos
- Defina prioridades (1ª, 2ª, 3ª)
- Registre anamnese detalhada

### **3. Análise IA**
- Use "Análise Rápida" para casos simples
- Página "Análise" para casos complexos
- Revise condutas geradas
- Ajuste conforme necessário

### **4. Acompanhamento**
- Registre evoluções
- Monitore gráficos de progresso
- Avalie eficácia (0-10)
- Ajuste tratamentos

---

**VENARES IA** - Transformando a medicina personalizada com Inteligência Artificial avançada.

*Desenvolvido com as melhores práticas de segurança médica e tecnologia de ponta.*