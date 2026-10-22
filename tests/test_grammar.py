"""Context rules: python3 -m unittest discover tests"""

import unittest

from varnele.__main__ import Checker

CK = Checker()


def findings(text):
    return {(f.word, f.rule): f.suggestions for f in CK.check_text(text)}


# (sentence, word, rule, expected first suggestion)
FLAGGED = [
    ("Viskas veikia net jeigu rašau prastai.", "net", "comma", ", net"),
    ("Manau, kad šita žmogų reikia aptarti.", "šita", "agreement", "šitą"),   # žmogų is not a genitive here
    ("Ir aš matau dar viena klaida.", "viena", "object", "vieną"),            # transitive verb, skips "dar"
    ("Ir aš matau dar viena klaida.", "klaida", "object", "klaidą"),
    ("Aš matau ką man rašo telefonas.", "ką", "comma", ", ką"),               # indirect question
    ("Kodėl nepataiso visų zodziou?", "zodziou", "unknown", "žodžių"),   # agree with visų
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
    ("Kuriu tai kas reikalinga.", "kas", "comma", ", kas"),          # relative clause after tai
    ("Darau viską ką galiu.", "ką", "comma", ", ką"),
    ("Kodėl jis ziuri?", "ziuri", "unknown", "žiūri"),               # a verb after jis, not žiuri (jury)
    ("Parašyk koki nors sakinį.", "koki", "case", "kokį"),          # indefinite pronoun before nors
    ("Per 10 metu daug pasikeitė.", "metu", "quantity", "metų"),    # number ending in 0 or 11-19
    ("Kainavo 15 euru.", "euru", "quantity", "eurų"),
    ("Ieškau raktu.", "raktu", "case", "raktų"),                     # verb with a genitive object
    ("Lauksiu tavo zinutes.", "zinutes", "unknown", "žinutės"),
    ("Nusipirkau naujas automobilis.", "automobilis", "object", "automobilį"),
    ("Radau nukritusią sagute.", "sagute", "agreement", "sagutę"),
    ("Pagrindinė kylanti grėsme yra kirtimai.", "grėsme", "agreement", "grėsmė"),
    ("Kodėl nepataiso visu žodžių?", "visu", "negation", "visų"),
    ("Kodėl nepataiso žodžių kuriu aš rašau?", "kuriu", "relative", "kurių"),
    ("Kodėl nepataiso visų zodzou?", "zodzou", "unknown", "žodžių"),
    # unknown word: context picks the suggestion order
    ("Grįžau prieš porą dienu.", "dienu", "unknown", "dienų"),
    ("Vakar pries porą dienų.", "pries", "unknown", "prieš"),
    # parenthetical words, greetings and address
    ("Deja jis neatėjo.", "jis", "comma", ", jis"),
    ("Jis deja neatėjo į susitikimą.", "deja", "comma", ", deja"),
    ("Jis deja neatėjo į susitikimą.", "neatėjo", "comma", ", neatėjo"),
    ("Žinoma aš ateisiu.", "aš", "comma", ", aš"),
    ("Kita vertus tai brangu.", "tai", "comma", ", tai"),
    ("Labas Jonai kaip sekasi?", "Jonai", "comma", ", Jonai"),
    ("Labas Jonai kaip sekasi?", "kaip", "comma", ", kaip"),
    ("Ačiū drauge.", "drauge", "comma", ", drauge"),
    # comparison clause, repeated connectives, lists, participial phrases
    ("Padariau daugiau negu reikėjo.", "negu", "comma", ", negu"),
    ("Nei Jonas nei Petras neatėjo.", "nei", "comma", ", nei"),
    ("Ar ateisi ar ne?", "ar", "comma", ", ar"),
    ("Mėgstu ne tik obuolius bet ir kriaušes.", "bet", "comma", ", bet"),
    ("Mėgstu obuolius kriaušes ir slyvas.", "kriaušes", "comma", ", kriaušes"),
    ("Žmogus stovintis prie lango žiūri į mus.", "stovintis", "comma", ", stovintis"),
    ("Žmogus stovintis prie lango žiūri į mus.", "žiūri", "comma", ", žiūri"),
    ("Pamačiau turistus norinčius patirti egzotikos.", "norinčius", "comma", ", norinčius"),
    # subject with an adverb between, relative case from the verb, instrumental-looking objects
    ("Aš vakar buvo namie.", "buvo", "subject", "buvau"),
    ("Jis jau einu.", "einu", "subject", "eina"),
    ("Tai knyga, kuria skaičiau.", "kuria", "relative", "kurią"),
    ("Tai mergina, kuria aš mačiau vakar.", "kuria", "relative", "kurią"),
    ("Radau nukritusia sagute.", "nukritusia", "object", "nukritusią"),
    ("Radau nukritusia sagute.", "sagute", "object", "sagutę"),
    ("Skaitau įdomia knyga.", "įdomia", "object", "įdomią"),
    ("Radau nukritusia sagutę.", "nukritusia", "object", "nukritusią"),   # noun fixed first (keyboard)
    ("Labas, Jonai kaip sekasi?", "kaip", "comma", ", kaip"),             # first comma already there
    ("Bebėgiodamas link namu.", "namu", "case", "namų"),
    ("Aš net ne vienos eilutes kodo neparašiau.", "eilutes", "agreement", "eilutės"),  # not "viena kitą"
    # a noun before another noun is its genitive
    ("Miesto gyventoju skaičius auga.", "gyventoju", "case", "gyventojų"),
    ("Vietoves gyventojai pyksta.", "Vietoves", "case", "Vietovės"),
    ("Lietuvos kariuomenes pulkas žygiavo.", "kariuomenes", "case", "kariuomenės"),
    ("Sutartis dėl branduoliniu ginklu kontrolės.", "branduoliniu", "case", "branduolinių"),
    ("Sutartis dėl branduoliniu ginklu kontrolės.", "ginklu", "case", "ginklų"),
    # objects of 3rd person transitive verbs once the subject is in front; adverbs in between
    ("Jonas mato namas.", "namas", "object", "namą"),
    ("Mama skaito knyga.", "knyga", "object", "knygą"),
    ("Jis vakar nupirko nauja knyga.", "nauja", "object", "naują"),
    ("Jis turi didele mašina.", "mašina", "object", "mašiną"),
    ("Mačiau labai gražus namas.", "gražus", "object", "gražų"),
    # agreement: change the word typed without diacritics; predicate adjectives
    ("Tai buvo nedidele mergaitė.", "nedidele", "agreement", "nedidelė"),
    ("Ėjo pro nedideles gyvenvietės.", "gyvenvietės", "agreement", "gyvenvietes"),   # pro takes the accusative
    ("Ji nedidele.", "nedidele", "agreement", "nedidelė"),
    ("Mergaitė buvo labai nedidele.", "nedidele", "agreement", "nedidelė"),
    ("Lempa kabo virs stalo.", "virs", "case", "virš"),               # virs = will become, unless a verb came before
    # keyboard order: the words before were committed (and fixed) before the head was typed
    ("Surengė dalyvaujančiu šalių viršūnių susitikimą.", "dalyvaujančiu", "agreement", "dalyvaujančių"),
    ("Laikė priėmimo į teises mokyklą testus.", "teises", "case", "teisės"),        # acc pl + acc sg: not one phrase
    ("Laikė priėmimo į teises mokykla testus.", "teises", "case", "teisės"),        # the head is į's object
    ("Laikė priėmimo į teisės mokykla testus.", "mokykla", "case", "mokyklą"),      # across the genitive
    ("Medžiokles plotas priklausė girininkijai.", "Medžiokles", "case", "Medžioklės"),  # plotas: not a participle here
    ("Nutiesus pažintini taką lankytojai nukreipiami.", "pažintini", "agreement", "pažintinį"),  # -tinas takes no object
    # unknown words typed without diacritics: the context picks among their candidates
    ("Memorandume dalyvaujanciu saliu atstovai.", "dalyvaujanciu", "unknown", "dalyvaujančių"),  # agrees with šalių
    ("Jis rado salyga.", "salyga", "unknown", "sąlygą"),                       # object of a transitive verb
    ("Ten veikė Parsukovo papuosalu dirbtuve.", "papuosalu", "unknown", "papuošalų"),  # genitive before a noun
    ("Iškilo tarpusavio sienu klausimas.", "sienu", "unknown", "sienų"),       # not šienų (hay)
]

CORRECT = [
    "Grįšiu, ir net jei vėluosiu, paskambinsiu.",
    "Einu gatve namo.",                       # motion verb: instrumental is right
    "Mačiau ką tik atėjusį žmogų.",
    "Žinau ką nors apie tai.",
    "Aš manau, kas bus toliau.",               # no object fix on a clause word
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
    "Vienas kitam padėjo. Ne vienas žmogus atėjo. Bėgau namų link.",
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
    # new comma rules: the predicate use of participles, genitive chains, modifiers, "known"
    "Žinoma tik viena rūšis. Žinoma, kad jis gimė Vilniuje.",
    "Laba diena. Labas rytas. Sveiki atvykę. Ačiū tau.",
    "Jis aukštesnis negu aš. Arba tu, arba aš.",
    "Ar žinai, kad jis grįžo ir ar jis sveikas?",
    "Pavadinimas kilęs iš vardo. Miestas įsikūręs prie upės.",
    "Laumės mėgstančios rinktis prie upių.",
    "Gruodį susitiko su sausuma žygiavusia Aleksandro kariauna.",
    "Bangų fizika nagrinėja bangos amplitudės ir fazės pokyčius.",
    "Sienos atkurtos tomis pačiomis spalvomis ir medžiagomis.",
    "Ruja būna pavasarį gegužę ir birželį.",
    "Grįžęs namo jis atsigulė.",              # the comma here is optional
    "Aš labai noriu valgyti. Aš ir jis buvome ten.",
    "Tai plunksna, kuria rašau. Tai knyga, kuria didžiuojuosi. Tai knyga, kurios neskaičiau.",
    "Mačiau tuo metu daug žmonių. Matėme tapusią vienuole seserį.",
    "Jis neatėjo laiku.",                     # laiku = on time, not an object
    "Įmonė kuria ir parduoda baldus. Įmonė kuria baldus. Ji kuria jį.",   # the verb kurti
    "Režisierė, kuri kuria vaizdo klipus.",
    "Dainas kuriu tai, kas reikalinga. Žodžių kuriu ir rašau daug.",
    "Tai kas dabar?",
    "Pamėgink rašyti kokį nors sakinį. Ar kas nors ateis?",
    "Turėjau 2 katinus. Laukiau valandą. 2010 metais. Plaukė vandenynu.",
    "Rieduliai guli 20 m atstumu. Suskirstyta į 12 etniniu pagrindu suformuotų regionų.",
    # instrumentals and accusatives before a noun that are not genitives
    "Karo metu žmonės slėpėsi. Šiuo metu dirbu. Sovietmečiu dvarai nugriauti. Vienu metu kaime veikė mokykla.",
    "Pamatė mergaites mokykloje. Grįžo su broliu namo. Dirbo mokytoju kaimo mokykloje.",
    "Tapo oficialiu ekipos pilotu bandytoju. Garsėja aktyviu naktiniu gyvenimu.",
    "Knygą skaito mama. Jonas ir Petras mato namą. Ši kolekcija atsirado kartu su muziejumi.",
    "Jie sutiko baigti partiją. Intervencija turėtų būti suprantama plačiau. Vaikai gavo dovanų.",
    "Cerkvė tapo parapine. Ji buvo mokytoja. Jos buvo gražios. Jis buvo geru draugu. Ji grįžo laiminga.",
    "Mama virs sriubos. Vanduo greitai virs.",
    # keyboard-order rules: heads after genitives, prepositions, passive participles
    "Susitiko su dideliu žmonių būriu. Kalbėjo su dideliu žmonių",
    "Adalis tapo svarbiausiu musulmonų kovos prieš krikščionis centru. Mūšis laikomas lemiamu serbų kovoje.",
    "Kitose kalbose, kaip rusų kalba žodžiu rinkliava apibūdinamas ir muitas.",
    "Tai buvo įsiveržimų į Kalavijuočių ordino žemes serija.",
    "Nukentėjo I pasaulinio karo metu. Tai įstojimo į NATO diena.",
    "Buvo nutarta išleidimo datą paankstinti. Kurioje buvo numatyta koplyčią paversti galerija.",
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
