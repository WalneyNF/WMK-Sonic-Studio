# WMK Maestro IA — protótipo funcional (prioridade máxima)

Este módulo gera **MIDI multitrilha real** a partir de pedidos em português. O usuário pode baixar o resultado e abrir no **WMK Sonic Studio** pelo menu File > Open (.mid). Não há ainda integração nativa ao C++ ou áudio no navegador.

## Windows (Python 3.10 ou superior)
Abra PowerShell na pasta `maestro`:
```powershell
py -3 maestro.py
```
Acesse **http://127.0.0.1:8768** no navegador. Clique em **Criar minha música** e baixe o arquivo .mid.

- **Sem IA externa:** modo local baseado em regras gera melodias, acompanhamento, baixo e percussão.
- **Com Ollama:** marque a opção na página, instale/execute Ollama em `127.0.0.1:11434` e baixe um modelo configurado. A IA interpreta o pedido; o gerador musical ainda é baseado em regras.
- Os arquivos MIDI e o resumo JSON ficam em `maestro/composicoes/` (não são enviados à Internet).
- O serviço escuta apenas em `127.0.0.1`. Não exponha a porta à Internet.

## Limitações atuais
A qualidade musical é **experimental**; ritmos, articulações e harmonia requerem aperfeiçoamento. Os nomes de instrumentos são sugestões MIDI General MIDI: para ouvir timbres realistas, associe SoundFonts SF2/SF3/SFZ ou plugins na DAW. Nenhum som comercial ou biblioteca de terceiros é distribuído aqui. O MIDI não contém áudio.

## Testes
```powershell
py -3 -m unittest discover -s maestro -p "test_*.py"
```

## Ler partituras e estudar notas

Abra [Leitor de Partituras](partituras.html) com o servidor iniciado (URL: http://127.0.0.1:8768/partituras.html).

Documentação: [LEITOR_PARTITURAS.md](LEITOR_PARTITURAS.md). Formatos iniciais: .musicxml, .xml, .mxl, .mid, .midi.
