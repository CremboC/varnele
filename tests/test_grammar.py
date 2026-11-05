"""Context rules: python3 -m unittest discover tests"""

import unittest

from varnele.__main__ import Checker

CK = Checker()


def findings(text):
    return {(f.word, f.rule): f.suggestions for f in CK.check_text(text)}


# (sentence, word, rule, expected first suggestion)
FLAGGED = [
    ("Ateisiu veliau, gerai?", "veliau", "rare", "vėliau"),             # a verb seen 79 times, the twin 48,849
    ("Parašiau nauja sakini vakar.", "sakini", "rare", "sakinį"),       # never seen
    ("Vakar mačiau jo masina kieme.", "masina", "rare", "mašiną"),      # the words around it choose the case
    ("Vakar jis gavi laišką.", "gavi", "rare", "gavo"),                 # short, never seen, one key from a common word
    ("Viskas veikia net jeigu rašau prastai.", "net", "comma", ", net"),
    ("Manau, kad šita žmogų reikia aptarti.", "šita", "agreement", "šitą"),   # žmogų is not a genitive here
    ("Ir aš matau dar viena klaida.", "viena", "object", "vieną"),            # transitive verb, skips "dar"
    ("Ir aš matau dar viena klaida.", "klaida", "object", "klaidą"),
    ("Aš matau ką man rašo telefonas.", "ką", "comma", ", ką"),               # indirect question
    ("Kodėl nepataiso visų zodziou?", "zodziou", "unknown", "žodžių"),   # agree with visų
    ("Grįžau prieš pora dienų.", "pora", "case", "porą"),
    ("Susitikime per pietūs.", "pietūs", "case", "pietus"),
    ("Jis žiūrėjo į kitokį grobi.", "grobi", "case", "grobį"),        # an ogonek left off: a vocative or a verb
    ("Vakare einam į šoki.", "šoki", "case", "šokį"),                  # (šoki: you dance) is still the accusative
    ("Jaučiu didelį pykti.", "pykti", "agreement", "pyktį"),
    ("Kas vyko per pamoka?", "pamoka", "case", "pamoką"),
    ("Per savo istorija miestas nukentėjo.", "istorija", "case", "istoriją"),             # kas … per only with pronouns between
    ("Noriu pasiekti geru rezultatu.", "geru", "case", "gerų"),       # pasiekti gerų seen, geru never          # a noun after per: the preposition
    ("Dirbu aštuonias valandas per diena.", "diena", "case", "dieną"),
    ("Perėjome per didele upe.", "upe", "case", "upę"),
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
    ("Neturiu tą gražią knygą.", "knygą", "negation", "knygos"),    # a demonstrative goes with its phrase
    ("Neturiu tą gražią knygą.", "tą", "negation", "tos"),
    ("Nemačiau šią knygą.", "knygą", "negation", "knygos"),         # šis is a pronoun, not a particle
    ("Pamiršiu ši vakarą.", "ši", "agreement", "šį"),
    ("Mačiau seni.", "seni", "object", "senį"),                     # a diacritic twin before senus
    ("Ši kartą aš liksiu.", "Ši", "agreement", "Šį"),                # not karta: the typed ą is meant
    ("Nemačiau tą filmą.", "tą", "negation", "to"),                  # the head's gender first
    ("Turiu ta pati problema.", "pati", "object", "pačią"),          # pati after a demonstrative: "same"
    ("Aš turiu šeima.", "šeima", "object", "šeimą"),                 # not seimą: a typed diacritic stays
    ("Matau pirma kartą.", "pirma", "object", "pirmą"),             # pirma is an adverb too, pirmiausia mostly
    ("Nemačiau jį vakar.", "jį", "negation", "jo"),
    ("Nevalgau mėsą.", "mėsą", "negation", "mėsos"),
    ("Aš buvo namie.", "buvo", "subject", "buvau"),
    ("Tu eina namo.", "eina", "subject", "eini"),
    ("Mes skaito knygas.", "skaito", "subject", "skaitome"),
    ("Jis einu namo.", "einu", "subject", "eina"),
    ("Mes negali grįžti.", "negali", "subject", "negalime"),
    ("Aš kalba lietuviškai.", "kalba", "subject", "kalbu"),         # kalba is also a noun: aš kalbu 605 times
    ("Tu yra mano draugas.", "yra", "subject", "esi"),              # būti's own paradigm, not yri
    ("Aš nėra kaltas.", "nėra", "subject", "nesu"),
    ("Kaip tu gyvena?", "gyvena", "subject", "gyveni"),             # kaip opens the clause: not compared
    ("Aš girdi tave.", "girdi", "subject", "girdžiu"),              # not the rare adjective girdus
    ("Aš vakar važiuosi namo.", "važiuosi", "subject", "važiuosiu"),
    ("Vakar mačiau namas.", "namas", "object", "namą"),
    ("Kuriu tai kas reikalinga.", "kas", "comma", ", kas"),          # relative clause after tai
    ("Darau viską ką galiu.", "ką", "comma", ", ką"),
    ("Kodėl jis ziuri?", "ziuri", "unknown", "žiūri"),               # a verb after jis, not žiuri (jury)
    ("Jis elgesi gerai.", "elgesi", "unknown", "elgėsi"),            # the verb, though elgesį ranks first alone
    ("Jis grazino knygą.", "grazino", "unknown", "grąžino"),         # verbs in the suggester's order, not gražino
    ("Mačiau ji pries porą dienų.", "pries", "unknown", "prieš"),    # no rare verb form (priės) over a likely word
    ("Jis buves mokytojas.", "buves", "unknown", "buvęs"),           # nor over a participle (būvės)
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
    # a clause without a verb (copula left out), degree adverbs, feminine plural subjects, comparisons
    ("O čia neprivaloma nepaisant to, kad žiema žymiai rimtesne.", "rimtesne", "agreement", "rimtesnė"),
    ("O čia neprivaloma nepaisant to, kad ziema žymiai rimtesne ", "rimtesne", "agreement", "rimtesnė"),  # a reverted ziema
    ("Čia individualios teisės žymiai svarbesnes negu visuomenės saugumas.", "svarbesnes", "agreement", "svarbesnės"),
    ("Teisės yra svarbesnes.", "svarbesnes", "agreement", "svarbesnės"),
    ("Žiema buvo kur kas rimtesne.", "rimtesne", "agreement", "rimtesnė"),
    ("Mama didele.", "didele", "agreement", "didelė"),
    ("Jie gerokai mažesnį už pagrindinį objektą.", "mažesnį", "agreement", "mažesni"),
    ("Teisės svarbesnės negu visuomenes saugumas.", "visuomenes", "case", "visuomenės"),   # after a conjunction
    ("Jis atėjo ir visuomenes saugumas pagerėjo.", "visuomenes", "case", "visuomenės"),
    # an unknown subject takes the twin its predicate agrees with (the keyboard re-decides its own žiemą)
    ("Kad ziema žymiai rimtesnė.", "ziema", "unknown", "žiema"),
    ("Per sesiolika mėnesių aplankė daug šalių.", "sesiolika", "unknown", "šešiolika"),    # a numeral after per
    ("Vienas iš penkiu vandenynų.", "penkiu", "unknown", "penkių"),
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
    # a phrase of two modifiers and a noun: the case most of it shares (lost diacritic 1, re-inflection 2)
    ("Ant stalo guli viena nukritusią sagutė.", "nukritusią", "phrase", "nukritusi"),
    ("Ant stalo guli didele graži sagutė.", "didele", "phrase", "didelė"),
    ("Vakar uždarė ta mano didele kavinę.", "ta", "phrase", "tą"),           # across a possessive
    ("Vakar uždarė ta mano didele kavinę.", "didele", "phrase", "didelę"),
    ("Mačiau ta mano didele kavine.", "ta", "object", "tą"),                    # the verb gives the case
    ("Mačiau ta mano didele kavine.", "kavine", "object", "kavinę"),
    ("Mačiau dideli namą.", "dideli", "agreement", "didelį"),
    ("Kada baigsis visa sita isterija?", "sita", "unknown", "šita"),           # agrees with visa, not šitą
    # valency: the case the verb takes (data/valency.tsv), for a phrase that agrees with itself
    ("Visa šita isterija mačiau vakar.", "Visa", "valency", "Visą"),          # nothing nominative before mačiau
    ("Visa šita isterija mačiau vakar.", "isterija", "valency", "isteriją"),
    ("Visa šita istorija esu girdėjęs vakar.", "istorija", "valency", "istoriją"),   # a compound past: girdėti
    ("Visa šita istorija girdėjau vakar.", "šita", "valency", "šitą"),          # girdėjau pools with girdi, girdėti
    ("Esu girdėjęs visa šita istorija.", "visa", "valency", "visą"),
    ("Per daug pasitikėdamas, aš padariau klaida.", "klaida", "valency", "klaidą"),
    ("Man nesvarbu, kiek jūs turite pinigu.", "pinigu", "valency", "pinigų"),                    # number, not case: not didelius
    ("Galbūt reikia padidinti įprasta dydi?", "įprasta", "valency", "įprastą"),  # dydi is only a vocative: no case
    ("Galbūt reikia padidinti įprasta dydi?", "dydi", "valency", "dydį"),
    ("Noriu nupirkti automobili.", "automobili", "valency", "automobilį"),  # nupirkti stays: no modifier
    ("Ar turite skėti?", "skėti", "valency", "skėtį"),                  # a genitive is an object too: turite laiko
    ("Duok man tavo numeri.", "numeri", "valency", "numerį"),           # over the possessive
    ("Padariau kažkur klaida.", "klaida", "valency", "klaidą"),         # kažkur is no question word
    ("Aš žinojau kas tai buvo.", "kas", "comma", ", kas"),            # buvo is a verb, not a particle (buvo/O)
    ("Aš tavimi didžiuojasi.", "didžiuojasi", "subject", "didžiuojuosi"),
    # negation over an instrumental as written: a lost ų when the verb doesn't take it and the genitive is the
    # likelier word (much more frequent, or seen after the verb)
    ("Man nesudarė sunkumu padaryti jį.", "sunkumu", "negation", "sunkumų"),
    ("Tu buvai ten, bet tu nežudei kariu.", "kariu", "negation", "karių"),
    ("Nenuostabu, kad tu neturi draugu.", "draugu", "negation", "draugų"),
    ("Robertas neturėjo bilietu.", "bilietu", "negation", "bilietų"),
    ("Neturiu jokiu klausimu.", "jokiu", "negation", "jokių"),           # the evidence is on jokių: neturiu jokių
    ("Neturiu jokiu klausimu.", "klausimu", "negation", "klausimų"),
    ("Man nereikia jokiu pinigu.", "pinigu", "negation", "pinigų"),     # reikėti takes a genitive object
    ("Nebijok sunkumu.", "sunkumu", "negation", "sunkumų"),
    ("Jis nebijo velniu.", "velniu", "negation", "velnių"),
    ("Nelauk jokiu stebuklu.", "stebuklu", "negation", "stebuklų"),
    ("Aš nesuprantu juoku.", "juoku", "negation", "juokų"),
    ("Aš nesiėmiau jokiu veiksmu.", "veiksmu", "negation", "veiksmų"),  # a nesi- verb: its key is ėmė~
    ("Klausimu neturiu.", "Klausimu", "valency", "Klausimų"),
    ("Nepaisant šiu faktu, jis liko.", "faktu", "valency", "faktų"),     # nepaisyti is counted almost only negated
    ("Tu nekenti filmu.", "filmu", "negation", "filmų"),
    ("Aš nesuprantu pavadinimu.", "pavadinimu", "negation", "pavadinimų"),   # the verb's counts decide, not frequency
    ("Jis neturi vardu.", "vardu", "negation", "vardų"),
    ("Hymanas Rotas nesulauks Naujuju metu.", "metu", "negation", "metų"),   # metas: no adverbial here
    # genitive before a head noun after a copula (buvo is a verb, not a particle, since the loader change)
    ("Tai buvo garbes reikalas.", "garbes", "case", "garbės"),
    ("Čia buvo upes vaga.", "upes", "case", "upės"),
    ("Mačiau didelę ir gražia kavinę.", "gražia", "phrase", "gražią"),       # not kavine
    ("Tie gražūs didelė namai.", "didelė", "phrase", "dideli"),              # gender and number
    ("Specialiais ryškias ženklais.", "ryškias", "phrase", "ryškiais"),
    ("Nors V. Topalovas turėjo šiokia tokią kompensaciją, jo pozicija atrodė gera.", "šiokia", "phrase", "šiokią"),
    ("Šamanizmas – tam tikrų religinės praktikų, pabrėžiančių ryšius.", "religinės", "phrase", "religinių"),
    # the neuter visa tai doesn't decline
    ("Tačiau visą tai ateis vėliau.", "visą", "agreement", "visa"),
    ("Visą tai buvo kvailystė.", "Visą", "agreement", "Visa"),
    ("Padariau visą tai.", "visą", "agreement", "visa"),
    ("Ką tu žinai apie visą tai?", "visą", "agreement", "visa"),
    ("Visą tai jau padarė kiti.", "Visą", "agreement", "Visa"),
    ("Visą tai gražiai padarė.", "Visą", "agreement", "Visa"),                # gražiai isn't a dative here
    ("Visą tai kelia nerimą.", "Visą", "agreement", "Visa"),                  # kelia, a verb: not kelią
]

CORRECT = [
    "Palauk senoli.",                        # an address: senoli is seen as often as senolį
    "Pakrančių apsaugos sraigtasparni, girdite mane?",   # apsaugos modifies the address
    "Ateik šuneli.",                         # ateiti takes no case often enough to make šuneli an object
    "Imk šuneli.",                           # šuneli is seen more than šunelį (sūneli is no twin with a case)
    "Ko tu nori meiluži?",                   # norėti mostly takes the genitive
    "Padėk man ligoni.",                     # ligoni unseen, ligonį only 70 times
    "Gyvenu mažame nameli.",                 # mažame would have to be re-inflected
    "Visi dalyvauja savo noru.",             # a possessive is stepped over only for a phrase with no case
    "Nekalbėk mano vardu.",
    "Žinau kur tavo mašina.",
    "Žinau kur mašina.",                     # an indirect question, not an object
    "Ar žinai kieno ta mašina?",
    "Turėtum didžiuotis tėčiu.",             # didžiuotis is a verb (data/extra.txt), not an adverb
    "Aš didžiuojuosi tavimi.",
    "Manoma, jog jis didžiuoju kunigaikščiu tapo 1236 m.",   # didžiuoju: didysis, not "I am proud"
    "Jis didžiuoju meridianiniu skrituliu matavo.",
    "Aš nesididžiuoju tuo darbu.",           # negation leaves an instrumental the verb governs
    "Aš niekada taip nesididžiavau Tomu.",
    "Aš nesidomiu tuo sportu.",
    "Neturiu tuo metu laiko.",               # tuo metu: when, not what
    "Aš nedirbu mokytoju.",
    "Aš netikiu Dievu.",                     # negation: an instrumental the verb governs stays
    "Nekalbėk tokiu tonu.",
    "Tėtis neatsiliepia telefonu.",
    "Rūmai nepasižymėjo dideliu masteliu ir prabanga.",
    "Daktarai sakė, kad tai plaučių uždegimas.",
    "Aš nesijuokiu iš vaikų.",               # nesijuokiu is reflexive: no object rule
    "Aš nesijuokiu vaikai.",                 # (was vaikus: ne+si+juokiu was lost with the plain forms)
    "Nerodyk tokiu būdu.",                   # būdas is an adverbial, as in valency
    "Palauk kūdiki.",                        # an address (was kūdikį, a known false alarm until 2026-11-04)
    "Net nežinau kokiu kanalu.",             # an indirect question after the negated verb
    "Nežinau kuo tu vardu.",
    "Nekalbėk su manimi tokiu tonu.",
    "Mano mėgstamiausias gėrimas yra arbata.",
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
    # phrase agreement: predicates, partitives, participles with objects, adverbs, coordination
    "Jis vienas didžiausių miestų. Man buvo lengva visą dieną. Jos myli viena kitą.",
    "Ji, viena baigusi mokyklą, dirbo. Megarą, vieną pašovęs strėle, užmušė.",
    "Dumplūnių vaisiai patrauklūs tarptautinėje prekyboje. Korporacijos yra žinomos visame pasaulyje.",
    "Tai buvo pirmoji kairiųjų pergalė. Būdingi plačialapių miškai. Susidarė palankesnė baltiesiems baigmė.",
    "Treniravo rezervines ir pagrindinę komandas. Futbolininkas sužaidė dvidešimt devynerias rungtynes.",
    "Augančių medžių rūšių, turinčių vieną storiausių kamienų. Tai lyg ištikimybės vienas kitam simbolis.",
    "Filmai-operos turi pirmiausia didelę edukacinę vertę. Dažniausiai mišrioji sandauga užrašoma. Tam tikru būdu.",
    "Sienos atkurtos tomis pačiomis spalvomis. Reikia atsižvelgti į nuolatinį pirmosios virsmą.",
    "Jis žino visas jo užnugaris yra tie stipenos.",          # jo is no possessive inside a phrase
    # valency: subjects after the verb, adjuncts, objects already there, set phrases, the clause's subject
    "Kelią jiems parodė pelėda. Leidinį išleido leidykla „Kadokawa“. Kada baigsis visa šita isterija?",
    "Jis gyveno su motina. Aktorius debiutuoja kine. Plačiąja prasme apima viską. Albumas pasirodė savaite anksčiau.",
    "Ją apgynė aukščiausiu įvertinimu. Žmonės ją gaudo drobine paklode. Galima buvo daryti laisva valia.",
    "Jis rašo įvairia tematika. Imperija ėmė visiškai kontroliuoti Britanija. Pati mačiau. Gausi tautosaka išliko.",
    "Su šia nuomone sutinka ne visi. Ji baigė Vilniaus pedagoginį institutą. Sumuštinius su mišraine valgiau.",
    "Kalva – pailga lėkštašlaitė neryškia papėde.",
    # predicate adjectives: a verb in the clause or left out of it, adverbs and verbs as subjects, prefixed copulas
    "Aš nupirkau knygą, o sesė žymiai gražesnę. Hobitas labai gudrus. Atlieka tiek barokinę, tiek moderniąją muziką.",
    "Grupė atliko kiek kitokią, nei jiems įprasta, muziką. Mama didele",
    # genitive after a conjunction: a verb, coordinated words in the same case
    "Pastatas su virtuve bei butu raštininkui. Brahma įtvirtina žemę tarp vandenų ir žvaigždes danguje. Nes rėžiu tiesą į akis.",
    # visa tai: correct as it is in any case; tai as the dative of ta, a mistyped tą, the next word not typed yet
    "Padariau visa tai. Kalbėjome apie visa tai. Už visa tai sumokėjau.",
    "Atidaviau visą tai mergaitei. Atidaviau visą tai mažai mergaitei.",
    "Dirbau visą tai laiką. Dirbau visą tai laika.",
    "Tačiau visą tai",
    "Atidaviau visą tai mažai",
    # subject rule on dialogue: no verb reading that is the likely one, a predicate with the copula left out,
    # a pronoun compared (kaip tu) or an object after another pronoun, nė + noun, a line break between
    "Mes visi einame namo. Aš jus įvesiu į kambarį. Tu tik žiūrėk. Aš iš ten. Mes juk sakėme. Mano draugai.",
    "Mes verti daugiau. Aš nepratusi anksti keltis. Tu nepratęs. Mes karšti!",
    "Tokie kaip tu elgiasi kitaip. Tokių kaip aš jiems reikia. Tu ji nužudysi! Aš nė karto nemačiau.",
    "Aš\nPablogėjo.",
    # a vocative-only noun reading of a word that reads otherwise too is no phrase's noun (toli, gali, seni);
    # per before a nominative phrase: the degree word or kas … per; an instrumental the verb governs
    # šiuo metu is an adverbial of time; durations after a negated verb; the emphatic pronoun; an object already
    # there; a nominative that is the next verb's subject
    "Vienas iš šiuo metu veikiančių. Daug šiuo metu nevyksta. Neateik tą pačią dieną. Nenorėjau šį savaitgalį būti.",
    "Turėsi vieną pati kada nors. Myliu tave visa siela. Manau ši perspektyva jums patinka.",
    # an adverb, the emphatic pati, a reflexive infinitive, an instrumental noun: no object
    "Filmai turi pirmiausia didelę vertę. Bandžiau pati, bet veltui. Turime keltis liftu. Myliu tave visa širdimi.",
    "Kas čia per vieta? Kas tai jau per vieta? Dabar mes kovojame vieni. Aš atėjau vienas.",
    "Tai per toli. Ką gali padaryti? Jie per seni. Per anksti išėjai. Ji per brangi.",
    "Per didelė rizika. Kas čia per vieta? Kas jūs per žmonės? Kas per velniava? Kas tai per kambarys?",
    "Prisiekiu Dievu. Mes bandėme su jais susisiekti telefonu.",
    "Jie šventi. Tu viso to nematei. Jis šiuo metu laisvėje. Mes mano kieme. Mes atkirsti.",
]


# Known false alarms, left on purpose (each with why). The test fails when one is no longer flagged: then move
# it to CORRECT.
KNOWN_FALSE_ALARMS = [
    "Nemalk liežuviu.",                      # an instrumental of means after a verb whose counts say it takes
    "Kodėl jūs man šito nepasakėte telefonu?",   # none; the verb-first negation guard is net better (AGENTS.md)
    "Klausyk seni, aš nesu jaunas.",          # an address: seni is a vocative, but also the accusative senį typed
                                              # without its ogonek, which the object rule must keep catching
]


class Grammar(unittest.TestCase):
    def test_known_false_alarms(self):
        for text in KNOWN_FALSE_ALARMS:
            with self.subTest(text=text):
                got = {k: v for k, v in findings(text).items() if k[1] != "unknown"}
                self.assertTrue(got, "no longer flagged: move it to CORRECT")


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

    def test_slips_onto_foreign_letters(self):
        """One finger slip onto w, q or x is a typo; foreign words stay foreign."""
        for bad, good in {"ziwma": "žiema", "priwglobscio": "prieglobsčio", "xiūrėti": "žiūrėti",
                          "ziewma": "žiema"}.items():   # the last: w pressed as well as e
            with self.subTest(word=bad):
                self.assertEqual(CK.check_word(bad)[0], "unknown")
                self.assertEqual(CK.check_word(bad)[1][0], good)
        # seen in the corpus, a name, too short, w not touching d
        for word in "news wiki Ziwma tax wirba zwiema".split():
            with self.subTest(word=word):
                self.assertEqual(CK.check_word(word), ("skip", []))
        # a capital at a sentence start may be the keyboard's own, unless it is the slip itself (a name)
        got = [(f.start, f.suggestions[0]) for f in CK.check_text("Ziwma buvo šalta. Westu ir Ziwma.")]
        self.assertEqual(got, [(0, "Žiema")])


class RareWords(unittest.TestCase):
    def test_a_typed_diacritic_and_a_name_stay(self):
        for text in ("Ji yra dantistė.", "Kalbėjau su Ukmerge kartą.", "Mačiau Eduarda vakar.", "Skaitė apie vašu tautą."):
            with self.subTest(text=text):
                self.assertFalse([f for f in CK.check_text(text) if f.rule == "rare"])

    def test_grammar_undecided_shows_the_twins(self):
        got = [f.suggestions for f in CK.check_text("Masina stovi kieme.") if f.rule == "rare"]
        self.assertEqual(sorted(got[0][:2]), ["Mašina", "Mašiną"])

    def test_key_shift_when_nothing_is_close(self):
        self.assertEqual(CK.check_word("fofrkua")[1][0], "didelis")
        self.assertIn("labas", CK.check_word("ksbsd")[1])


if __name__ == "__main__":
    unittest.main()
