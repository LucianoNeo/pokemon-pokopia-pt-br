# Pokémon Pokopia — Tradução PT-BR

**Versão 0.0.2 — prévia incompleta**

Esta versão substitui os textos da tabela em inglês do jogo por traduções em português do Brasil. Foi preparada para a versão 1.0.4 do jogo e continua em revisão; alguns textos ainda aparecem em inglês.

## Arquivos incluídos

- `romfs/LD_C0_R.BIN` — textos
- `romfs/LI_C0_R.IDX` — índice correspondente
- `romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0x00011c54.fdata` — textura da tela inicial, com o aviso “APERTE O BOTÃO” e o ícone A.

O ZIP contém somente esses três arquivos modificados. O FDATA pertence ao update 327680; não é necessário ter uma pasta de arquivos base separada.

## Instalação

1. Feche o jogo e o emulador.
2. Faça uma cópia de segurança dos arquivos originais.
3. Extraia o ZIP no mod RomFS associado ao update 327680, preservando a árvore `romfs` e os nomes dos arquivos. Na instalação manual, substitua os arquivos correspondentes dentro da pasta `romfs` do update.
4. Mantenha o idioma do jogo em inglês para carregar a tabela C0 substituída.

Mantenha `LD_C0_R.BIN` e `LI_C0_R.IDX` juntos para carregar os textos. O FDATA também é necessário para traduzir o aviso da tela inicial. Para remover o pacote, retire os três arquivos do mod ou restaure os originais correspondentes.

## Textos ainda pendentes

No menu de serviços mostrado nas capturas, `Challenges`, `Shop` e `Get Items` ainda podem aparecer em inglês; a ocorrência de `Challenges` nas tabelas textuais foi traduzida para **Desafios**, mas essa tela parece usar outra fonte. O aviso da tela inicial agora está em português no atlas do update. O nome de item `Mirror (large)` foi revisado para **Espelho grande**; confirme no jogo se essa é a fonte usada pelo rótulo `Large mirror`.

## Aviso

Projeto comunitário não oficial. Pokémon e os arquivos originais do jogo pertencem aos respectivos detentores. Distribui-se apenas o patch de tradução; mantenha uma cópia legal do jogo e dos arquivos originais.

