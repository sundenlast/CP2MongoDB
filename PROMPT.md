Case- Sistema de empréstimo de livros

Contexto
A biblioteca da faculdade ainda controla os empréstimos numa planilha, e vive acontecendo de emprestarem um livro que já não tem na estante. Sua equipe vai criar o backend do novo sistema, com livros, alunos e empréstimos guardados no MongoDB.

Modelo de dados sugerido
livros: isbn, titulo, autor, ano, categoria, exemplares_total, exemplares_disponiveis
alunos: matricula, nome, curso, email
emprestimos: isbn, matricula, data_emprestimo, data_prevista, data_devolucao (nulo enquanto não devolvido), multa
Requisitos
R1 — Cadastro de livros (CRUD). Cadastrar, buscar por ISBN, listar, atualizar e remover livros. O ISBN não pode se repetir, então use um índice único. Um livro com empréstimo em aberto não pode ser removido.

R2 — Cadastro de alunos. Cadastrar e buscar alunos pela matrícula, que também é única. Validar se o e-mail contém @.

R3 — Busca de livros. Buscar por parte do título ou do autor, sem diferenciar maiúsculas de minúsculas, e filtrar por categoria. Os resultados devem vir ordenados por título.

R4 — Emprestar livro.

Só empresta se houver exemplar disponível.
Cada aluno pode ter no máximo 3 empréstimos em aberto.
Um aluno com empréstimo atrasado não pode pegar outro livro.
O prazo de devolução é de 7 dias.
Ao emprestar, exemplares_disponiveis diminui em 1. Use update_one com filtro exemplares_disponiveis > 0 e $inc, para que dois empréstimos ao mesmo tempo não deixem o estoque negativo.
R5 — Devolver livro. Registrar a data_devolucao e devolver o exemplar ao estoque. Se houver atraso, a multa é de R$ 2,00 por dia. Devolver duas vezes o mesmo empréstimo deve gerar erro.

R6 — Relatórios (Aggregation Pipeline).

Os 5 livros mais emprestados.
A quantidade de empréstimos por curso.
Os alunos com empréstimos atrasados, mostrando nome, livro e dias de atraso.
O total arrecadado em multas.
R7 — Interface. Um menu simples no terminal que permita usar todas as funções acima.

Regras de implementação
Separar o código em camadas: db.py (conexão e índices), service.py (regras de negócio) e main.py (menu).
Usar exceções próprias para os erros de negócio, como LivroIndisponivel, LimiteEmprestimos, AlunoComAtraso e EmprestimoJaDevolvido.
A data atual deve poder ser passada como parâmetro, para que o atraso possa ser testado sem esperar dias.
Entregáveis
Código-fonte organizado em camadas.
Testes com pytest, com pelo menos um teste por requisito de R1 a R6.
Um README.md explicando como rodar o projeto e as principais decisões da equipe.
Um docker-compose.yml subindo o MongoDB, ou instruções para usar o MongoDB Atlas.