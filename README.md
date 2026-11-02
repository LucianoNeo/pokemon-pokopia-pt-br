# Pokémon Pokopia — Tradução PT-BR

## Sobre o projeto

Tradução comunitária não oficial de **Pokémon Pokopia** para português brasileiro, por **LucianoNeo**, feita com auxílio de inteligência artificial e revisão manual. O mod traz versões separadas para os jogos **1.0.4** e **2.0.1**. Os nomes dos golpes permanecem em inglês por escolha do projeto.

**Versão do mod: 2.1.0**

| Versão do jogo | Update | Cobertura de localização |
| --- | --- | --- |
| **1.0.4** | `327680` | **100% do conteúdo localizável catalogado** |
| **2.0.1** | `655360` | **100% do conteúdo localizável catalogado** |

⭐ Antes de baixar, dê uma estrela no [repositório](https://github.com/LucianoNeo/pokemon-pokopia-pt-br) para apoiar o projeto.

## Download

[**Baixar a tradução PT-BR v2.1.0 — jogos 1.0.4 e 2.0.1 (ZIP)**](https://github.com/LucianoNeo/pokemon-pokopia-pt-br/releases/download/v2.1.0/Pokemon-Pokopia-PT-BR-v2.1.0.zip)

## Conteúdo traduzido

| Versão do jogo | Entradas textuais traduzidas | Imagens/texturas traduzidas |
| --- | ---: | ---: |
| **1.0.4** | **30.826** | **36** |
| **2.0.1** | **35.533** | **40** |

A cobertura de 100% se refere ao catálogo textual e às imagens identificados para localização no mod. As contagens textuais incluem repetições e variantes; excluem campos apenas de pontuação e adaptações de unidades de medida. Nomes oficiais de Pokémon e de golpes permanecem como no jogo.

## Estrutura do pacote

Cada versão tem sua própria pasta dentro do ZIP. Instale somente a correspondente à versão do jogo:

```text
README.md
1.0.4/
└── romfs/
    ├── LD_C0_R.BIN
    ├── LI_C0_R.IDX
    └── motor_asset_re/
        └── KIDS_PLATFORM_OUNCE/
            ├── root.rdb
            └── 0x4b13d561.fdata
2.0.1/
└── romfs/
    ├── LD_C0_R.BIN
    ├── LI_C0_R.IDX
    └── motor_asset_re/
        └── KIDS_PLATFORM_OUNCE/
            ├── root.rdb
            └── 0x4b13d561.fdata
```

## Imagens de exemplo

![Coleção de carimbos em português](docs/previews/v0.0.6/colecao-carimbos.png)

![Culinária em português](docs/previews/v0.0.6/culinaria.png)

![Desafios diários em português](docs/previews/v0.0.6/desafios-diarios.png)

![Inventário e banco de tronco em português](docs/previews/v0.0.6/inventario-banco-tronco.png)

## Instalação

1. Feche o jogo. O emulador pode continuar aberto se o jogo não estiver rodando.
2. Confira a versão do jogo e escolha a pasta correspondente no ZIP:
   - Jogo **1.0.4**: `1.0.4/romfs`, para o update **327680**.
   - Jogo **2.0.1**: `2.0.1/romfs`, para o update **655360**.
3. Faça backup dos arquivos correspondentes no RomFS do update escolhido. Copie apenas a pasta `romfs` da versão selecionada para a pasta do mod. Na instalação manual, copie o conteúdo dessa `romfs` para a `romfs` do update, substituindo os arquivos correspondentes. As pastas `1.0.4` e `2.0.1` organizam o ZIP e não devem ser copiadas para dentro do RomFS.
4. Instale os pares de arquivos juntos:
   - `romfs/LD_C0_R.BIN` e `romfs/LI_C0_R.IDX`.
   - `romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/root.rdb` e `romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0x4b13d561.fdata`.
5. Mantenha o idioma do jogo em **inglês** para carregar os textos traduzidos e inicie o jogo novamente.

Para desinstalar, remova o mod ou, se fez a substituição manual, restaure os backups originais.
