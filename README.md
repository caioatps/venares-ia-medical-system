# Venares — Aulas automáticas (Zoom → PDF → Google Drive)

Quando você termina de gravar uma aula no Zoom, este agente faz sozinho o que
hoje você faz na mão:

1. Recebe o aviso do Zoom de que a gravação e a **transcrição** ficaram prontas.
2. Baixa a transcrição da nuvem do Zoom.
3. Limpa o ruído e **aplica o glossário médico** (corrige os termos que a
   transcrição automática erra e padroniza as siglas que a equipe usa).
4. Gera o **resumo estruturado** com o Claude e renderiza no **PDF do modelo**.
5. Descobre se a aula foi da **Start** ou da **Surgical** pelo título da reunião.
6. Lê a pasta certa no Google Drive, vê que a última é a **03** e nomeia a nova
   como **04**, com a data e o nome da mentoria.
7. Sobe **o vídeo e o PDF** para a pasta daquela mentoria.
8. Manda um **WhatsApp para o responsável de TI** com os dois links, o número
   da aula e a data, prontos para ele publicar na plataforma.

Nada disso exige um clique seu.

---

## Como está organizado

```
src/venares_aulas/
  api.py              servidor de webhook (FastAPI) + fila + agendador
  cli.py              comandos de operação e depuração
  pipeline.py         orquestra a aula inteira, com retentativa
  config.py           leitura do config.yaml e do .env
  db.py               fila e histórico em SQLite (nunca duplica upload)
  nomeacao.py         Start × Surgical, numeração sequencial, nome do arquivo
  zoom/               OAuth, API de gravações, validação de webhook
  transcricao/        leitura do .vtt e o glossário médico
  resumo/             prompts, modelo de dados e chamada ao Claude
  pdf/                Jinja2 + WeasyPrint
  drive/              autenticação e upload retomável
  notificacao/        WhatsApp (Meta Cloud API ou Twilio)
config/               config.yaml e glossario.yaml (você edita estes)
templates/            resumo_aula.html — o modelo do PDF
```

---

## Instalação

### 1. Dependências

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

O WeasyPrint precisa de bibliotecas do sistema. No Ubuntu/Debian:

```bash
sudo apt install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b \
                 libcairo2 libgdk-pixbuf-2.0-0 fonts-dejavu-core
```

(O `Dockerfile` já traz tudo isso — se for rodar em container, pule este passo.)

### 2. Configuração

```bash
cp .env.example .env
cp config/config.example.yaml config/config.yaml
cp config/glossario.example.yaml config/glossario.yaml
```

### 3. Zoom

No [App Marketplace](https://marketplace.zoom.us) → **Develop → Build App →
Server-to-Server OAuth**:

- Copie `Account ID`, `Client ID` e `Client Secret` para o `.env`.
- Em **Scopes**, adicione:
  - `cloud_recording:read:list_user_recordings:admin`
  - `cloud_recording:read:list_recording_files:admin`
  - `meeting:read:meeting:admin`
  - `cloud_recording:delete:meeting_recording:admin` *(só se for usar
    `apagar_da_nuvem_apos_upload`)*
- Em **Feature → Event Subscriptions**, ative e cadastre a URL
  `https://SEU-DOMINIO/webhooks/zoom`, assinando os eventos:
  - `recording.completed`
  - `recording.transcript_completed`
- Copie o **Secret Token** dessa aba para `ZOOM_SECRET_TOKEN` no `.env`.

> **Importante:** a transcrição automática precisa estar ligada na sua conta
> (Settings → Recording → *Cloud recording* → *Create audio transcript*). Sem
> isso o Zoom nunca dispara `recording.transcript_completed`.

O Zoom valida a URL enviando um desafio — o servidor já responde a ele, então
basta ter o serviço no ar antes de clicar em *Validate*.

### 4. Google Drive

Recomendado para o Drive pessoal (os arquivos ficam com você como dono):

1. No Google Cloud Console: crie um projeto e ative a **Google Drive API**.
2. Credenciais → **OAuth client ID** → tipo **Desktop app** → baixe o JSON.
3. Rode e autorize com a conta dona do Drive:
   ```bash
   python scripts/autorizar_google.py ~/Downloads/client_secret.json
   ```
4. Cole as três linhas impressas no `.env`.

Se as pastas estiverem em um **Drive Compartilhado** do Workspace, use uma
conta de serviço (`GOOGLE_SERVICE_ACCOUNT_FILE`) e informe o
`drive_compartilhado_id` de cada mentoria no `config.yaml`.

**Os IDs das pastas** são o trecho da URL depois de `/folders/`:
`https://drive.google.com/drive/folders/`**`1AbCdEf...`**

### 5. Claude

`ANTHROPIC_API_KEY` no `.env` (console.anthropic.com).

### 6. WhatsApp

**Meta Cloud API** (padrão): crie o app em developers.facebook.com, pegue o
token permanente e o `Phone Number ID`. Fora da janela de 24 horas, o WhatsApp
só entrega **mensagem de template aprovado** — por isso o padrão aqui é
template. Cadastre um com 5 variáveis, nesta ordem:

```
Nova aula pronta para publicação.
Mentoria: {{1}} · Aula {{2}} · {{3}}
Vídeo: {{4}}
Resumo: {{5}}
```

e ponha o nome dele em `notificacao.whatsapp.nome_template`.

**Twilio** é a alternativa: troque `provedor: "twilio"` e preencha as três
variáveis `TWILIO_*`.

### 7. Confira tudo antes de subir

```bash
venares-aulas verificar
```

Ele testa o token do Zoom, abre as duas pastas do Drive, mostra **qual será o
número da próxima aula de cada mentoria**, valida o template do PDF e o
glossário, e aponta o que está faltando.

---

## Como rodar

### Servidor (produção)

```bash
docker compose up -d --build
# ou, sem docker:
venares-aulas servir --porta 8080
```

O serviço precisa de uma **URL pública HTTPS** para o Zoom alcançar
(Cloud Run, Railway, Render, ou um VPS com Caddy/Nginx à frente).

Além do webhook, um agendador interno reexamina a cada minuto o que ficou
pendente — se o Zoom demorar para publicar a transcrição, ou se um webhook se
perder, a aula continua sendo processada.

### Comandos úteis

```bash
# testa a regra Start × Surgical num título, sem tocar em nada
venares-aulas classificar "Mentoria Surgical - Aula de quinta"

# processa uma gravação específica pelo UUID
venares-aulas processar "abc123==" --forcar

# rede de segurança: acha gravações dos últimos dias que ficaram para trás
venares-aulas varrer --dias 7 --simular

# histórico e erros
venares-aulas listar
venares-aulas listar --status erro

# gera o PDF a partir de um .vtt local — para calibrar o modelo e o glossário
venares-aulas resumir-arquivo aula.vtt --titulo "Mentoria Start - Aula 4" \
                                       --data 17/03/2026 --numero 4
```

Esse último é o comando para você usar enquanto ajusta o modelo do PDF: pegue
a transcrição de uma aula antiga, rode, olhe o resultado, ajuste
`templates/resumo_aula.html` e `config/glossario.yaml`, e repita. Nada é
enviado para o Drive.

---

## O que você vai querer ajustar

| O quê | Onde |
|---|---|
| Nomes e palavras-chave das mentorias | `config/config.yaml` → `mentorias` |
| IDs das duas pastas do Drive | `config/config.yaml` → `pasta_drive_id` |
| Padrão do nome do arquivo | `config/config.yaml` → `nomeacao.padrao` |
| Termos médicos e siglas | `config/glossario.yaml` |
| Frases de ruído a descartar | `config/glossario.yaml` → `remover_frases` |
| Layout, cores e logotipo do PDF | `templates/resumo_aula.html` e `pdf:` |
| Tom e ênfase do resumo | `config/config.yaml` → `resumo.instrucoes_extras` |
| Seções do resumo | `src/venares_aulas/resumo/modelos.py` + o template |

### Numeração sequencial

O número não é contado internamente: ele é **lido dos nomes que já estão na
pasta** do Drive, pelo regex `nomeacao.regex_numero`. Se a pasta tem até
`Aula 03`, a próxima é a `04` — inclusive para arquivos que você subiu à mão
antes de instalar isto, desde que o nome case com o regex. O banco local
guarda os números já atribuídos como trava extra contra duplicidade.

### Se a mentoria não for identificada

O agente **não chuta**: ele para, registra o erro e te avisa no WhatsApp. Você
pode reprocessar depois de corrigir o título, ou definir `mentoria_padrao` no
`config.yaml` para ele assumir uma das duas quando o título não disser nada.

---

## Testes

```bash
PYTHONPATH=src pytest -q
```

Cobrem o que quebra na prática: leitura do `.vtt` do Zoom, o glossário
(incluindo ruído colado em fala legítima), a classificação Start × Surgical,
a numeração sequencial lida do Drive, a assinatura do webhook e o preenchimento
do template do PDF.

---

## Segurança e privacidade

- O `.env`, o `config.yaml` e o `glossario.yaml` **não vão para o git**.
- A assinatura HMAC de todo webhook é conferida, com janela de 5 minutos
  contra replay.
- Os arquivos baixados ficam em uma pasta temporária e são **apagados ao fim
  de cada aula**, com ou sem erro.
- O prompt instrui o modelo a **não incluir dados que identifiquem pacientes**
  nos casos discutidos.
- Os endpoints `/admin/*` exigem o cabeçalho `X-Admin-Key`.
