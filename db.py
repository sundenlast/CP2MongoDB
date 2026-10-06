"""Camada de acesso ao banco: conexão com o MongoDB e criação de índices."""

import os

from pymongo import ASCENDING, MongoClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "biblioteca")


def get_db(uri=MONGO_URI, nome=MONGO_DB):
    """Abre a conexão e devolve o banco já com os índices criados."""
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")  # falha cedo se o MongoDB não estiver no ar
    db = client[nome]
    criar_indices(db)
    return db


def criar_indices(db):
    """Cria os índices usados pelo sistema (operação idempotente)."""
    # R1 / R2: chaves de negócio únicas
    db.livros.create_index([("isbn", ASCENDING)], unique=True, name="isbn_unico")
    db.alunos.create_index([("matricula", ASCENDING)], unique=True, name="matricula_unica")

    # Consultas frequentes de empréstimos em aberto por aluno e por livro
    db.emprestimos.create_index(
        [("matricula", ASCENDING), ("data_devolucao", ASCENDING)], name="aluno_abertos"
    )
    db.emprestimos.create_index(
        [("isbn", ASCENDING), ("data_devolucao", ASCENDING)], name="livro_abertos"
    )
    db.emprestimos.create_index(
        [("data_devolucao", ASCENDING), ("data_prevista", ASCENDING)], name="atrasados"
    )
