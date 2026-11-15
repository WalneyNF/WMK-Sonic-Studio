import unittest, tempfile
from pathlib import Path
import maestro
class MaestroTests(unittest.TestCase):
    def test_vlq(self):
        self.assertEqual(maestro.vlq(128), b'\x81\x00')
    def test_midi_multitrack(self):
        with tempfile.TemporaryDirectory() as d:
            original = maestro.OUTPUT
            maestro.OUTPUT = Path(d)
            try:
                result = maestro.compose({"prompt":"Música medieval com sanfona e violão, 95 BPM", "bars":8})
                midi = (Path(d)/result["arquivo"]).read_bytes()
                self.assertTrue(midi.startswith(b"MThd"))
                self.assertIn(b"MTrk", midi)
                self.assertGreaterEqual(len(result["instrumentos"]), 3)
                self.assertTrue((Path(d)/result["arquivo"].replace(".mid",".json")).is_file())
            finally:
                maestro.OUTPUT = original
    def test_bad_request(self):
        with self.assertRaises(ValueError):
            maestro.compose({"prompt":"oi", "bpm":999})
if __name__ == "__main__":
    unittest.main()
