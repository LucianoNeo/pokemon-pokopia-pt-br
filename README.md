# Pokémon Pokopia — Tradução PT-BR

## Sobre o projeto

Tradução comunitária não oficial de **Pokémon Pokopia** para português brasileiro, por **LucianoNeo**, feita com auxílio de inteligência artificial e revisão manual.

O projeto mantém patches separados para as versões **1.0.4** e **2.0.1** do jogo. Os nomes dos golpes permanecem em inglês.

**Versão do mod: 2.0.0.**

| Versão do jogo | Update | Disponibilidade |
| --- | --- | --- |
| **1.0.4** | `327680` | Finalizada |
| **2.0.1** | `655360` | Tradução textual concluída: **100% do catálogo em inglês**; revisão manual pendente |

⭐ Antes de baixar, dê uma estrela no [repositório](https://github.com/LucianoNeo/pokemon-pokopia-pt-br) para apoiar o projeto.

## Download

[**Baixar tradução PT-BR 2.0.0 — jogos 1.0.4 e 2.0.1 (ZIP)**](https://github.com/LucianoNeo/pokemon-pokopia-pt-br/releases/download/v2.0.0/Pokemon-Pokopia-PT-BR-v2.0.0.zip)

O pacote publicado da release 2.0.0 inclui as duas versões em pastas separadas e ainda é parcial para a **2.0.1**. **Nesta branch**, a tradução dos textos em inglês catalogados está concluída, preservando nomes oficiais, vocalizações e comandos. O complemento aguarda revisão manual e teste no jogo; ainda não há uma nova release publicada.

### Estrutura do pacote com as duas versões

Cada versão tem sua própria pasta dentro do mesmo ZIP:

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

Instale **somente a pasta correspondente à versão do seu jogo**. Os arquivos das duas versões não devem ser misturados. O ZIP já publicado do mod 1.0.0 mantém a estrutura anterior, com `romfs` diretamente na raiz.

## Traduções no mod

| Versão do jogo | Entradas textuais traduzidas | Imagens/texturas traduzidas |
| --- | ---: | ---: |
| **1.0.4** | **30.826** | **36** |
| **2.0.1** | **100% do catálogo textual em inglês** | **40** |

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
   - No ZIP anterior do mod **1.0.0**, use a pasta `romfs` da raiz, exclusiva da **1.0.4**.
3. Faça backup dos arquivos correspondentes no RomFS do update escolhido. Copie apenas a pasta `romfs` da versão selecionada para a pasta do mod. Na instalação manual, copie o conteúdo dessa `romfs` para a `romfs` do update, substituindo os arquivos correspondentes. As pastas `1.0.4` e `2.0.1` servem para organizar o ZIP; não são copiadas para dentro do RomFS.
4. Instale os pares de arquivos juntos:
   - `romfs/LD_C0_R.BIN` e `romfs/LI_C0_R.IDX`.
   - `romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/root.rdb` e `romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0x4b13d561.fdata`.
5. Mantenha o idioma do jogo em **inglês** para carregar os textos traduzidos e inicie o jogo novamente.

Para desinstalar, remova o mod ou, se fez a substituição manual, restaure os backups originais.
