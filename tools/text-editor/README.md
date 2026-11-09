# Editor local de textos do Pokopia

Aplicação local para consultar os textos encontrados nos bancos `LD_C0_R.BIN` / `LI_C0_R.IDX`, comparar com outra cópia do RomFS, editar, pesquisar e salvar as mudanças no formato do jogo.

## Abrir

1. Tenha o Python 3 instalado no Windows.
2. Execute `Iniciar_Editor.bat`.
3. O navegador abrirá em `http://127.0.0.1:8765`. A janela do terminal mantém o servidor ativo; feche-a ou pressione `Ctrl+C` para encerrar.
4. Selecione a pasta `romfs` da tradução. Para comparação lado a lado, selecione também a pasta `romfs` original em inglês.

O seletor pode apontar diretamente para `romfs` ou para qualquer pasta que contenha os dois arquivos C0. O jogo/emulador não precisa estar aberto para consultar; feche o jogo antes de salvar se os arquivos estiverem dentro da instalação ativa.

## Uso

- A busca considera texto original em inglês, tradução e posição do banco/linha/campo.
- Os resultados mostram o texto da RomFS de referência e a tradução lado a lado. A lista oculta automaticamente entradas identificadas como idiomas diferentes de inglês e português; nomes próprios e textos curtos ambíguos são mantidos. Sem selecionar uma referência, a coluna de referência fica vazia.
- O botão **Salvar alterações + backup** grava somente os textos editados. Antes de trocar os arquivos, cria `romfs_backup_texteditor_AAAAMMDD_HHMMSS` na pasta imediatamente acima de `romfs`, contendo os BIN e IDX anteriores.
- O editor confere se os arquivos não foram alterados desde a abertura, cria arquivos temporários e decodifica de volta os bancos alterados antes da gravação.
- Se uma alteração muda marcadores como `<...>`, `{...}` ou placeholders, aparece um aviso de revisão. O salvamento continua sob confirmação explícita.

## Escopo e privacidade

O servidor escuta somente em `127.0.0.1`; não envia os arquivos para a internet. Ele varre todos os registros IDX e decodifica as strings UTF-8 em tabelas de texto v2, mas a interface filtra automaticamente idiomas detectados como diferentes de inglês e português brasileiro. O filtro é heurístico, preserva nomes próprios e trechos curtos ambíguos, e não altera nem apaga as entradas ocultas. Bancos que não seguem o formato de tabela v2 também são preservados. A comparação usa o mesmo índice de banco, linha e campo entre as duas cópias.

Por segurança, faça primeiro uma cópia de teste do RomFS. O backup automático permite recuperar o par original de BIN/IDX caso queira desfazer um salvamento.
