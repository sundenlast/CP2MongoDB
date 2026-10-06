# CP2 MongoDB — Sistema de Empréstimo de Livros

Backend em Python + MongoDB para a biblioteca da faculdade: cadastro de livros e alunos, empréstimos, devoluções com multa e relatórios, tudo por um menu no terminal.

GRUPO:

Felipe Hideki RM98323
Guilherme Milheiro RM550295
Jhonatan Curci RM94188
Enzo Vasconcelos RM550702
Ricardo Queiroz RM94241

---

## 1. Pré-requisitos

Instale na sua máquina:

| Ferramenta | Para quê | Download |
|------------|----------|----------|
| **Python 3.10+** | Rodar o projeto | <https://www.python.org/downloads/> |
| **Git** | Baixar o projeto | <https://git-scm.com/downloads> |
| **Docker Desktop** | Subir o MongoDB | <https://www.docker.com/products/docker-desktop/> |

> No instalador do Python no Windows, marque **"Add python.exe to PATH"**.
>
> Não quer instalar o Docker? Use o MongoDB Atlas (gratuito, na nuvem). Veja a seção **3B**.

Confira se está tudo instalado:

```bash
python --version
git --version
docker --version
```

> Em Linux/macOS o comando pode ser `python3` em vez de `python`.

---

## 2. Baixar o projeto e preparar o ambiente Python

```bash
git clone https://github.com/<seu-usuario>/CP2MongoDB.git
cd CP2MongoDB
```

Crie e ative um ambiente virtual:

**Windows (PowerShell)**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```
> Se aparecer erro de "execução de scripts desabilitada", rode uma vez:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

**Windows (CMD)**
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

**Linux / macOS**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

---

## 3. Subir o MongoDB

### 3A. Com Docker (recomendado)

1. Abra o **Docker Desktop** e espere ele ficar "running".
2. Na pasta do projeto, rode:

```bash
docker compose up -d
```

Pronto: o MongoDB está em `localhost:27017`. Os dados ficam salvos num volume e sobrevivem a reinícios.

Comandos úteis:

```bash
docker compose ps        # ver se está rodando
docker compose stop      # parar
docker compose down -v   # parar e APAGAR os dados
```

### 3B. Com MongoDB Atlas (sem Docker)

1. Crie uma conta em <https://cloud.mongodb.com> e um cluster gratuito (**M0**).
2. Em **Database Access**, crie um usuário e senha.
3. Em **Network Access**, clique em **Add IP Address → Allow access from anywhere** (ou adicione o seu IP).
4. Em **Connect → Drivers**, copie a connection string.
5. Defina a variável `MONGO_URI` no terminal (troque usuário, senha e endereço):

**Windows (PowerShell)**
```powershell
$env:MONGO_URI = "mongodb+srv://usuario:senha@cluster0.xxxxx.mongodb.net"
```

**Linux / macOS**
```bash
export MONGO_URI="mongodb+srv://usuario:senha@cluster0.xxxxx.mongodb.net"
```

> A variável vale só para o terminal aberto. Defina de novo se abrir outro.

Variáveis de ambiente aceitas:

| Variável    | Padrão                      |
|-------------|-----------------------------|
| `MONGO_URI` | `mongodb://localhost:27017` |
| `MONGO_DB`  | `biblioteca`                |

---

## 4. Rodar o sistema

Com o ambiente virtual ativo e o MongoDB no ar:

```bash
python main.py
```

Vai aparecer o menu:

```
 Livros        1) Cadastrar  2) Buscar por ISBN  3) Listar  4) Atualizar  5) Remover  6) Buscar
 Alunos        7) Cadastrar  8) Buscar por matrícula
 Empréstimos   9) Emprestar  10) Devolver  11) Listar empréstimos de um aluno
 Relatórios   12) Top 5 livros  13) Por curso  14) Atrasados  15) Total de multas
               0) Sair
```

**Dica para testar atrasos:** ao emprestar, devolver ou ver atrasados, o menu pede uma data (`AAAA-MM-DD`). Deixe em branco para usar hoje, ou digite uma data futura para simular atraso e multa.

Roteiro rápido de teste:
1. Opção `1`: cadastre um livro (ex.: ISBN `111`, 1 exemplar).
2. Opção `7`: cadastre um aluno (ex.: matrícula `A1`).
3. Opção `9`: empreste o `111` para `A1` com data `2026-01-01`.
4. Opção `11`: veja o empréstimo e copie o **id**.
5. Opção `10`: devolva usando o id, com data `2026-01-12`. Multa de R$ 6,00 (3 dias de atraso).
6. Opção `15`: veja o total arrecadado.

---

## 5. Rodar os testes

```bash
pytest -v
```

Os testes usam um MongoDB **em memória** (mongomock), então **não precisam do Docker**.

Para rodar contra um MongoDB real (o banco `biblioteca_test` é apagado e recriado):

```powershell
# Windows PowerShell
$env:MONGO_TEST_URI = "mongodb://localhost:27017"; pytest -v
```
```bash
# Linux / macOS
MONGO_TEST_URI="mongodb://localhost:27017" pytest -v
```

---

## 6. Problemas comuns

| Problema | Solução |
|----------|---------|
| `Não foi possível conectar ao MongoDB` | O Docker Desktop está aberto? Rode `docker compose ps`. No Atlas, confira a `MONGO_URI` e o Network Access. |
| `python` não é reconhecido | Reinstale o Python marcando "Add to PATH", ou use `py` (Windows) / `python3` (Linux/macOS). |
| `docker compose` não existe | Versões antigas usam `docker-compose` (com hífen). |
| Porta 27017 já em uso | Já existe um MongoDB rodando na máquina. Pare-o, ou use-o direto sem Docker. |
| `ModuleNotFoundError: pymongo` | O ambiente virtual não está ativo. Ative-o (passo 2) e rode `pip install -r requirements.txt`. |

---

## 7. Estrutura do projeto

```
db.py               conexão com o MongoDB e criação dos índices
service.py          regras de negócio e exceções próprias
main.py             menu do terminal
tests/              testes com pytest (R1 a R6)
docker-compose.yml  MongoDB local
requirements.txt    dependências Python
```

## 8. Principais decisões da equipe

- **Camadas separadas:** `db.py` (banco), `service.py` (regras, sem `print`/`input`) e `main.py` (menu).
- **Exceções próprias:** todas herdam de `ErroNegocio` (`LivroIndisponivel`, `LimiteEmprestimos`, `AlunoComAtraso`, `EmprestimoJaDevolvido`...). O menu mostra a mensagem sem fechar o programa.
- **Estoque seguro:** o empréstimo usa `update_one` com filtro `exemplares_disponiveis > 0` e `$inc: -1`. A operação é atômica, então dois empréstimos simultâneos nunca deixam o estoque negativo.
- **Devolução única:** a devolução só atualiza se `data_devolucao` ainda for nula. Devolver duas vezes gera `EmprestimoJaDevolvido`, e o estoque não é incrementado duas vezes.
- **Índices únicos** em `livros.isbn` e `alunos.matricula`, mais índices para buscar empréstimos em aberto e atrasados.
- **Data como parâmetro:** emprestar, devolver e o relatório de atrasos aceitam `hoje`, para testar atrasos sem esperar dias.
- **Regras de prazo:** prazo de 7 dias. Atraso contado em dias corridos após a data prevista, com multa de R$ 2,00 por dia, gravada no empréstimo na devolução.
- **Relatórios** feitos com Aggregation Pipeline (`$group`, `$lookup`, `$unwind`, `$project`, `$sort`, `$limit`).
- **Limitação conhecida:** o limite de 3 empréstimos é verificado sem transação. Dois pedidos simultâneos do mesmo aluno poderiam passar do limite.
