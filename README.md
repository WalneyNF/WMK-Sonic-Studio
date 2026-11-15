# WMK Sonic Studio 🎧

**Estúdio de produção musical para criar trilhas, efeitos e músicas para jogos.**

Fork do [LYNX SHARE](https://github.com/Ka1-S/LYNX-SHARE), desenvolvido em C++20/JUCE 8, sob licença **AGPL-3.0**. Projeto em fase **alfa**.

**Projeto WMK:** Walney Moreira Klein — walneyk@hotmail.com.

## Funcionalidades da base
- Channel Rack, Piano Roll, Playlist e Mixer.
- Edição MIDI, sintetizadores, sampler e SoundFonts SF2/SF3/SFZ.
- Plugins VST3/CLAP, efeitos, gravação, automação e exportação de áudio.
- Importação de projetos FL Studio e Ableton Live, com limitações de compatibilidade.
- Perfis de interface, salvamento automático e opções de colaboração.

## Tradução
**Português do Brasil já existe** no arquivo `resources/i18n/pt-BR.txt`. Para avaliar cobertura e erros:
```bash
python tools/i18n_tool.py status
python tools/i18n_tool.py lint pt-BR
```
No aplicativo, selecione **Português (Brasil)** nas configurações de idioma.

## Windows: GitHub Actions
[Actions](https://github.com/WalneyNF/WMK-Sonic-Studio/actions) • [Releases](https://github.com/WalneyNF/WMK-Sonic-Studio/releases)

O workflow existente `.github/workflows/release.yml` prevê compilação e geração de pacotes. Enquanto a migração de nomes técnicos não for concluída, o alvo CMake e o executável interno continuam como `LYNX` e `LYNX.exe` para preservar os scripts de build. Uma compilação ainda precisa ser validada no fork.

## WMK Maestro IA (novo protótipo)

- [Abrir compositor IA local e instruções](maestro/README.md)
- [Interface do compositor](maestro/index.html) — executar via servidor Python local
- [Código do gerador MIDI](maestro/maestro.py)

## Manuais WMK
- [Manual de iniciação musical e trilhas para jogos](manual.html)
- [Roadmap de evolução](roadmap.html)
- [Pesquisa e comparação de DAWs](pesquisa.html)
- [Status técnico herdado](docs/STATUS.md)
- [Licenças de terceiros](THIRD_PARTY.md)

## Licença e créditos
O código derivado é distribuído sob a [GNU AGPL-3.0](LICENSE). Você pode usar, estudar, modificar, distribuir e comercializar respeitando suas condições, incluindo a disponibilização do código-fonte correspondente quando exigida. O autor original, demais colaboradores e suas atribuições devem permanecer reconhecidos. Serviços online e endereços do projeto original ainda exigem auditoria antes de uma publicação WMK.
## Leitor de Partituras + Professor Musical (experimental)

- [Interface do leitor de partituras](maestro/partituras.html) — acessível com o servidor local ativo.
- [Manual do leitor e formatos](maestro/LEITOR_PARTITURAS.md).
- [Roadmap de evolução](roadmap.html).

**Formatos iniciais:** MusicXML/MXL e MIDI. PDFs, imagens e arquivos MSCZ diretos ainda não são suportados.

## WMK Music Bridge — MuseScore e Suno

- [Painel de integração](maestro/integracoes.html) — após iniciar o serviço Python em `127.0.0.1:8768`.
- [Conversor de arquivos pelo MuseScore instalado](maestro/integracoes.py).
- [Roadmap completo](roadmap.html).

O conversor é executado **no seu computador** e usa a instalação local do MuseScore Studio. O painel monta prompts para o Suno, mas **não utiliza API não oficial nem baixa músicas automaticamente**. Use áudio somente quando houver licença e download permitidos, especialmente em jogos comerciais.

No Windows: `py -3 maestro/maestro.py`, depois `http://127.0.0.1:8768/integracoes.html`.
