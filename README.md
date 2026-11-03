# Pokémon Pokopia — Tradução PT-BR

## Sobre o projeto

Tradução comunitária não oficial de **Pokémon Pokopia** para português brasileiro, por **LucianoNeo**, feita com auxílio de inteligência artificial e revisão manual. Esta versão é destinada ao jogo **2.0.1 e 2.0.1a**. Os nomes dos golpes permanecem em inglês por escolha do projeto.

**Versão do mod: 2.5.1**

| Versão do jogo | Update | Cobertura de localização |
| --- | --- | --- |
| **2.0.1 / 2.0.1a** | `655360` | **100% do conteúdo localizável catalogado** |

⭐ Antes de baixar, dê uma estrela no [repositório](https://github.com/LucianoNeo/pokemon-pokopia-pt-br) para apoiar o projeto.

## Download

[**Baixar a tradução PT-BR v2.5.1 — jogo 2.0.1/2.0.1a (ZIP com instalador)**](https://github.com/LucianoNeo/pokemon-pokopia-pt-br/releases/download/v2.5.1/Pokemon-Pokopia-PT-BR-v2.5.1.zip)

## Conteúdo traduzido

| Versão do jogo | Entradas textuais traduzidas | Imagens/texturas traduzidas |
| --- | ---: | ---: |
| **2.0.1 / 2.0.1a** | **35.533** | **40** |

A cobertura de 100% se refere ao catálogo textual e às imagens identificados para localização no mod. A contagem textual inclui repetições e variantes; exclui campos apenas de pontuação e adaptações de unidades de medida. Nomes oficiais de Pokémon e de golpes permanecem como no jogo.

## Estrutura do pacote

O ZIP contém somente a pasta da versão compatível:

```text
README.md
Pokemon-Pokopia-PT-BR-Installer-v2.5.1.exe
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

### Instalação automática

1. Extraia o ZIP para uma pasta.
2. Execute `Pokemon-Pokopia-PT-BR-Installer-v2.5.1.exe`.
3. Selecione a pasta do jogo, do update ou de `romfs`. O instalador identifica o update **2.0.1/2.0.1a** e usa os arquivos incluídos neste pacote.
4. Feche o jogo antes de aplicar a tradução. O emulador pode continuar aberto se o jogo não estiver rodando. O instalador guarda os arquivos substituídos em `%LOCALAPPDATA%\PokemonPokopiaPTBR\backups`.

### Instalação manual

1. Feche o jogo. O emulador pode continuar aberto se o jogo não estiver rodando.
2. Faça backup dos arquivos correspondentes no RomFS do update **655360**.
3. Copie o conteúdo de `2.0.1/romfs` para a pasta `romfs` do update, substituindo os arquivos correspondentes. A pasta `2.0.1` organiza o ZIP e não deve ser copiada para dentro do RomFS.
4. Mantenha juntos os arquivos `LD_C0_R.BIN` e `LI_C0_R.IDX`, além dos dois arquivos em `motor_asset_re/KIDS_PLATFORM_OUNCE`.
5. Mantenha o idioma do jogo em **inglês** para carregar os textos traduzidos e inicie o jogo novamente.

Para desinstalar, remova o mod ou, se fez a substituição manual, restaure os backups originais.
