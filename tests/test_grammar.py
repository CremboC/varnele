"""Context rules: python3 -m unittest discover tests"""

import unittest

from varnele.__main__ import Checker

CK = Checker()


def findings(text):
    return {(f.word, f.rule): f.suggestions for f in CK.check_text(text)}


# (sentence, word, rule, expected first suggestion)
FLAGGED = [
    ("Grįžau prieš pora dienų.", "pora", "case", "porą"),
    ("Nuėjome į didele kavine.", "didele", "case", "didelę"),
    ("Nuėjome į didele kavine.", "kavine", "case", "kavinę"),
    ("Kalbėjome apie nauja knyga.", "knyga", "case", "knygą"),
    ("Ten buvo daug vaiku.", "vaiku", "quantity", "vaikų"),
    ("Radome gražią kavine.", "kavine", "agreement", "kavinę"),
    ("Jis sakė kad nebus.", "kad", "comma", ", kad"),
    ("Tai žmogus su kuriuo dirbau.", "su", "comma", ", su"),
    ("Neateisiu nes sergu.", "nes", "comma", ", nes"),
    ("Gaminys buvo prastos kokybes.", "kokybes", "agreement", "kokybės"),
    ("Dizainas nesikeitė daugybę metu.", "metu", "quantity", "metų"),
    ("Neturiu laiką.", "laiką", "negation", "laiko"),
    ("Nemačiau jį vakar.", "jį", "negation", "jo"),
    ("Nevalgau mėsą.", "mėsą", "negation", "mėsos"),
    ("Aš buvo namie.", "buvo", "subject", "buvau"),
    ("Tu eina namo.", "eina", "subject", "eini"),
    ("Mes skaito knygas.", "skaito", "subject", "skaitome"),
    ("Jis einu namo.", "einu", "subject", "eina"),
    ("Vakar mačiau namas.", "namas", "object", "namą"),
    ("Nusipirkau naujas automobilis.", "automobilis", "object", "automobilį"),
    ("Radau nukritusią sagute.", "sagute", "agreement", "sagutę"),
    ("Pagrindinė kylanti grėsme yra kirtimai.", "grėsme", "agreement", "grėsmė"),
    ("Kodėl nepataiso visu žodžių?", "visu", "negation", "visų"),
    ("Kodėl nepataiso žodžių kuriu aš rašau?", "kuriu", "relative", "kurių"),
    ("Kodėl nepataiso visų zodzou?", "zodzou", "unknown", "žodžių"),
    # unknown word: context picks the suggestion order
    ("Grįžau prieš porą dienu.", "dienu", "unknown", "dienų"),
    ("Vakar pries porą dienų.", "pries", "unknown", "prieš"),
]

CORRECT = [
    "Grįžau prieš porą dienų.",
    "Nuėjome į didelę kavinę prie upės.",
    "Ten buvo daug vaikų ir keletas suaugusiųjų.",
    "Bet kas gali ateiti, o kai kurie liks.",
    "Kas nors paskambins, kai kas nors sužinos.",
    "Namas per didelis.",
    "Iš Vilniaus atvažiavo dešimt žmonių.",
    "Jis sakė, kad nebus, nes serga.",
    "Tai žmogus, su kuriuo dirbau.",
    "Kalbėjau su geru draugu apie naują knygą.",
    "Ir kad ir kaip būtų, net jei lis, eisime.",
    # found on Wikipedia while tuning: genitive modifiers, participles, idioms
    "Bendradarbiavo su lietuvių kultūros draugija ir su teisininkų padėjėja.",
    "Įstojo į teisės mokyklą, o paskui informacija nutrūko.",
    "Apie pusė nelaimingų įvykių yra traumos.",
    "Prie stebuklingu laikomo šaltinio stovi koplyčia.",
    "Per šešiolika mėnesių aplankė daug mažų ežerėlių.",
    "Euromaidano metu palaikė opozicijos pusę.",
    "Seserys viena kitą papildė, nors ir nedaug.",
    "Tuo metu žinomas, kuriam laikui tapo vadovu bet kokioms bausmėms.",
    "Karą nutraukė profesorių O. Mauserio darbai.",
    # verb rules: durations, copulas, homonyms of verbs
    "Nedirbau visą dieną. Nebuvo laiko. Aš nesu mokytojas. Esu studentas.",
    "Dizainas nesikeitė daugybę metų.",
    "Lietuvai atiteko tik nedidelis ruožas. Atskiri ruožai skirti slidininkams.",
    "Tuo metu miestas buvo atstatytas. Keli pastatai išliko.",
    "Aš nemačiau jo, o tu matei mane.",
    # participles with objects or predicates, not agreeing attributes
    "Ji, praėjusi advokatūrą, pradėjo dirbti. Užuot pasirašiusi memorandumą, išvyko.",
    "Matėme tapusią vienuole seserį. Jis išrinktas prezidentu, vadinamas tėvu, laikomas didvyriu.",
    "Tai veiksmažodis, išreiškianti liepimą forma.",
    "Forma, einanti sakinio gale kaip tarinys. Esantis mieste namas.",
    "Dainas kuriu pats. Einu gatve namo.",
]


class Grammar(unittest.TestCase):
    def test_flagged(self):
        for text, word, rule, fix in FLAGGED:
            with self.subTest(text=text, word=word):
                got = findings(text)
                self.assertIn((word, rule), got, f"expected {rule} on '{word}', got {got}")
                self.assertEqual(got[(word, rule)][0], fix)

    def test_correct_sentences_pass(self):
        """No grammar flags on correct text (unknown names are a lexicon matter)."""
        for text in CORRECT:
            with self.subTest(text=text):
                got = {k: v for k, v in findings(text).items() if k[1] != "unknown"}
                self.assertEqual(got, {})


if __name__ == "__main__":
    unittest.main()
