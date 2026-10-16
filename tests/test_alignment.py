import importlib.util,unittest,tempfile,pathlib
spec=importlib.util.spec_from_file_location('alignment',str(pathlib.Path(__file__).resolve().parents[1]/'build_alignment.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class TestAlignment(unittest.TestCase):
 def test_book_case_and_non_numeric(self):
  xml='<TEI><text><body><div type="textpart" subtype="Book" n="1"><div type="textpart" subtype="chapter" n="132"><div type="textpart" subtype="section" n="1"><p>Magus.</p></div><div type="textpart" subtype="section" n="prol"><p>Prologue.</p></div></div></div></body></text></TEI>'
  with tempfile.TemporaryDirectory() as d:
   f=pathlib.Path(d)/'test.xml'; f.write_text(xml)
   self.assertEqual(m.parts(f),[('1','132','1','Magus.')])
if __name__=='__main__':unittest.main()
