"""Interface de terminal (R7) do sistema de empréstimo de livros."""

from datetime import datetime

from pymongo.errors import PyMongoError

from db import get_db
from service import BibliotecaService, ErroNegocio

MENU = """
========= BIBLIOTECA =========
 Livros
  1) Cadastrar livro
  2) Buscar livro por ISBN
  3) Listar livros
  4) Atualizar livro
  5) Remover livro
  6) Buscar livros (título/autor/categoria)
 Alunos
  7) Cadastrar aluno
  8) Buscar aluno por matrícula
 Empréstimos
  9) Emprestar livro
 10) Devolver livro
 11) Listar empréstimos de um aluno
 Relatórios
 12) 5 livros mais emprestados
 13) Empréstimos por curso
 14) Alunos com empréstimos atrasados
 15) Total arrecadado em multas
  0) Sair
==============================="""


# ------------------------------------------------------------------ entrada
def perguntar(rotulo, obrigatorio=True):
    while True:
        valor = input(f"{rotulo}: ").strip()
        if valor or not obrigatorio:
            return valor
        print("  Campo obrigatório.")


def perguntar_data(rotulo="Data (AAAA-MM-DD, vazio = hoje)"):
    """Permite simular a data atual para testar atrasos."""
    while True:
        valor = input(f"{rotulo}: ").strip()
        if not valor:
            return None
        try:
            return datetime.strptime(valor, "%Y-%m-%d")
        except ValueError:
            print("  Data inválida, use o formato AAAA-MM-DD.")


def fmt_data(valor):
    return valor.strftime("%d/%m/%Y") if valor else "-"


def fmt_reais(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ------------------------------------------------------------------ saída
def mostrar_livros(livros):
    if not livros:
        print("Nenhum livro encontrado.")
        return
    print(f"{'ISBN':<15} {'Título':<35} {'Autor':<25} {'Ano':>4} {'Categoria':<15} Disp.")
    for l in livros:
        print(
            f"{l['isbn']:<15} {l['titulo'][:35]:<35} {l['autor'][:25]:<25} "
            f"{l['ano']:>4} {l['categoria'][:15]:<15} "
            f"{l['exemplares_disponiveis']}/{l['exemplares_total']}"
        )


def mostrar_emprestimo(e):
    status = f"devolvido em {fmt_data(e['data_devolucao'])}" if e["data_devolucao"] else "em aberto"
    print(
        f"[{e['_id']}] ISBN {e['isbn']} | emprestado {fmt_data(e['data_emprestimo'])} | "
        f"previsto {fmt_data(e['data_prevista'])} | {status} | multa {fmt_reais(e['multa'])}"
    )


# ------------------------------------------------------------------ ações
def cadastrar_livro(s):
    livro = s.cadastrar_livro(
        perguntar("ISBN"), perguntar("Título"), perguntar("Autor"),
        perguntar("Ano"), perguntar("Categoria"), perguntar("Quantidade de exemplares"),
    )
    print(f"Livro '{livro['titulo']}' cadastrado.")


def buscar_livro(s):
    mostrar_livros([s.buscar_livro(perguntar("ISBN"))])


def atualizar_livro(s):
    isbn = perguntar("ISBN")
    mostrar_livros([s.buscar_livro(isbn)])
    print("Deixe em branco o que não quiser alterar.")
    campos = {}
    for campo, rotulo in [
        ("titulo", "Título"), ("autor", "Autor"), ("ano", "Ano"),
        ("categoria", "Categoria"), ("exemplares_total", "Total de exemplares"),
    ]:
        valor = perguntar(rotulo, obrigatorio=False)
        if valor:
            campos[campo] = valor
    mostrar_livros([s.atualizar_livro(isbn, **campos)])


def remover_livro(s):
    isbn = perguntar("ISBN")
    if perguntar(f"Confirma remoção do livro {isbn}? (s/n)").lower() == "s":
        s.remover_livro(isbn)
        print("Livro removido.")


def buscar_livros(s):
    texto = perguntar("Parte do título ou autor (vazio = todos)", obrigatorio=False)
    categoria = perguntar("Categoria (vazio = todas)", obrigatorio=False)
    mostrar_livros(s.buscar_livros(texto, categoria))


def cadastrar_aluno(s):
    aluno = s.cadastrar_aluno(
        perguntar("Matrícula"), perguntar("Nome"), perguntar("Curso"), perguntar("E-mail"),
    )
    print(f"Aluno {aluno['nome']} cadastrado.")


def buscar_aluno(s):
    a = s.buscar_aluno(perguntar("Matrícula"))
    print(f"{a['matricula']} - {a['nome']} | {a['curso']} | {a['email']}")


def emprestar(s):
    e = s.emprestar(perguntar("ISBN"), perguntar("Matrícula"), perguntar_data())
    print(f"Empréstimo registrado (id {e['_id']}). Devolver até {fmt_data(e['data_prevista'])}.")


def devolver(s):
    e = s.devolver(perguntar("Id do empréstimo"), perguntar_data())
    if e["multa"]:
        print(f"Devolvido com atraso. Multa: {fmt_reais(e['multa'])}.")
    else:
        print("Devolvido no prazo, sem multa.")


def listar_emprestimos(s):
    matricula = perguntar("Matrícula")
    s.buscar_aluno(matricula)
    abertos = perguntar("Somente em aberto? (s/n)", obrigatorio=False).lower() == "s"
    emprestimos = s.listar_emprestimos(matricula, apenas_abertos=abertos)
    if not emprestimos:
        print("Nenhum empréstimo.")
    for e in emprestimos:
        mostrar_emprestimo(e)


def rel_top_livros(s):
    linhas = s.top_livros()
    if not linhas:
        print("Nenhum empréstimo registrado.")
    for i, l in enumerate(linhas, 1):
        print(f"{i}. {l['titulo']} ({l['isbn']}) - {l['total']} empréstimo(s)")


def rel_por_curso(s):
    linhas = s.emprestimos_por_curso()
    if not linhas:
        print("Nenhum empréstimo registrado.")
    for l in linhas:
        print(f"{l['curso']}: {l['total']}")


def rel_atrasados(s):
    linhas = s.alunos_com_atraso(perguntar_data())
    if not linhas:
        print("Nenhum empréstimo atrasado.")
    for l in linhas:
        print(f"{l['nome']} ({l['matricula']}) - '{l['livro']}' - {l['dias_atraso']} dia(s) de atraso")


def rel_multas(s):
    print(f"Total arrecadado em multas: {fmt_reais(s.total_multas())}")


ACOES = {
    "1": cadastrar_livro, "2": buscar_livro, "3": lambda s: mostrar_livros(s.listar_livros()),
    "4": atualizar_livro, "5": remover_livro, "6": buscar_livros,
    "7": cadastrar_aluno, "8": buscar_aluno,
    "9": emprestar, "10": devolver, "11": listar_emprestimos,
    "12": rel_top_livros, "13": rel_por_curso, "14": rel_atrasados, "15": rel_multas,
}


def main():
    try:
        servico = BibliotecaService(get_db())
    except PyMongoError as erro:
        print(f"Não foi possível conectar ao MongoDB: {erro}")
        return

    while True:
        print(MENU)
        opcao = input("Opção: ").strip()
        if opcao == "0":
            print("Até logo!")
            break
        acao = ACOES.get(opcao)
        if acao is None:
            print("Opção inválida.")
            continue
        try:
            acao(servico)
        except ErroNegocio as erro:
            print(f"Erro: {erro}")
        except PyMongoError as erro:
            print(f"Erro de banco de dados: {erro}")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nAté logo!")
