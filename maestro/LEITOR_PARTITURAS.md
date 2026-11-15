# Leitor de Partituras — WMK Maestro IA

Primeira versão experimental da importação de partituras.

## Como abrir
Abra um terminal na pasta raiz do repositório:

```powershell
py -3 maestro/maestro.py
```

Acesse **http://127.0.0.1:8768/partituras.html**.

Escolha um arquivo `.musicxml`, `.xml`, `.mxl`, `.mid` ou `.midi`. Após a leitura, o sistema mostra instrumentos, andamento e primeiras notas. MusicXML/MXL pode ser convertido para arquivo MIDI com um botão de download.

- Para arquivos `.mscz`, abra primeiro no **MuseScore Studio** e exporte como **MusicXML**.
- Para ouvir instrumentos com timbres reais, importe o MIDI no WMK Sonic Studio e configure SoundFonts ou VST3/CLAP apropriados.
- O professor básico identifica nome, oitava e duração de notas. Ainda não existe IA conversacional nesta tela.
- PDF e imagens exigem tecnologia **OMR**; não estão implementados.
- Ainda não são preservados repetições, articulações, dinâmicas, ligaduras e outros símbolos avançados. A exportação MIDI usa timbre padrão; a seleção do instrumento precisa ser feita na DAW.
- Apenas arquivos de até 1 MB podem ser enviados pela interface. O servidor funciona apenas em `127.0.0.1`.

## Testar

```powershell
py -3 -m unittest discover -s maestro -p "test_*.py" -v
```

## Segurança e privacidade
Não expor a porta local à internet. O leitor não requer serviços de IA pagos, nem envia seus arquivos para terceiros. Respeite os direitos autorais de partituras obtidas na internet.

## Créditos
Walney Moreira Klein — walneyk@hotmail.com. Fork do LYNX SHARE sob AGPL-3.0.
