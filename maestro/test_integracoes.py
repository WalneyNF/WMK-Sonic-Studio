import tempfile, unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import integracoes

class IntegrationTests(unittest.TestCase):
    def test_suno_prompt_musical(self):
        x=integracoes.suno_prompt("RPG medieval com sanfona e violão",95)
        self.assertIn("accordion",x["estilo_sugerido"])
        self.assertIn("acoustic guitar",x["estilo_sugerido"])
        self.assertIn("95 BPM",x["estilo_sugerido"])
        self.assertIn("Instrumental",x["letra_ou_instrucoes"])
    def test_invalid_bpm(self):
        with self.assertRaises(ValueError):integracoes.suno_prompt("Aventura",500)
    def test_cli_conversion_mock(self):
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/"origem.mid";src.write_bytes(b"MThd")
            dst=Path(tmp)/"partitura.musicxml"
            exe=Path(tmp)/"musescore.exe";exe.write_bytes(b"test")
            def fake_run(args,**kwargs):
                dst.write_text("<score-partwise></score-partwise>")
                return MagicMock(returncode=0,stdout="",stderr="")
            with patch.object(integracoes.subprocess,"run",side_effect=fake_run) as run:
                x=integracoes.convert(src,dst,str(exe))
                self.assertTrue(dst.exists())
                self.assertEqual(Path(x["saida"]),dst.resolve())
                self.assertIn("-o",run.call_args.args[0])
                self.assertFalse(run.call_args.kwargs.get("shell",False))
    def test_invalid_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/"app.exe";f.write_bytes(b"abc")
            with self.assertRaises(ValueError):
                integracoes.convert(f,Path(tmp)/"out.pdf")
if __name__=="__main__":unittest.main()
