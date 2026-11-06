# Instalador PT-BR

O instalador independente `Pokemon-Pokopia-PT-BR-Installer-v2.5.5.exe` aplica a tradução da versão 2.0.1. Ele não exige Python para ser executado.

## Formatos aceitos

- **Pasta do jogo/update ou `romfs`:** substitui os quatro arquivos traduzidos e guarda cópias dos arquivos atuais em `%LOCALAPPDATA%\PokemonPokopiaPTBR\backups`.
- **Arquivo NUP:** localiza o update 655360 de Pokémon Pokopia dentro do contêiner e cria uma nova cópia traduzida, por padrão com o sufixo `-PTBR`. O NUP de origem é preservado. Os outros pacotes e dados do contêiner são mantidos.
- **Arquivo NSP:** os arquivos NCA do NSP são criptografados, então o instalador não altera o NSP. Em vez disso, instala a tradução como mod LayeredFS em `user\load\0400A3A01EE4C000\romfs` no perfil do Eglantine selecionado. O NSP original fica intacto.

Para a instalação por NSP, selecione a pasta `user` do Eglantine quando o instalador pedir. Se selecionar a própria pasta `load`, o instalador também reconhece esse caso. A identificação interna de versão/título do NSP criptografado não é possível; use o NSP de Pokémon Pokopia 2.0.1.

O instalador pode usar os arquivos de tradução incluídos na pasta/ZIP da release. Se o executável estiver sozinho, baixa como alternativa o pacote de tradução PT-BR v2.5.5.

## Compilar no Windows

Com Python 3.12 instalado, execute:

```powershell
.\tools\installer\build.ps1 -OutputDirectory C:\caminho\de\saida
```

O script prepara um ambiente temporário, instala PyInstaller e gera o executável independente `Pokemon-Pokopia-PT-BR-Installer-v2.5.5.exe`.
