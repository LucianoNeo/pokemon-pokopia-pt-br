# Instalador PT-BR

O instalador reconhece as versões **1.0.4** e **2.0.1**. Extraia o ZIP da
release v2.2.0 e execute `Pokemon-Pokopia-PT-BR-Installer-v2.2.0.exe`. Ele usa
as pastas de tradução incluídas no pacote; não precisa baixar o ZIP novamente.
Também é possível selecionar a pasta do jogo, do update ou de `romfs`.

Antes de substituir os arquivos do jogo, o programa cria backups em:

`%LOCALAPPDATA%\PokemonPokopiaPTBR\backups`

Se o instalador for executado sem as pastas de tradução ao lado, ele baixa e
confere o pacote oficial v2.1.0 como alternativa.

## Compilar no Windows

Com Python 3.12 instalado, execute:

```powershell
.\tools\installer\build.ps1 -OutputDirectory C:\caminho\de\saida
```

O script prepara um ambiente virtual temporário, instala PyInstaller e gera o
executável independente `Pokemon-Pokopia-PT-BR-Installer-v2.2.0.exe`.
