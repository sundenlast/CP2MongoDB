"""Regras de negócio do sistema de empréstimo de livros.

Todas as funções que dependem da data atual aceitam o parâmetro ``hoje``
(``date`` ou ``datetime``). Se omitido, usa-se ``datetime.now()``. Isso
permite testar atrasos e multas sem esperar dias.
"""

import re
from datetime import date, datetime, timedelta

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import DuplicateKeyError

PRAZO_DIAS = 7
MAX_EMPRESTIMOS_ABERTOS = 3
MULTA_POR_DIA = 2.00


# --------------------------------------------------------------------------
# Exceções de negócio
# --------------------------------------------------------------------------
class ErroNegocio(Exception):
    """Base para todos os erros de regra de negócio."""


class DadosInvalidos(ErroNegocio):
    pass


class LivroNaoEncontrado(ErroNegocio):
    pass


class LivroDuplicado(ErroNegocio):
    pass


class LivroComEmprestimoAberto(ErroNegocio):
    pass


class AlunoNaoEncontrado(ErroNegocio):
    pass


class AlunoDuplicado(ErroNegocio):
    pass


class EmailInvalido(ErroNegocio):
    pass


class LivroIndisponivel(ErroNegocio):
    pass


class LimiteEmprestimos(ErroNegocio):
    pass


class AlunoComAtraso(ErroNegocio):
    pass


class EmprestimoNaoEncontrado(ErroNegocio):
    pass


class EmprestimoJaDevolvido(ErroNegocio):
    pass


# --------------------------------------------------------------------------
# Utilitários de data
# --------------------------------------------------------------------------
def _agora(hoje=None):
    """Normaliza ``hoje`` para datetime (o BSON não armazena ``date`` puro)."""
    if hoje is None:
        return datetime.now()
    if isinstance(hoje, datetime):
        return hoje
    if isinstance(hoje, date):
        return datetime(hoje.year, hoje.month, hoje.day)
    raise DadosInvalidos("Data inválida.")


def _inicio_do_dia(momento):
    return datetime(momento.year, momento.month, momento.day)


def dias_de_atraso(data_prevista, hoje):
    """Dias corridos entre a data prevista e ``hoje`` (0 se não há atraso)."""
    return max(0, (_agora(hoje).date() - data_prevista.date()).days)


def _sem_id(doc):
    if doc is not None:
        doc.pop("_id", None)
    return doc


# --------------------------------------------------------------------------
# Serviço
# --------------------------------------------------------------------------
class BibliotecaService:
    def __init__(self, db):
        self.db = db
        self.livros = db.livros
        self.alunos = db.alunos
        self.emprestimos = db.emprestimos

    # ---------------------------------------------------------------- R1
    def cadastrar_livro(self, isbn, titulo, autor, ano, categoria, exemplares_total):
        isbn = str(isbn).strip()
        titulo = str(titulo).strip()
        autor = str(autor).strip()
        categoria = str(categoria).strip()
        if not isbn or not titulo or not autor or not categoria:
            raise DadosInvalidos("ISBN, título, autor e categoria são obrigatórios.")
        ano = self._inteiro(ano, "ano")
        exemplares_total = self._inteiro(exemplares_total, "exemplares_total", minimo=1)

        livro = {
            "isbn": isbn,
            "titulo": titulo,
            "autor": autor,
            "ano": ano,
            "categoria": categoria,
            "exemplares_total": exemplares_total,
            "exemplares_disponiveis": exemplares_total,
        }
        try:
            self.livros.insert_one(livro)
        except DuplicateKeyError:
            raise LivroDuplicado(f"Já existe um livro com ISBN {isbn}.") from None
        return _sem_id(livro)

    def buscar_livro(self, isbn):
        livro = self.livros.find_one({"isbn": str(isbn).strip()}, {"_id": 0})
        if livro is None:
            raise LivroNaoEncontrado(f"Livro com ISBN {isbn} não encontrado.")
        return livro

    def listar_livros(self):
        return list(self.livros.find({}, {"_id": 0}).sort("titulo", 1))

    def atualizar_livro(self, isbn, **campos):
        """Atualiza título, autor, ano, categoria e/ou exemplares_total.

        Ao mudar ``exemplares_total`` a diferença é aplicada também em
        ``exemplares_disponiveis``. A operação é atômica e falha se reduzir o
        total abaixo da quantidade de exemplares emprestados.
        """
        permitidos = {"titulo", "autor", "ano", "categoria", "exemplares_total"}
        invalidos = set(campos) - permitidos
        if invalidos:
            raise DadosInvalidos(f"Campos não atualizáveis: {', '.join(sorted(invalidos))}.")

        atual = self.buscar_livro(isbn)
        set_ = {}
        for campo in ("titulo", "autor", "categoria"):
            if campo in campos:
                valor = str(campos[campo]).strip()
                if not valor:
                    raise DadosInvalidos(f"O campo {campo} não pode ficar vazio.")
                set_[campo] = valor
        if "ano" in campos:
            set_["ano"] = self._inteiro(campos["ano"], "ano")

        filtro = {"isbn": atual["isbn"]}
        update = {}
        if "exemplares_total" in campos:
            novo_total = self._inteiro(campos["exemplares_total"], "exemplares_total", minimo=1)
            delta = novo_total - atual["exemplares_total"]
            if delta:
                update["$inc"] = {"exemplares_total": delta, "exemplares_disponiveis": delta}
                # Garante que disponíveis não fique negativo nem com corrida
                filtro["exemplares_disponiveis"] = {"$gte": -delta}
                filtro["exemplares_total"] = atual["exemplares_total"]
        if set_:
            update["$set"] = set_
        if not update:
            return atual

        resultado = self.livros.update_one(filtro, update)
        if resultado.matched_count == 0:
            raise DadosInvalidos(
                "Não é possível reduzir o total abaixo dos exemplares emprestados."
            )
        return self.buscar_livro(isbn)

    def remover_livro(self, isbn):
        livro = self.buscar_livro(isbn)
        if self.emprestimos.count_documents({"isbn": livro["isbn"], "data_devolucao": None}):
            raise LivroComEmprestimoAberto(
                f"O livro {livro['isbn']} tem empréstimo em aberto e não pode ser removido."
            )
        self.livros.delete_one({"isbn": livro["isbn"]})

    # ---------------------------------------------------------------- R2
    def cadastrar_aluno(self, matricula, nome, curso, email):
        matricula = str(matricula).strip()
        nome = str(nome).strip()
        curso = str(curso).strip()
        email = str(email).strip()
        if not matricula or not nome or not curso:
            raise DadosInvalidos("Matrícula, nome e curso são obrigatórios.")
        if "@" not in email:
            raise EmailInvalido(f"E-mail inválido: {email!r} (deve conter @).")

        aluno = {"matricula": matricula, "nome": nome, "curso": curso, "email": email}
        try:
            self.alunos.insert_one(aluno)
        except DuplicateKeyError:
            raise AlunoDuplicado(f"Já existe um aluno com matrícula {matricula}.") from None
        return _sem_id(aluno)

    def buscar_aluno(self, matricula):
        aluno = self.alunos.find_one({"matricula": str(matricula).strip()}, {"_id": 0})
        if aluno is None:
            raise AlunoNaoEncontrado(f"Aluno com matrícula {matricula} não encontrado.")
        return aluno

    # ---------------------------------------------------------------- R3
    def buscar_livros(self, texto=None, categoria=None):
        """Busca por parte do título ou autor (sem diferenciar maiúsculas) e
        filtra por categoria. Resultado ordenado por título."""
        filtro = {}
        if texto and texto.strip():
            padrao = {"$regex": re.escape(texto.strip()), "$options": "i"}
            filtro["$or"] = [{"titulo": padrao}, {"autor": padrao}]
        if categoria and categoria.strip():
            filtro["categoria"] = {
                "$regex": f"^{re.escape(categoria.strip())}$",
                "$options": "i",
            }
        return list(self.livros.find(filtro, {"_id": 0}).sort("titulo", 1))

    # ---------------------------------------------------------------- R4
    def emprestar(self, isbn, matricula, hoje=None):
        agora = _agora(hoje)
        aluno = self.buscar_aluno(matricula)
        livro = self.buscar_livro(isbn)

        abertos = {"matricula": aluno["matricula"], "data_devolucao": None}
        atrasado = self.emprestimos.find_one(
            {**abertos, "data_prevista": {"$lt": _inicio_do_dia(agora)}}
        )
        if atrasado:
            raise AlunoComAtraso(
                f"{aluno['nome']} tem empréstimo atrasado e não pode pegar outro livro."
            )
        if self.emprestimos.count_documents(abertos) >= MAX_EMPRESTIMOS_ABERTOS:
            raise LimiteEmprestimos(
                f"{aluno['nome']} já tem {MAX_EMPRESTIMOS_ABERTOS} empréstimos em aberto."
            )

        # Decremento atômico: só casa se ainda houver exemplar disponível,
        # então dois empréstimos simultâneos nunca deixam o estoque negativo.
        resultado = self.livros.update_one(
            {"isbn": livro["isbn"], "exemplares_disponiveis": {"$gt": 0}},
            {"$inc": {"exemplares_disponiveis": -1}},
        )
        if resultado.modified_count == 0:
            raise LivroIndisponivel(f"Não há exemplar disponível de '{livro['titulo']}'.")

        emprestimo = {
            "isbn": livro["isbn"],
            "matricula": aluno["matricula"],
            "data_emprestimo": agora,
            "data_prevista": agora + timedelta(days=PRAZO_DIAS),
            "data_devolucao": None,
            "multa": 0.0,
        }
        try:
            self.emprestimos.insert_one(emprestimo)
        except Exception:
            # Compensa o estoque se a gravação do empréstimo falhar
            self.livros.update_one(
                {"isbn": livro["isbn"]}, {"$inc": {"exemplares_disponiveis": 1}}
            )
            raise
        return emprestimo

    def listar_emprestimos(self, matricula=None, apenas_abertos=False):
        filtro = {}
        if matricula is not None:
            filtro["matricula"] = str(matricula).strip()
        if apenas_abertos:
            filtro["data_devolucao"] = None
        return list(self.emprestimos.find(filtro).sort("data_emprestimo", 1))

    # ---------------------------------------------------------------- R5
    def devolver(self, emprestimo_id, hoje=None):
        agora = _agora(hoje)
        try:
            oid = ObjectId(emprestimo_id)
        except (InvalidId, TypeError):
            raise EmprestimoNaoEncontrado(f"Empréstimo {emprestimo_id} não encontrado.") from None

        emprestimo = self.emprestimos.find_one({"_id": oid})
        if emprestimo is None:
            raise EmprestimoNaoEncontrado(f"Empréstimo {emprestimo_id} não encontrado.")
        if emprestimo["data_devolucao"] is not None:
            raise EmprestimoJaDevolvido(f"O empréstimo {emprestimo_id} já foi devolvido.")

        multa = dias_de_atraso(emprestimo["data_prevista"], agora) * MULTA_POR_DIA

        # O filtro data_devolucao=None torna a devolução idempotente mesmo com
        # duas requisições simultâneas: só uma delas consegue marcar.
        resultado = self.emprestimos.update_one(
            {"_id": oid, "data_devolucao": None},
            {"$set": {"data_devolucao": agora, "multa": multa}},
        )
        if resultado.modified_count == 0:
            raise EmprestimoJaDevolvido(f"O empréstimo {emprestimo_id} já foi devolvido.")

        self.livros.update_one(
            {"isbn": emprestimo["isbn"]}, {"$inc": {"exemplares_disponiveis": 1}}
        )
        return self.emprestimos.find_one({"_id": oid})

    # ---------------------------------------------------------------- R6
    def top_livros(self, limite=5):
        pipeline = [
            {"$group": {"_id": "$isbn", "total": {"$sum": 1}}},
            {"$sort": {"total": -1, "_id": 1}},
            {"$limit": limite},
            {"$lookup": {
                "from": "livros", "localField": "_id",
                "foreignField": "isbn", "as": "livro",
            }},
            {"$unwind": {"path": "$livro", "preserveNullAndEmptyArrays": True}},
            {"$project": {
                "_id": 0, "isbn": "$_id",
                "titulo": {"$ifNull": ["$livro.titulo", "(livro removido)"]},
                "total": 1,
            }},
        ]
        return list(self.emprestimos.aggregate(pipeline))

    def emprestimos_por_curso(self):
        pipeline = [
            {"$lookup": {
                "from": "alunos", "localField": "matricula",
                "foreignField": "matricula", "as": "aluno",
            }},
            {"$unwind": "$aluno"},
            {"$group": {"_id": "$aluno.curso", "total": {"$sum": 1}}},
            {"$sort": {"total": -1, "_id": 1}},
            {"$project": {"_id": 0, "curso": "$_id", "total": 1}},
        ]
        return list(self.emprestimos.aggregate(pipeline))

    def alunos_com_atraso(self, hoje=None):
        inicio_hoje = _inicio_do_dia(_agora(hoje))
        pipeline = [
            {"$match": {"data_devolucao": None, "data_prevista": {"$lt": inicio_hoje}}},
            {"$lookup": {
                "from": "alunos", "localField": "matricula",
                "foreignField": "matricula", "as": "aluno",
            }},
            {"$unwind": "$aluno"},
            {"$lookup": {
                "from": "livros", "localField": "isbn",
                "foreignField": "isbn", "as": "livro",
            }},
            {"$unwind": "$livro"},
            {"$project": {
                "_id": 0,
                "matricula": 1,
                "nome": "$aluno.nome",
                "livro": "$livro.titulo",
                "data_prevista": 1,
                # ceil((início de hoje - data_prevista) / 1 dia) == diferença
                # em dias corridos, mesmo com data_prevista fora da meia-noite
                "dias_atraso": {"$ceil": {"$divide": [
                    {"$subtract": [inicio_hoje, "$data_prevista"]}, 86_400_000,
                ]}},
            }},
            {"$sort": {"dias_atraso": -1, "nome": 1}},
        ]
        return list(self.emprestimos.aggregate(pipeline))

    def total_multas(self):
        pipeline = [
            {"$match": {"multa": {"$gt": 0}}},
            {"$group": {"_id": None, "total": {"$sum": "$multa"}}},
        ]
        resultado = list(self.emprestimos.aggregate(pipeline))
        return float(resultado[0]["total"]) if resultado else 0.0

    # ---------------------------------------------------------------- apoio
    @staticmethod
    def _inteiro(valor, campo, minimo=None):
        try:
            numero = int(valor)
        except (TypeError, ValueError):
            raise DadosInvalidos(f"O campo {campo} deve ser um número inteiro.") from None
        if minimo is not None and numero < minimo:
            raise DadosInvalidos(f"O campo {campo} deve ser no mínimo {minimo}.")
        return numero
