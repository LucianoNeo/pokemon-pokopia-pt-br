# Instalador PT-BR

O instalador independente `Pokemon-Pokopia-PT-BR-Installer-v2.5.5.exe` aplica a tradução da versão 2.0.1. Ele não exige Python para ser executado.

## Formatos aceitos

- **Pasta do jogo/update ou `romfs`:** substitui os quatro arquivos traduzidos e guarda cópias dos arquivos atuais em `%LOCALAPPDATA%\PokemonPokopiaPTBR\backups`.
- **Arquivo NUP:** localiza o update 655360 de Pokémon Pokopia dentro do contêiner e cria uma nova cópia traduzida, por padrão com o sufixo `-PTBR`. O NUP de origem é preservado. Os outros pacotes e dados do contêiner são mantidos.
- **Arquivo NSP:** os arquivos NCA do NSP são criptografados, então o instalador não altera o NSP. Em vez disso, instala a tradução como mod LayeredFS em `user\load\0400A3A01EE4C000\romfs` no perfil do Eglantine selecionado. O NSP original fica intacto.

### Como localizar a pasta do Eglantine para um NSP

O instalador não altera o NSP, pois seus arquivos internos são criptografados. Ele instala a tradução como mod LayeredFS no perfil do Eglantine selecionado.

1. Abra a mesma cópia do Eglantine que você usa para iniciar Pokémon Pokopia.
2. No menu, clique em **File → Open Eglantine Folders → Mod Folder**. O Explorador abrirá a pasta `load` correta para esse perfil.
3. Quando o instalador pedir uma pasta, selecione essa pasta `load`.
4. Os arquivos serão instalados em `load\0400A3A01EE4C000\romfs`. Inicie o jogo usando essa mesma cópia/perfil do Eglantine.

Para localizar manualmente, clique com o botão direito no atalho do Eglantine e escolha **Abrir local do arquivo**. Se houver uma pasta `user` ao lado de `eglantine.exe`, use `<pasta do Eglantine>\user\load`. Sem essa pasta portátil, o perfil costuma estar em `%APPDATA%\eden\load`; pressione **Win + R**, digite `%APPDATA%\eden\load` e pressione Enter.

Se você mantém várias instalações do Eglantine, abra **Mod Folder** na instalação usada para jogar. Cada instalação pode usar um perfil diferente. A identificação interna de versão/título do NSP criptografado não é possível; use o NSP de Pokémon Pokopia 2.0.1.

O instalador pode usar os arquivos de tradução incluídos na pasta/ZIP da release. Se o executável estiver sozinho, baixa como alternativa o pacote de tradução PT-BR v2.5.5.

## Compilar no Windows

Com Python 3.12 instalado, execute:

```powershell
.\tools\installer\build.ps1 -OutputDirectory C:\caminho\de\saida
```

O script prepara um ambiente temporário, instala PyInstaller e gera o executável independente `Pokemon-Pokopia-PT-BR-Installer-v2.5.5.exe`.
