"""Regression tests: python3 -m unittest discover tests"""

import unittest

from varnele.analyzer import Analyzer
from varnele.suggest import Suggester

AN = Analyzer()
SG = Suggester(AN)

VALID = {
    "nouns": "medžio medyje medžių akies akių akmens akmenyje sesers dukters svečias svečio "
             "svetyje abstrakcijos Vilniaus Lietuvoje žmonių žmogaus mėnesio šuns vėjyje bičių",
    "adjectives": "gerojo geresnis geriausias gerai geriau gražiojo gražų gražiai gražesnė "
                  "kiečiausias žaliąjį medinė",
    "verbs": "jaučiu jauti jaučiasi jautė jaučiau jausiu jaustų jausdamas mačiau matys nešiu neš "
             "bėk bėkite buvo buvome bus esame esu nėra yra dirbdavo dirbtų",
    "participles": "jaučiantis jaučiančio mačiusi matęs nešusi dirbantis dirbančio dirbantysis "
                   "dirbęs dirbusi dirbamas dirbtas dirbtinas",
    "verbal nouns": "matymas nešimas buvimas abejojimas",
    "prefixes": "nusiprausė neapsimoka nesijaučia apibūdina neapibūdina",
    "reflexive-only": "džiaugiuosi juokiuosi elgiuosi domiuosi pasidžiaugiau susidomėjau",
    "closed classes": "tokių tiems tuos penkių keturis trisdešimties trečiojo vienuolikos",
}

INVALID = "medžyje jaučie nedžiaugiasi nusipraustis apbūdina gerasias dirbantisis".split()

SPOKEN = {"valgyt": "valgyti", "buvom": "buvome", "jaučias": "jaučiasi", "mokykloj": "mokykloje",
          "namuos": "namuose", "dirbkit": "dirbkite", "eime": "eikime"}

FIXES = {"sviesa": "šviesa", "ivikis": "įvykis", "isvaziavo": "išvažiavo",
         "nesidziaugia": "nesidžiaugia", "vilniaus": "Vilniaus", "rasyt": "rašyti",
         "sita": "šita", "turetu": "turėtų"}   # y is its own key: not syta


class Morphology(unittest.TestCase):
    def test_valid_forms(self):
        for group, words in VALID.items():
            for w in words.split():
                with self.subTest(group=group, word=w):
                    self.assertTrue(AN.analyze(w), f"{w} should be accepted")

    def test_invalid_forms(self):
        for w in INVALID:
            with self.subTest(word=w):
                self.assertEqual(AN.check(w).status, "unknown")

    def test_spoken(self):
        for short, full in SPOKEN.items():
            with self.subTest(word=short):
                r = AN.check(short)
                self.assertEqual(r.status, "colloquial")
                self.assertIn(full, r.formal)

    def test_suggestions(self):
        for bad, good in FIXES.items():
            with self.subTest(word=bad):
                self.assertIn(good, SG.suggest(bad)[:3])


if __name__ == "__main__":
    unittest.main()
