from datetime import timedelta

import pytest

from conftest import DIA_1
from service import (
    AlunoComAtraso,
    AlunoDuplicado,
    AlunoNaoEncontrado,
    DadosInvalidos,
    EmailInvalido,
    EmprestimoJaDevolvido,
    EmprestimoNaoEncontrado,
    LimiteEmprestimos,
    LivroComEmprestimoAberto,
    LivroDuplicado,
    LivroIndisponivel,
    LivroNaoEncontrado,
)


def disponiveis(servico, isbn):
    return servico.buscar_livro(isbn)["exemplares_disponiveis"]


# ------------------------------------------------------------------ R1
class TestR1CadastroLivros:
    def test_cadastrar_e_buscar_por_isbn(self, servico):
        servico.cadastrar_livro("999", "Livro X", "Autor Y", 2020, "Teste", 3)
        livro = servico.buscar_livro("999")
        assert livro["titulo"] == "Livro X"
        assert livro["exemplares_total"] == 3
        assert livro["exemplares_disponiveis"] == 3

    def test_isbn_unico(self, servico):
        servico.cadastrar_livro("999", "Livro X", "Autor Y", 2020, "Teste", 1)
        with pytest.raises(LivroDuplicado):
            servico.cadastrar_livro("999", "Outro", "Outro", 2021, "Teste", 1)

    def test_listar_ordenado_por_titulo(self, acervo):
        titulos = [l["titulo"] for l in acervo.listar_livros()]
        assert titulos == sorted(titulos)
        assert len(titulos) == 6

    def test_atualizar(self, acervo):
        livro = acervo.atualizar_livro("111", titulo="Dom Casmurro (ed. revista)", exemplares_total=4)
        assert livro["titulo"] == "Dom Casmurro (ed. revista)"
        assert livro["exemplares_total"] == 4
        assert livro["exemplares_disponiveis"] == 4

    def test_atualizar_nao_reduz_abaixo_dos_emprestados(self, acervo):
        acervo.emprestar("111", "A1", hoje=DIA_1)
        acervo.emprestar("111", "B2", hoje=DIA_1)
        with pytest.raises(DadosInvalidos):
            acervo.atualizar_livro("111", exemplares_total=1)
        assert acervo.buscar_livro("111")["exemplares_total"] == 2

    def test_remover(self, acervo):
        acervo.remover_livro("555")
        with pytest.raises(LivroNaoEncontrado):
            acervo.buscar_livro("555")

    def test_nao_remove_livro_com_emprestimo_aberto(self, acervo):
        emp = acervo.emprestar("555", "A1", hoje=DIA_1)
        with pytest.raises(LivroComEmprestimoAberto):
            acervo.remover_livro("555")
        acervo.devolver(emp["_id"], hoje=DIA_1)
        acervo.remover_livro("555")  # após a devolução, pode remover

    def test_buscar_inexistente(self, servico):
        with pytest.raises(LivroNaoEncontrado):
            servico.buscar_livro("000")


# ------------------------------------------------------------------ R2
class TestR2CadastroAlunos:
    def test_cadastrar_e_buscar(self, servico):
        servico.cadastrar_aluno("M1", "Maria", "Medicina", "maria@fac.br")
        assert servico.buscar_aluno("M1")["nome"] == "Maria"

    def test_matricula_unica(self, servico):
        servico.cadastrar_aluno("M1", "Maria", "Medicina", "maria@fac.br")
        with pytest.raises(AlunoDuplicado):
            servico.cadastrar_aluno("M1", "Outra", "Direito", "outra@fac.br")

    def test_email_sem_arroba(self, servico):
        with pytest.raises(EmailInvalido):
            servico.cadastrar_aluno("M1", "Maria", "Medicina", "maria.fac.br")

    def test_aluno_inexistente(self, servico):
        with pytest.raises(AlunoNaoEncontrado):
            servico.buscar_aluno("XX")


# ------------------------------------------------------------------ R3
class TestR3BuscaLivros:
    def test_parte_do_titulo_sem_diferenciar_maiusculas(self, acervo):
        assert [l["isbn"] for l in acervo.buscar_livros("CLEAN")] == ["222"]

    def test_parte_do_autor(self, acervo):
        titulos = [l["titulo"] for l in acervo.buscar_livros("machado")]
        assert titulos == ["Dom Casmurro", "Memórias Póstumas de Brás Cubas"]

    def test_filtrar_por_categoria_ordenado(self, acervo):
        titulos = [l["titulo"] for l in acervo.buscar_livros(categoria="computação")]
        assert titulos == ["Algoritmos", "Banco de Dados", "Clean Code"]

    def test_texto_e_categoria(self, acervo):
        assert [l["isbn"] for l in acervo.buscar_livros("o", categoria="Romance")] == [
            "111", "333", "555",
        ]

    def test_caracteres_especiais_nao_quebram_regex(self, acervo):
        assert acervo.buscar_livros("(.*") == []


# ------------------------------------------------------------------ R4
class TestR4Emprestar:
    def test_emprestimo_decrementa_estoque_e_prazo_7_dias(self, acervo):
        emp = acervo.emprestar("111", "A1", hoje=DIA_1)
        assert disponiveis(acervo, "111") == 1
        assert emp["data_prevista"] == DIA_1 + timedelta(days=7)
        assert emp["data_devolucao"] is None

    def test_sem_exemplar_disponivel(self, acervo):
        acervo.emprestar("222", "A1", hoje=DIA_1)
        with pytest.raises(LivroIndisponivel):
            acervo.emprestar("222", "B2", hoje=DIA_1)
        assert disponiveis(acervo, "222") == 0

    def test_estoque_nunca_fica_negativo(self, acervo, db):
        # Simula a corrida: o livro aparenta ter estoque na leitura, mas outro
        # processo zera antes do update. O filtro "$gt: 0" impede o negativo.
        db.livros.update_one({"isbn": "444"}, {"$set": {"exemplares_disponiveis": 0}})
        with pytest.raises(LivroIndisponivel):
            acervo.emprestar("444", "A1", hoje=DIA_1)
        assert disponiveis(acervo, "444") == 0

    def test_limite_de_3_emprestimos(self, acervo):
        for isbn in ("111", "333", "444"):
            acervo.emprestar(isbn, "A1", hoje=DIA_1)
        with pytest.raises(LimiteEmprestimos):
            acervo.emprestar("666", "A1", hoje=DIA_1)
        assert disponiveis(acervo, "666") == 2

    def test_aluno_com_atraso_nao_pega_outro(self, acervo):
        acervo.emprestar("111", "A1", hoje=DIA_1)
        # No 7º dia ainda está no prazo
        acervo.emprestar("333", "A1", hoje=DIA_1 + timedelta(days=7))
        # No 8º dia o primeiro empréstimo está atrasado
        with pytest.raises(AlunoComAtraso):
            acervo.emprestar("444", "A1", hoje=DIA_1 + timedelta(days=8))

    def test_aluno_ou_livro_inexistente(self, acervo):
        with pytest.raises(AlunoNaoEncontrado):
            acervo.emprestar("111", "ZZ", hoje=DIA_1)
        with pytest.raises(LivroNaoEncontrado):
            acervo.emprestar("000", "A1", hoje=DIA_1)


# ------------------------------------------------------------------ R5
class TestR5Devolver:
    def test_devolucao_no_prazo(self, acervo):
        emp = acervo.emprestar("111", "A1", hoje=DIA_1)
        dev = acervo.devolver(emp["_id"], hoje=DIA_1 + timedelta(days=7))
        assert dev["data_devolucao"] == DIA_1 + timedelta(days=7)
        assert dev["multa"] == 0
        assert disponiveis(acervo, "111") == 2

    def test_multa_de_2_reais_por_dia(self, acervo):
        emp = acervo.emprestar("111", "A1", hoje=DIA_1)
        dev = acervo.devolver(emp["_id"], hoje=DIA_1 + timedelta(days=10))
        assert dev["multa"] == pytest.approx(6.00)  # 3 dias de atraso

    def test_devolver_duas_vezes_gera_erro(self, acervo):
        emp = acervo.emprestar("111", "A1", hoje=DIA_1)
        acervo.devolver(emp["_id"], hoje=DIA_1)
        with pytest.raises(EmprestimoJaDevolvido):
            acervo.devolver(emp["_id"], hoje=DIA_1)
        assert disponiveis(acervo, "111") == 2  # estoque não é incrementado 2x

    def test_aceita_id_como_texto(self, acervo):
        emp = acervo.emprestar("111", "A1", hoje=DIA_1)
        acervo.devolver(str(emp["_id"]), hoje=DIA_1)

    def test_emprestimo_inexistente(self, acervo):
        with pytest.raises(EmprestimoNaoEncontrado):
            acervo.devolver("000000000000000000000000")
        with pytest.raises(EmprestimoNaoEncontrado):
            acervo.devolver("id-invalido")

    def test_devolucao_libera_aluno_atrasado(self, acervo):
        emp = acervo.emprestar("111", "A1", hoje=DIA_1)
        depois = DIA_1 + timedelta(days=9)
        with pytest.raises(AlunoComAtraso):
            acervo.emprestar("333", "A1", hoje=depois)
        acervo.devolver(emp["_id"], hoje=depois)
        acervo.emprestar("333", "A1", hoje=depois)


# ------------------------------------------------------------------ R6
class TestR6Relatorios:
    @pytest.fixture
    def historico(self, acervo):
        """Dom Casmurro 3x, Algoritmos 2x, Clean Code 1x."""
        d = DIA_1
        for mat in ("A1", "B2", "C3"):
            e = acervo.emprestar("111", mat, hoje=d)
            acervo.devolver(e["_id"], hoje=d + timedelta(days=1))
        e = acervo.emprestar("444", "A1", hoje=d)
        acervo.devolver(e["_id"], hoje=d + timedelta(days=12))  # 5 dias → R$ 10
        e = acervo.emprestar("444", "B2", hoje=d)
        acervo.devolver(e["_id"], hoje=d + timedelta(days=8))   # 1 dia → R$ 2
        acervo.emprestar("222", "C3", hoje=d + timedelta(days=20))  # em aberto
        return acervo

    def test_top_5_livros(self, historico):
        top = historico.top_livros()
        assert [(l["isbn"], l["total"]) for l in top] == [("111", 3), ("444", 2), ("222", 1)]
        assert top[0]["titulo"] == "Dom Casmurro"

    def test_top_limita_a_5(self, acervo):
        for isbn in ("111", "222", "333", "444", "555", "666"):
            e = acervo.emprestar(isbn, "A1", hoje=DIA_1)
            acervo.devolver(e["_id"], hoje=DIA_1)
        assert len(acervo.top_livros()) == 5

    def test_emprestimos_por_curso(self, historico):
        assert historico.emprestimos_por_curso() == [
            {"curso": "Engenharia", "total": 4},
            {"curso": "Direito", "total": 2},
        ]

    def test_alunos_com_atraso(self, historico):
        hoje = DIA_1 + timedelta(days=20 + 7 + 4)  # 4 dias após o prazo
        assert historico.alunos_com_atraso(hoje=hoje) == [{
            "matricula": "C3", "nome": "Carla", "livro": "Clean Code",
            "data_prevista": DIA_1 + timedelta(days=27), "dias_atraso": 4,
        }]
        assert historico.alunos_com_atraso(hoje=DIA_1 + timedelta(days=27)) == []

    def test_total_multas(self, historico):
        assert historico.total_multas() == pytest.approx(12.00)

    def test_total_multas_vazio(self, servico):
        assert servico.total_multas() == 0.0
