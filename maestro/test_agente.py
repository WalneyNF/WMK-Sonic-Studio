import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import agente
import maestro
from partituras import parse_midi

class AgentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name)
        self.output_patch=patch.object(agente,"OUTPUT",self.folder)
        self.output_patch.start()
        self.addCleanup(self.output_patch.stop)
        old=maestro.OUTPUT
        maestro.OUTPUT=self.folder
        self.addCleanup(setattr,maestro,"OUTPUT",old)
        self.file=maestro.compose({"prompt":"música medieval com sanfona e violão","bars":8})["arquivo"]
    def test_preview_then_apply_and_undo_by_original(self):
        preview=agente.plan(self.file,"subir 2 semitons e tempo para 120")
        self.assertEqual(len(preview["acoes"]),2)
        old=(self.folder/self.file).read_bytes()
        result=agente.apply(self.file,preview["acoes"])
        self.assertEqual((self.folder/self.file).read_bytes(),old)
        self.assertNotEqual(result["nova_versao"],self.file)
        imported=parse_midi((self.folder/result["nova_versao"]).read_bytes())
        self.assertEqual(imported["bpm"],120)
        self.assertTrue((self.folder/result["nova_versao"].replace(".mid",".json")).is_file())
    def test_reject_unsafe_command(self):
        with self.assertRaises(ValueError):
            agente.validate([{"tipo":"executar_codigo","codigo":"import os"}],[{"pista":1}])
        with self.assertRaises(ValueError):
            agente.plan("../outro.mid","subir 3 semitons")
    def test_reject_extreme_transposition(self):
        with self.assertRaises(ValueError):
            agente.validate([{"tipo":"transpor","semitons":100}],[{"pista":1}])
if __name__=="__main__":
    unittest.main()
