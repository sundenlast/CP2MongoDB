import os
from datetime import datetime

import mongomock
import pytest

from db import criar_indices
from service import BibliotecaService

DIA_1 = datetime(2026, 3, 2, 10, 0)


@pytest.fixture
def db():
    """Banco em memória (mongomock) já com os índices do sistema.

    Para rodar contra um MongoDB real, defina MONGO_TEST_URI.
    """
    uri = os.getenv("MONGO_TEST_URI")
    if uri:
        from pymongo import MongoClient

        client = MongoClient(uri)
        client.drop_database("biblioteca_test")
        banco = client["biblioteca_test"]
    else:
        banco = mongomock.MongoClient()["biblioteca_test"]
    criar_indices(banco)
    yield banco
    if uri:
        client.drop_database("biblioteca_test")


@pytest.fixture
def servico(db):
    return BibliotecaService(db)


@pytest.fixture
def acervo(servico):
    """Alguns livros e alunos prontos para os testes."""
    servico.cadastrar_livro("111", "Dom Casmurro", "Machado de Assis", 1899, "Romance", 2)
    servico.cadastrar_livro("222", "Clean Code", "Robert C. Martin", 2008, "Computação", 1)
    servico.cadastrar_livro("333", "Memórias Póstumas de Brás Cubas", "Machado de Assis", 1881, "Romance", 3)
    servico.cadastrar_livro("444", "Algoritmos", "Thomas Cormen", 2009, "Computação", 5)
    servico.cadastrar_livro("555", "O Cortiço", "Aluísio Azevedo", 1890, "Romance", 1)
    servico.cadastrar_livro("666", "Banco de Dados", "Carlos Heuser", 2009, "Computação", 2)
    servico.cadastrar_aluno("A1", "Ana", "Engenharia", "ana@fac.br")
    servico.cadastrar_aluno("B2", "Bruno", "Direito", "bruno@fac.br")
    servico.cadastrar_aluno("C3", "Carla", "Engenharia", "carla@fac.br")
    return servico
