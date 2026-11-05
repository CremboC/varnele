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
    "reflexive-only": "džiaugiuosi juokiuosi elgiuosi domiuosi pasidžiaugiau susidomėjau "
                      "didžiuojuosi didžiuotis didžiavausi nesididžiuoju bastausi bastėsi",   # ispell-lt's bare R/O
    "closed classes": "tokių tiems tuos penkių keturis trisdešimties trečiojo vienuolikos",
}

INVALID = ("medžyje jaučie nedžiaugiasi nusipraustis apbūdina gerasias dirbantisis džiaugiu elgiu "
           "besijaudink besijaudinu "   # be-si- without S: participles and gerunds only
           "arklis").split()            # arklys/D is singular: no plural i-stem forms (durys/MK has them)

# a reflexive-only verb has plain forms only with -si-: didžiuoju is the instrumental of didysis, not "I am
# proud"; gėrimas is a drink, not a participle of gėrėtis
NOT_PLAIN_VERB = "didžiuoju didžiuoja elgia gėrimas gėrimo blaivus".split()
SI_PREFIXED = ("nesidomiu nesijuokiu nesidžiaugiu nesielgiu besidžiaugiantis nesididžiuoju "
               "nesijaudink nesijaudinu besijaudinantis").split()   # jaudinti/TRNX: R and N make ne-si- (no S)
# forms ispell-lt also lists with only a reflexive flag (buvo/O, saugo/R): verbs, not particles
NOT_PARTICLE = "buvo saugo būna didžiuotis darbinti".split()

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

    def test_reflexive_only(self):
        for w in NOT_PLAIN_VERB:
            with self.subTest(word=w):
                self.assertFalse([a.tag for a in AN.analyze(w) if a.tag.startswith("V.")
                                  and not a.tag.endswith(".refl") and "si" not in a.prefix])
        for w in SI_PREFIXED:      # ne+si+domiu, a reflexive verb (the object rule leaves it alone)
            with self.subTest(word=w):
                self.assertTrue([a for a in AN.analyze(w) if a.prefix.endswith("si")])

    def test_no_particle_reading(self):
        for w in NOT_PARTICLE:
            with self.subTest(word=w):
                self.assertFalse([a for a in AN.analyze(w) if a.tag == "W"])

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
