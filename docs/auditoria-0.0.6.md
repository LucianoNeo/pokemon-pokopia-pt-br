# Auditoria de cobertura — tradução 0.0.6

## Resultado desta revisão

- 1.616 entradas revisadas/aplicadas neste ciclo. A contagem inclui variantes, nomes de locais e campos numéricos; não representa esse número de frases inéditas.
- Tabelas antes ausentes: preferências de habitat, roupas, acessórios, penteados, gestos, filtros da câmera, categorias de itens, brindes, formas e categorias da Pokédex, e nomes de Ilhas dos Sonhos.
- Duas tabelas de locais reconstruídas com dois ponteiros relativos por registro de 12 bytes, preservando seus metadados. Incluem nomes e formas usadas dentro de frases.
- Alturas e pesos da tabela inglesa passaram a usar os valores métricos originais do jogo, com vírgula decimal; não houve conversão a partir de valores imperiais arredondados.
- Corrigidos sufixos ingleses ligados a campos dinâmicos, como `ing`, `ed` e possessivos, e frases com o início “Às vezes” incompleto. Também foram ajustados títulos de ajuda, interjeições e falas identificadas durante essa conferência.
- Dez falas de introdução encontradas numa tabela antiga, versão 0, foram traduzidas e incluídas na geração do patch.

## Cobertura registrada

| Área | Leitura realizada |
| --- | --- |
| Pasta do jogo | 28 arquivos inventariados, com tratamento individual no CSV |
| Índice do BIN | 23.565 posições alinhadas examinadas; 9.678 pares distintos |
| Contêineres do BIN | 7.216 blocos decodificados, incluindo cabeçalhos maiores e trechos sem compressão |
| Dados crus indexados | 1.760 blocos lidos, sem nova tabela de texto confirmada; mais 702 entradas de zero ou um byte |
| Tabelas versão 2 | 2.644 estruturas registradas, incluindo tabelas pequenas e de outros idiomas |
| Idiomas | 245 grupos de nove idiomas reconhecidos; o inglês é identificado também pela posição no grupo |
| Bancos de destino | 254 bancos; 33.810 campos textuais referenciados conferidos |
| Arquivos `.fdata` | 12 arquivos; 71.247 recursos; 15.17 GB descompactados |
| Executáveis | `main`, `rtld`, `sdk` e `subsdk0`: segmentos descompactados e checksums internos conferidos |
| Áudio e metadados | Dois arquivos IDRK/TSRS/KTSR e arquivos RDB/RDX/NPDM examinados por strings ASCII/UTF-16 |

Nos bancos de destino conferidos: **zero ponteiros sem resolução e zero divergências nos metadados verificados**. A leitura dos recursos `.fdata` terminou com **zero erros de descompressão**. A busca nesses recursos não confirmou novos textos de interface entre os candidatos; encontrou nomes internos, identificadores e fragmentos de dados.

## Conteúdo mantido

Nomes de Pokémon, nomes de golpes, marcas, identificadores técnicos, licenças e vocalizações próprias dos Pokémon podem continuar iguais ao original. Termos válidos em português, como “Normal”, “Total”, “Menu” e “DJ”, também não precisam ser substituídos. As especialidades de ações e os nomes comuns de itens são traduzidos conforme seu contexto.

O catálogo distingue os registros de texto comuns, com 8 bytes; os pares de nomes de locais/habitats, com 12 bytes; e as seis formas dos nomes de itens, com 32 bytes. As correções foram incorporadas ao processo de geração para evitar que uma reconstrução volte à leitura anterior.

## Limites da auditoria

Esta é uma auditoria de arquivos, estruturas e strings. **Ainda depende de teste dentro do jogo** para confirmar encaixe, contexto e execução de todas as cenas. A ausência de candidatos na busca não comprova ausência absoluta de inglês.

Não houve novo OCR das imagens ou dos quadros dos dois vídeos `.webm` nesta revisão textual. A cópia `.restore-tmp` foi identificada como backup inativo. Ela não representa o conteúdo carregado pelo jogo.

## Evidências

- [Cobertura por arquivo](cobertura-arquivos-0.0.6.csv)
- [Cobertura dos pares indexados](cobertura-bancos-0.0.6.csv)

Os relatórios detalhados, listas de candidatos, planos de revisão e backups estão preservados no diretório de trabalho `pokopia_coverage_v2_20261101`.

O par BIN/IDX foi aplicado à pasta do jogo, à cópia de teste e ao repositório local. Os backups originais foram preservados. Versão mantida em **0.0.6**, sem commit ou release nesta etapa.
