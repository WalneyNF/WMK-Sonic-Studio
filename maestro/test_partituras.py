"""Testes automáticos para importação MIDI, MusicXML e MXL."""
import io, struct, unittest, zipfile
import partituras

SAMPLE=b"""<?xml version='1.0' encoding='utf-8'?>
<!DOCTYPE score-partwise  PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">
<score-partwise version="4.0">
<work><work-title>Vila Musical</work-title></work>
<part-list><score-part id="P1"><part-name>Sanfona</part-name></score-part></part-list>
<part id="P1"><measure number="1">
<attributes><divisions>4</divisions><time><beats>4</beats><beat-type>4</beat-type></time></attributes>
<note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration><type>quarter</type></note>
<note><chord/><pitch><step>E</step><octave>4</octave></pitch><duration>4</duration><type>quarter</type></note>
<note><pitch><step>G</step><octave>4</octave></pitch><duration>4</duration><type>quarter</type></note>
</measure></part></score-partwise>"""

class ScoreTests(unittest.TestCase):
    def test_musicxml_to_midi(self):
        score=partituras.parse_musicxml(SAMPLE,"tema.musicxml")
        self.assertEqual(score["total_notas"],3)
        self.assertEqual(score["instrumentos"][0]["instrumento"],"Sanfona")
        self.assertEqual(score["instrumentos"][0]["notas"][0]["midi"],60)
        self.assertEqual(score["instrumentos"][0]["notas"][1]["inicio"],0)
        midi=partituras.to_midi(score)
        self.assertTrue(midi.startswith(b"MThd"))
        parsed=partituras.parse_midi(midi)
        self.assertEqual(parsed["total_notas"],3)
    def test_mxl(self):
        out=io.BytesIO()
        with zipfile.ZipFile(out,"w") as z:
            z.writestr("score.xml",SAMPLE)
        score=partituras.parse_musicxml(out.getvalue(),"partitura.mxl")
        self.assertEqual(score["titulo"],"Vila Musical")
    def test_limits(self):
        with self.assertRaises(ValueError): partituras.parse_musicxml(b"x"*3_000_000)
        with self.assertRaises(ValueError): partituras.parse_midi(b"nao midi")
    def test_teacher(self):
        n=partituras.explain_note({"midi":60,"nota":"Dó4"})
        self.assertIn("Dó",n["explicacao"])
if __name__=="__main__":unittest.main()
