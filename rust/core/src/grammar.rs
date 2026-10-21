//! Context rules: errors a word-by-word checker cannot see.
//! A line-by-line port of varnele/grammar.py; see that file for the reasoning
//! behind each rule and exception.

use std::cell::{OnceCell, RefCell};
use std::collections::BTreeMap;

use crate::analyzer::{Analysis, Analyzer, Status};
use crate::data::Kind;
use crate::fx::FxMap;
use crate::text::*;

const FINITE: &[&str] = &["prs", "pst", "pstf", "fut", "cond", "imp", "inf"];
const CASES: &[&str] = &["nom", "gen", "dat", "acc", "ins", "loc", "voc"];
fn case_name(c: &str) -> &'static str {
    match c {
        "nom" => "nominative",
        "gen" => "genitive",
        "dat" => "dative",
        "acc" => "accusative",
        "ins" => "instrumental",
        "loc" => "locative",
        _ => "vocative",
    }
}

fn prep_cases(p: &str) -> Option<&'static [&'static str]> {
    Some(match p {
        "į" | "per" | "pro" | "prieš" | "apie" | "pagal" | "palei" | "pas" | "aplink" => &["acc"],
        "iš" | "be" | "nuo" | "prie" | "iki" | "ligi" | "dėl" | "ant" | "virš" | "tarp" | "anot"
        | "pasak" | "šalia" | "vietoj" | "netoli" | "anapus" | "šiapus" | "abipus" | "vidury"
        | "vidur" | "link" => &["gen"],
        "už" => &["acc", "gen"],
        "su" | "sulig" => &["ins"],
        "ties" => &["gen", "ins"],
        _ => return None,
    })
}
const PREP_LIST: &[&str] = &[
    "į", "per", "pro", "prieš", "apie", "pagal", "palei", "pas", "aplink", "iš", "be", "nuo",
    "prie", "iki", "ligi", "dėl", "ant", "virš", "tarp", "anot", "pasak", "šalia", "vietoj",
    "netoli", "anapus", "šiapus", "abipus", "vidury", "vidur", "link", "už", "su", "sulig", "ties",
];

const QUANTIFIER_WORDS: &[&str] = &[
    "daug", "mažai", "nemažai", "kiek", "tiek", "daugiau", "mažiau", "nedaug", "keletas", "keleto",
    "keletą", "keletui", "keletu", "daugybė", "daugybę", "daugybės", "dauguma", "daugumą",
    "daugumos", "pora", "porą", "poros", "porai", "pustrečio", "kelios", "keliolika", "tūkstantis",
    "tūkstančiai", "tūkstančių", "tūkstantį", "tūkstančius",
];
const QUANTIFIER_LEMMAS: &[&str] = &[
    "šimtas", "tūkstantis", "milijonas", "milijardas", "dešimtis", "keletas", "pora", "daugybė",
    "dauguma", "pusė", "trečdalis", "ketvirtadalis", "ketvirtis",
];
const KURIS: &[&str] = &[
    "kuris", "kuri", "kurio", "kurios", "kuriam", "kuriai", "kurį", "kurią", "kuriuo", "kuria",
    "kuriame", "kurioje", "kurie", "kurių", "kuriems", "kurioms", "kuriuos", "kurias", "kuriais",
    "kuriomis", "kuriuose", "kuriose",
];
/// (number, gender) each form of kuris can have; gender None = any
const KURIS_FEATURES: &[(&str, &[(&str, Option<&str>)])] = &[
    ("kuris", &[("sg", Some("m"))]), ("kuri", &[("sg", Some("f"))]), ("kurio", &[("sg", Some("m"))]),
    ("kurios", &[("sg", Some("f")), ("pl", Some("f"))]), ("kuriam", &[("sg", Some("m"))]),
    ("kuriai", &[("sg", Some("f"))]), ("kurį", &[("sg", Some("m"))]), ("kurią", &[("sg", Some("f"))]),
    ("kuriuo", &[("sg", Some("m"))]), ("kuria", &[("sg", Some("f"))]), ("kuriame", &[("sg", Some("m"))]),
    ("kurioje", &[("sg", Some("f"))]), ("kurie", &[("pl", Some("m"))]), ("kurių", &[("pl", None)]),
    ("kuriems", &[("pl", Some("m"))]), ("kurioms", &[("pl", Some("f"))]), ("kuriuos", &[("pl", Some("m"))]),
    ("kurias", &[("pl", Some("f"))]), ("kuriais", &[("pl", Some("m"))]), ("kuriomis", &[("pl", Some("f"))]),
    ("kuriuose", &[("pl", Some("m"))]), ("kuriose", &[("pl", Some("f"))]),
];
const CLAUSE_STARTERS: &[&str] =
    &["kad", "nes", "jog", "bet", "tačiau", "kadangi", "nors", "jei", "jeigu", "kai", "kol", "nebent", "o"];
const NO_COMMA_AFTER: &[&str] = &[
    "ir", "ar", "arba", "bei", "o", "bet", "nes", "kad", "jog", "tik", "net", "ypač", "būtent",
    "nebent", "juk", "negu", "nei", "kaip", "jei", "jeigu", "kai", "nors", "tačiau", "kadangi",
    "kol", "vos", "lyg", "tarsi", "užtat", "taigi",
];
const INTERROGATIVES: &[&str] = &[
    "kas", "ką", "ko", "kam", "kuo", "kur", "kada", "kaip", "kodėl", "kieno", "kiek", "koks",
    "kokia", "kokį", "kokią", "kokie", "kokios", "kokių", "kokio", "kokiam", "kokiu", "kokiame",
    "kokioje", "kokiems", "kokius", "kokias", "kažkas", "kažkur",
];
fn interrogative_folded(fw: &str) -> bool {
    INTERROGATIVES.iter().chain(KURIS.iter()).any(|w| fold(w) == fw)
}
fn neg_pronoun(w: &str) -> Option<&'static str> {
    Some(match w {
        "jį" => "jo",
        "ją" => "jos",
        "juos" | "jas" => "jų",
        "mane" => "manęs",
        "tave" => "tavęs",
        "mus" => "mūsų",
        "jus" => "jūsų",
        "save" => "savęs",
        "tą" => "to",
        "šį" => "šio",
        "šią" => "šios",
        "tuos" => "tų",
        "šiuos" => "šių",
        _ => return None,
    })
}
const TIME_LEMMAS: &[&str] = &[
    "diena", "naktis", "savaitė", "mėnuo", "metai", "valanda", "minutė", "sekundė", "kartas",
    "rytas", "vakaras", "žiema", "vasara", "pavasaris", "ruduo", "para", "pusmetis", "dešimtmetis",
    "šimtmetis", "amžius", "laikotarpis", "popietė",
];
// Verbs that take a genitive object: laukiu tavo žinutės, reikia pagalbos, ieškau raktų
const GENITIVE_VERBS: &[&str] = &[
    "laukti", "laukia", "laukė", "ieškoti", "ieško", "ieškojo", "bijoti", "bijo", "bijojo",
    "siekti", "siekia", "siekė", "reikėti", "reikia", "reikėjo", "vengti", "vengia", "vengė",
];
const VERB_PREFIXES: &[&str] = &["ap", "at", "į", "iš", "nu", "pa", "par", "per", "pra", "pri", "su", "už", "api", "ati"];
const POSSESSIVES: &[&str] = &["mano", "tavo", "savo", "jo", "jos", "jų", "mūsų", "jūsų"];

/// A number ending in 0 or 11-19 right before the word (gap "… 10 "): it takes the genitive plural.
fn gen_number(gap: &str) -> Option<String> {
    let g: Vec<char> = gap.chars().collect();
    let mut e = g.len();
    while e > 0 && g[e - 1].is_whitespace() {
        e -= 1;
    }
    if e == g.len() {
        return None;
    }
    let mut b = e;
    while b > 0 && g[b - 1].is_ascii_digit() {
        b -= 1;
    }
    if b == e || (b > 0 && !(g[b - 1].is_whitespace() || "(–—-".contains(g[b - 1]))) {
        return None;
    }
    let d: String = g[b..e].iter().collect();
    let last2: u32 = d[d.len().saturating_sub(2)..].parse().unwrap_or(0);
    let nonzero = d.chars().any(|c| c != '0');
    (nonzero && (last2 % 10 == 0 || (11..=19).contains(&last2))).then_some(d)
}
const TIME_WORDS: &[&str] = &["visą", "visus", "visas", "kiekvieną", "ištisą", "ištisus", "ištisas"];
/// Verbs whose object is practically never a bare instrumental, so "matau viena klaida" is an
/// accusative typed without diacritics (motion verbs do take one: einu gatve). Principal parts,
/// matched by ending so prefixed entries count (pamatyti, surado). Verbs that take an
/// instrument (rašau ranka, valgau šakute) stay out.
const TRANSITIVE_VERBS: &[&str] = &[
    "matyti", "mato", "matė", "rasti", "randa", "rado", "turėti", "turi", "turėjo", "gauti", "gauna",
    "gavo", "pirkti", "perka", "pirko", "žinoti", "žino", "žinojo", "mylėti", "myli", "mylėjo",
    "girdėti", "girdi", "girdėjo", "sutikti", "sutinka", "sutiko", "skaityti", "skaito", "skaitė",
];
/// Words that may stand between a verb and its object: matau dar vieną klaidą
const OBJECT_SKIP: &[&str] = &["dar", "jau", "vėl", "irgi", "tik", "net"];
/// Verbs of seeing, knowing and saying that take an indirect question: matau, ką man rašo
/// (principal parts, matched by ending so prefixed entries count)
const QUESTION_VERBS: &[&str] = &[
    "matyti", "mato", "matė", "žinoti", "žino", "žinojo", "suprasti", "supranta", "suprato", "sakyti",
    "sako", "sakė", "klausti", "klausia", "klausė", "girdėti", "girdi", "girdėjo", "galvoti", "galvoja",
    "galvojo", "manyti", "mano", "manė", "aiškinti", "aiškina", "aiškino", "rodyti", "rodo", "rodė",
    "pasakoti", "pasakoja", "pasakojo",
];
/// These start a clause, they are not the object: manau, kas ... / žinau, kuris ...
const CLAUSE_WORDS: &[&str] = &["kas", "kuris", "kuri", "kurie", "kurios", "koks", "kokia", "kokie", "kokios"];
/// Accusative forms of kuris: knyga, kurią skaičiau
const KURIS_ACC: &[&str] = &["kurį", "kurią", "kuriuos", "kurias"];
// a demonstrative followed by a kas-word starts a relative clause: tai, kas reikalinga
const DEMONSTRATIVES: &[&str] = &["tai", "tas", "ta", "tą", "to", "viskas", "viską", "visko"];
const KAS_FORMS: &[&str] = &["kas", "ką", "ko", "kam", "kuo"];
// an object right after kuria/kuriu makes it the verb kurti: kuriu tai, kas reikalinga
const VERB_OBJECTS: &[&str] = &["tai", "tą", "viską", "jį", "ją", "juos", "jas"];
/// Parenthetical words, set off by commas: Deja, neatėjo. / Jis, beje, sutiko.
const INTRO_ANYWHERE: &[&str] = &["deja", "beje", "pavyzdžiui"];
const INTRO_START: &[&str] = &["deja", "beje", "pavyzdžiui", "vadinasi", "žinoma"];
const INTRO_PAIRS: &[(&str, &str)] = &[("kita", "vertus"), ("be", "abejo"), ("mano", "nuomone"), ("ko", "gero")];
/// Greetings: a vocative or a new clause after them takes a comma (Labas, Jonai, kaip sekasi?)
const GREETINGS: &[&str] = &[
    "labas", "laba", "labi", "labos", "sveikas", "sveika", "sveiki", "sveikos", "ačiū", "dėkui",
    "labanakt", "sudie", "sveikinu",
];
const SUBJECT_PRONOUNS: &[&str] = &["aš", "tu", "jis", "ji", "mes", "jūs", "jie", "jos"];
/// Between a subject pronoun and its verb (aš vakar buvo): not these
const SUBJECT_NO_SKIP: &[&str] = &["tai", "tas", "ta", "šis", "ši", "tie", "tos", "ne", "nei", "ar", "jo", "jos", "jų"];
/// A participial phrase does not run across these (plus CLAUSE_STARTERS and KURIS)
const PHRASE_STOP: &[&str] = &["ir", "bei", "ar", "arba", "o", "bet", "nei", "negu", "kaip"];
const SENTENCE_GAP: &str = ".!?…\n(„“\"«»–—-";
const COPULAS: &[&str] = &[
    "būti", "buvo", "būna", "esa", "yra", "tapti", "tapo", "tampa", "likti", "liko", "lieka",
    "atrodyti", "atrodė", "atrodo", "vadintis", "vadinosi", "vadinasi", "gimti", "gimė", "gimsta",
    "mirti", "mirė", "miršta", "jaustis", "jautėsi", "jaučiasi", "pasidaryti", "pasidarė",
    "pasidaro", "pasirodyti", "pasirodė", "pasirodo", "dirbti", "dirbo", "dirba",
];
/// Participles of these verbs take a predicate instrumental (tapusią vienuole);
/// matched by ending so prefixed entries (išrinkti) count too.
const PREDICATIVE_VERBS: &[&str] = &[
    "būti", "buvo", "būna", "esa", "tapti", "tapo", "tampa", "likti", "liko", "lieka", "atrodyti",
    "atrodė", "atrodo", "vadinti", "vadino", "vadina", "vadintis", "laikyti", "laikė", "laiko",
    "rinkti", "rinko", "renka", "skirti", "skyrė", "skiria", "pažinti", "pažino", "pažįsta", "skelbti",
    "skelbė", "skelbia", "tituluoti", "titulavo", "tituluoja", "dirbti", "dirbo", "dirba", "gimti",
    "gimė", "gimsta", "mirti", "mirė", "miršta", "jaustis", "jautėsi", "jaučiasi", "rodyti", "rodė",
    "rodo",
];
const COPULA_FORMS: &[&str] = &["nėra", "nesu", "nesi", "nesame", "nesate", "esu", "esi", "esame", "esate", "yra"];
/// Linking verbs whose predicate adjective is nominative (tapo parapine, dirbo vienas: not these)
const NOMINATIVE_COPULAS: &[&str] = &[
    "būti", "buvo", "būna", "esa", "yra", "atrodyti", "atrodė", "atrodo", "likti", "liko", "lieka",
    "jaustis", "jautėsi", "jaučiasi",
];
/// Subject pronoun -> (number, gender) of its predicate adjective
fn pronoun_features(w: &str) -> Option<(&'static str, &'static str)> {
    Some(match w {
        "jis" => ("sg", "m"),
        "ji" => ("sg", "f"),
        "jie" => ("pl", "m"),
        "jos" => ("pl", "f"),
        _ => return None,
    })
}
const COORDINATORS: &[&str] = &["ir", "bei", "arba", "ar", "nei"];
fn has_diacritics(w: &str) -> bool {
    w.chars().any(|c| "ąčęėįšųūžĄČĘĖĮŠŲŪŽ".contains(c))
}
fn subject_person(w: &str) -> Option<&'static str> {
    Some(match w {
        "aš" => "1sg",
        "tu" => "2sg",
        "mes" => "1pl",
        "jūs" => "2pl",
        "jis" | "ji" | "jie" => "3",
        _ => return None,
    })
}
const PERSONS: &[&str] = &["1sg", "2sg", "3", "1pl", "2pl"];
fn person_name(p: &str) -> &'static str {
    match p {
        "1sg" => "1st person singular",
        "2sg" => "2nd person singular",
        "3" => "3rd person",
        "1pl" => "1st person plural",
        _ => "2nd person plural",
    }
}

#[derive(Clone, Debug)]
pub struct Issue {
    pub start: usize,
    pub end: usize,
    pub word: String,
    pub rule: &'static str,
    pub message: String,
    pub suggestions: Vec<String>,
}

#[derive(Clone, Copy, PartialEq)]
enum Pos {
    Noun,
    Adj,
}

#[derive(Clone)]
struct Reading {
    pos: Pos,
    case: &'static str,
    number: Option<&'static str>,
    gender: Option<&'static str>,
    participle: bool,
}

fn agree(a: &Reading, b: &Reading) -> bool {
    fn same(x: Option<&str>, y: Option<&str>) -> bool {
        x.is_none() || y.is_none() || x == y
    }
    a.case == b.case && same(a.number, b.number) && same(a.gender, b.gender)
}

fn retag(tag: &str, case: Option<&str>, person: Option<&str>) -> String {
    tag.split('.')
        .map(|p| {
            if let (Some(c), true) = (case, CASES.contains(&p)) {
                c
            } else if let (Some(x), true) = (person, PERSONS.contains(&p)) {
                x
            } else {
                p
            }
        })
        .collect::<Vec<_>>()
        .join(".")
}

#[derive(Default)]
pub struct Grammar {
    analyses: RefCell<FxMap<String, Vec<Analysis>>>,
    readings: RefCell<FxMap<String, Vec<Reading>>>,
    variants: RefCell<FxMap<String, Vec<String>>>,
    known: RefCell<FxMap<String, bool>>,
    suggestions: RefCell<FxMap<String, Vec<String>>>,
}

struct G<'a> {
    an: &'a Analyzer,
    c: &'a Grammar,
}

struct Word {
    text: String,
    lower: String,
    start: usize,
    end: usize,
    own: Vec<Reading>,
    known: bool,
    variants: OnceCell<Vec<(String, Vec<Reading>)>>,
}

impl<'a> G<'a> {
    fn parts(&self, a: &Analysis) -> &'a [String] {
        &self.an.data.tag(a.tag).parts
    }
    fn tag(&self, a: &Analysis) -> &'a str {
        &self.an.data.tag(a.tag).s
    }
    fn finite(&self, a: &Analysis) -> bool {
        let p = self.parts(a);
        p[0] == "V" && p.len() > 2 && FINITE.contains(&p[1].as_str()) && PERSONS.contains(&p[2].as_str())
    }

    fn analyses(&self, w: &str) -> Vec<Analysis> {
        if let Some(v) = self.c.analyses.borrow().get(w) {
            return v.clone();
        }
        let v = self.an.analyze(w);
        self.c.analyses.borrow_mut().insert(w.to_string(), v.clone());
        v
    }

    fn readings_of(&self, w: &str) -> Vec<Reading> {
        if let Some(v) = self.c.readings.borrow().get(w) {
            return v.clone();
        }
        let out = self.readings(&self.an.analyze(w));
        self.c.readings.borrow_mut().insert(w.to_string(), out.clone());
        out
    }

    fn readings(&self, analyses: &[Analysis]) -> Vec<Reading> {
        let mut out = Vec::new();
        for a in analyses {
            let parts = self.parts(a);
            let Some(case) = parts.iter().find_map(|p| CASES.iter().find(|c| **c == p.as_str()).copied()) else {
                continue;
            };
            let has = |x: &str| parts.iter().any(|p| p == x);
            let number = if has("sg") { Some("sg") } else if has("pl") { Some("pl") } else { None };
            let gender = if has("m") { Some("m") } else if has("f") { Some("f") } else { None };
            let head = parts[0].as_str();
            if head == "N" {
                out.push(Reading { pos: Pos::Noun, case, number, gender, participle: false });
            } else if matches!(head, "A" | "P" | "Num") {
                out.push(Reading { pos: Pos::Adj, case, number, gender, participle: false });
            } else if head == "V" && parts.len() > 1 && parts[1].starts_with('p') {
                out.push(Reading { pos: Pos::Adj, case, number, gender, participle: true });
            }
        }
        out
    }

    fn lemma_freq(&self, a: &Analysis) -> u32 {
        *self.an.data.lemma_freq.get(&lower(&a.lemma)).unwrap_or(&0)
    }

    fn freq(&self, w: &str) -> u32 {
        *self.an.data.freq.get(&lower(w)).unwrap_or(&0)
    }

    fn variants_of(&self, w: &str) -> Vec<String> {
        if let Some(v) = self.c.variants.borrow().get(w) {
            return v.clone();
        }
        let mut v: Vec<(f64, String)> = self
            .an
            .folded_forms(&fold(w))
            .into_iter()
            .filter(|f| lower(f) != w && !self.an.analyze_exact(f).is_empty())
            .map(|f| (crate::suggest::cost(w, &lower(&f)), f))
            .collect();
        // closest first: šita -> šitą before sytą (y is its own key)
        v.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap().then_with(|| a.1.cmp(&b.1)));
        let v: Vec<String> = v.into_iter().map(|(_, f)| f).collect();
        self.c.variants.borrow_mut().insert(w.to_string(), v.clone());
        v
    }

    /// Typo corrections of an unknown word, lower case (candidates for context rules).
    fn suggestions_of(&self, w: &str) -> Vec<String> {
        if let Some(v) = self.c.suggestions.borrow().get(w) {
            return v.clone();
        }
        let v: Vec<String> = self.an.suggest(w, 5).iter().map(|s| lower(s)).collect();
        self.c.suggestions.borrow_mut().insert(w.to_string(), v.clone());
        v
    }

    fn known(&self, w: &str) -> bool {
        if let Some(&k) = self.c.known.borrow().get(w) {
            return k;
        }
        let k = self.an.check(w).status != Status::Unknown;
        self.c.known.borrow_mut().insert(w.to_string(), k);
        k
    }

    /// Forms of the same word with another tag, keeping its prefix: laiką -> laiko.
    fn inflect(&self, a: &Analysis, tag: &str) -> Vec<String> {
        let Some(&tid) = self.an.data.tag_ids.get(tag) else { return vec![] };
        let mut out: Vec<String> = Vec::new();
        for (form, t) in self.an.data.entry_forms(a.entry) {
            let f = format!("{}{}", a.prefix, form);
            if t == tid && !out.contains(&f) && !self.an.analyze_exact(&f).is_empty() {
                out.push(f);
            }
        }
        out
    }

    fn reinflect(&self, w: &Word, keep: impl Fn(&str) -> bool, case: Option<&str>) -> Vec<String> {
        let mut out: Vec<String> = Vec::new();
        for a in self.analyses(&w.text) {
            let t = self.tag(&a);
            if keep(t) {
                for f in self.inflect(&a, &retag(t, case, None)) {
                    let f = w.cap(&f);
                    if !out.contains(&f) && f != w.text {
                        out.push(f);
                    }
                }
            }
        }
        out
    }

    fn mostly_verb(&self, analyses: &[Analysis]) -> bool {
        if analyses.iter().any(|a| self.tag(a) == "W") {
            return false;
        }
        let (mut verb, mut other) = (0u32, 0u32);
        for a in analyses {
            let f = *self.an.data.lemma_freq.get(&lower(&a.lemma)).unwrap_or(&0);
            if self.tag(a).starts_with("V.") {
                verb = verb.max(f);
            } else {
                other = other.max(f).max(1);
            }
        }
        other == 0 || verb > other
    }

    /// A listed particle/adverb reading that is the frequent one: labai (very), not labas.
    fn mostly_particle(&self, analyses: &[Analysis]) -> bool {
        let w = analyses.iter().filter(|a| self.tag(a) == "W").map(|a| self.lemma_freq(a) as i64).max().unwrap_or(-1);
        w > 0 && analyses.iter().all(|a| self.lemma_freq(a) as i64 <= w)
    }

    /// Every reading is an active participle (or a gerund): stovintis, nukritusią.
    fn active_participle(&self, w: &str) -> bool {
        let an = self.analyses(w);
        !an.is_empty() && an.iter().all(|a| { let t = self.tag(a); t.starts_with("V.pap.") || t.starts_with("V.pprs.") || t.starts_with("V.ger.") })
    }

    /// Only adverb or particle readings: vakar, dar, tikrai (not tikras).
    fn adverb(&self, w: &str) -> bool {
        let an = self.analyses(w);
        !an.is_empty() && an.iter().all(|a| matches!(self.tag(a), "W" | "Adv"))
    }

    fn word(&self, text: String, start: usize, end: usize) -> Word {
        let own = self.readings_of(&text);
        let known = self.known(&text);
        Word { lower: lower(&text), text, start, end, own, known, variants: OnceCell::new() }
    }
}

impl Word {
    fn variants(&self, g: &G) -> &Vec<(String, Vec<Reading>)> {
        self.variants.get_or_init(|| {
            let mut forms = g.variants_of(&self.lower);
            if forms.is_empty() && !self.known {
                // unknown word without a diacritic-only reading: let context choose
                // between its typo corrections (zodzou -> žodžiu, žodžių)
                forms = g.suggestions_of(&self.text);
            }
            if first_lower(&self.text) {
                forms.retain(|f| first_lower(f));
            }
            forms.into_iter().map(|f| { let r = g.readings_of(&f); (f, r) }).collect()
        })
    }
    fn pos_readings(&self, g: &G) -> Vec<Reading> {
        if !self.own.is_empty() || self.known {
            return self.own.clone();
        }
        self.variants(g).iter().flat_map(|(_, rs)| rs.iter().cloned()).collect()
    }
    fn is_noun(&self, g: &G) -> bool {
        self.pos_readings(g).iter().any(|r| r.pos == Pos::Noun)
    }
    fn is_adj(&self, g: &G) -> bool {
        let rs = self.pos_readings(g);
        rs.iter().any(|r| r.pos == Pos::Adj) && !rs.iter().any(|r| r.pos == Pos::Noun)
    }
    fn is_participle(&self, g: &G) -> bool {
        let rs: Vec<Reading> = self.pos_readings(g).into_iter().filter(|r| r.pos == Pos::Adj).collect();
        !rs.is_empty() && rs.iter().all(|r| r.participle)
    }
    fn can_be(&self, g: &G, case: &str) -> bool {
        self.pos_readings(g).iter().any(|r| r.case == case)
    }
    fn can_be_verb(&self, g: &G) -> bool {
        for a in g.analyses(&self.text) {
            let p = g.parts(&a);
            if p[0] == "V" && p.len() > 1 && FINITE.contains(&p[1].as_str()) {
                let mut vp = a.prefix.as_str();
                for neg in ["nebe", "tebe", "ne", "be", "te"] {
                    if let Some(r) = vp.strip_prefix(neg) {
                        vp = r;
                        break;
                    }
                }
                if vp.is_empty() || vp == "si" {
                    return true;
                }
            }
        }
        false
    }
    fn is_quantity(&self, g: &G) -> bool {
        QUANTIFIER_WORDS.contains(&self.lower.as_str())
            || g.analyses(&self.text).iter().any(|a| {
                (QUANTIFIER_LEMMAS.contains(&lower(&a.lemma).as_str()) && matches!(a.kind, Kind::Noun | Kind::Num))
                    || (a.kind == Kind::Num && (a.lemma.ends_with("lika") || a.lemma.ends_with("dešimt")))
            })
    }
    fn is_comparative(&self, g: &G) -> bool {
        g.analyses(&self.text).iter().any(|a| g.tag(a).contains(".cmp"))
    }
    fn cap(&self, form: &str) -> String {
        cap_like(&self.text, form)
    }
}

fn phrase_stop(w: &str) -> bool {
    PHRASE_STOP.contains(&w) || CLAUSE_STARTERS.contains(&w) || KURIS.contains(&w)
}

fn could_agree(g: &G, w1: &Word, w2: &Word) -> bool {
    let mut r1 = w1.pos_readings(g);
    r1.extend(w1.variants(g).iter().flat_map(|(_, rs)| rs.iter().cloned()));
    let mut r2 = w2.pos_readings(g);
    r2.extend(w2.variants(g).iter().flat_map(|(_, rs)| rs.iter().cloned()));
    r1.iter().any(|a| r2.iter().any(|b| agree(a, b)))
}

impl Grammar {
    pub fn check(&self, an: &Analyzer, text: &str) -> Vec<Issue> {
        let g = G { an, c: self };
        let chars: Vec<char> = text.chars().collect();
        let spans = word_spans(&chars);
        let toks: Vec<Word> = spans.iter().map(|&(a, b)| g.word(substr(&chars, a, b), a, b)).collect();
        let adjacent: Vec<bool> = (0..toks.len())
            .map(|i| i > 0 && chars[toks[i - 1].end..toks[i].start].iter().all(|c| c.is_whitespace()))
            .collect();
        let mut issues: BTreeMap<usize, Issue> = BTreeMap::new();
        let add = |issues: &mut BTreeMap<usize, Issue>, x: Issue| {
            issues.entry(x.start).or_insert(x);
        };

        // participles end the phrase unless allowed (radau nukritusią sagutę)
        let phrase = |i: usize, participles: bool| -> Vec<usize> {
            let mut span: Vec<usize> = Vec::new();
            let mut j = i + 1;
            while j < toks.len() && adjacent[j] {
                let w = &toks[j];
                if let Some(&last) = span.last() {
                    if !could_agree(&g, &toks[last], w) {
                        break;
                    }
                }
                if w.is_noun(&g) {
                    span.push(j);
                    break;
                }
                if !w.is_adj(&g) || (w.is_participle(&g) && !participles) {
                    break;
                }
                span.push(j);
                j += 1;
            }
            span
        };

        let require = |issues: &mut BTreeMap<usize, Issue>, w: &Word, cases: &[&str], rule: &'static str, why: &str| {
            if w.own.iter().any(|r| cases.contains(&r.case)) {
                return;
            }
            if !cases.contains(&"gen") && w.own.iter().any(|r| r.case == "gen") {
                return;
            }
            let mut variants: Vec<&(String, Vec<Reading>)> =
                w.variants(&g).iter().filter(|(_, rs)| rs.iter().any(|r| cases.contains(&r.case))).collect();
            // an unknown word's candidates: prefer those agreeing with the adjective before it
            // (nepataiso visų zodziou -> žodžių, not žodžio)
            let i = toks.iter().position(|t| t.start == w.start).unwrap();
            if !w.known && i > 0 && adjacent[i] && toks[i - 1].known && toks[i - 1].is_adj(&g) {
                let prev = &toks[i - 1]; // its diacritic variants too: visu (not fixed yet) -> visų
                let ar: Vec<Reading> = prev
                    .pos_readings(&g)
                    .into_iter()
                    .chain(prev.variants(&g).iter().flat_map(|(_, rs)| rs.iter().cloned()))
                    .filter(|r| r.pos == Pos::Adj)
                    .collect();
                variants.sort_by_key(|(_, rs)| {
                    !ar.iter().any(|x| rs.iter().any(|y| y.pos == Pos::Noun && cases.contains(&y.case) && agree(x, y)))
                });
            }
            let fixes: Vec<String> = variants.iter().map(|(f, _)| w.cap(f)).collect();
            if fixes.is_empty() || (w.known && w.own.is_empty()) {
                return;
            }
            let rule = if w.known { rule } else { "context" };
            add(issues, Issue { start: w.start, end: w.end, word: w.text.clone(), rule, message: why.to_string(), suggestions: fixes });
        };

        let verb_at = |k: usize| {
            let an_k = g.analyses(&toks[k].text);
            an_k.iter().any(|a| g.finite(a)) && g.mostly_verb(&an_k)
        };
        let gap_of = |i: usize| -> String { if i == 0 { String::new() } else { chars[toks[i - 1].end..toks[i].start].iter().collect() } };
        let starts_sentence = |i: usize| i == 0 || gap_of(i).chars().any(|c| SENTENCE_GAP.contains(c));
        let has_finite = |k: usize| g.analyses(&toks[k].text).iter().any(|a| g.finite(a));
        // kuria / kuriu as the verb kurti, not kuris: Įmonė kuria ir parduoda, (aš) kuriu tai, kas reikalinga
        let verb_with_object = |i: usize| {
            if !has_finite(i) || i + 1 >= toks.len() || !adjacent[i + 1] {
                return false;
            }
            let nx = &toks[i + 1];
            if VERB_OBJECTS.contains(&nx.lower.as_str()) || (i > 0 && adjacent[i] && KURIS.contains(&toks[i - 1].lower.as_str())) {
                return true; // kuri kuria, kurie kuria: the relative pronoun is the one before
            }
            if nx.known && !nx.own.is_empty() && nx.own.iter().all(|r| r.pos == Pos::Noun && r.case == "acc") {
                return true; // kuria baldus
            }
            // kuria ir parduoda; at the end of the text wait for the next word (the keyboard types on)
            ["ir", "bei", "arba"].contains(&nx.lower.as_str()) && (i + 2 == toks.len() || adjacent[i + 2] && verb_at(i + 2))
        };

        for (i, w) in toks.iter().enumerate() {
            let nxt_adjacent = i + 1 < toks.len() && adjacent[i + 1];
            // 1. prepositions (also recognised without diacritics: pries, is, i, uz)
            let prep: Option<&str> = if prep_cases(&w.lower).is_some() {
                PREP_LIST.iter().find(|p| **p == w.lower).copied()
            } else if !w.known {
                let f = fold(&w.lower);
                PREP_LIST.iter().find(|p| fold(p) == f).copied()
            } else {
                None
            };
            if let (Some(prep), true) = (prep, nxt_adjacent) {
                let span = phrase(i, false);
                let numeral = !span.is_empty() && g.analyses(&toks[span[0]].text).iter().any(|a| a.kind == Kind::Num);
                if !span.is_empty()
                    && toks[*span.last().unwrap()].is_noun(&g)
                    && !numeral
                    && !(prep == "apie" && toks[span[0]].is_quantity(&g))
                {
                    let cases = prep_cases(prep).unwrap();
                    let want = cases.iter().map(|c| case_name(c)).collect::<Vec<_>>().join(" or ");
                    for &x in &span {
                        require(&mut issues, &toks[x], cases, "case", &format!("'{prep}' takes the {want}"));
                    }
                }
            }
            // 2b. numbers: 10 metu -> metų (a noun right after the number: not units "20 m atstumu",
            // manner "12 etniniu pagrindu", labels "KNM-ER 1813 atveju")
            let gap: String = chars[if i > 0 { toks[i - 1].end } else { 0 }..w.start].iter().collect();
            if let Some(n) = gen_number(&gap) {
                let upper = |t: &str| t.chars().any(|c| c.is_uppercase()) && !t.chars().any(|c| c.is_lowercase());
                if w.known && w.is_noun(&g) && clen(&w.lower) >= 3
                    && w.text.chars().next().is_some_and(|c| c.is_lowercase())
                    && !(i > 0 && clen(&toks[i - 1].text) > 1 && upper(&toks[i - 1].text))
                {
                    require(&mut issues, w, &["gen"], "quantity", &format!("after '{n}' use the genitive plural"));
                }
            }
            // 3. quantity words
            if nxt_adjacent && w.is_quantity(&g) {
                let span = phrase(i, false);
                if !span.is_empty()
                    && toks[*span.last().unwrap()].is_noun(&g)
                    && !span.iter().any(|&x| toks[x].is_comparative(&g))
                {
                    for &x in &span {
                        require(&mut issues, &toks[x], &["gen"], "quantity", &format!("after '{}' use the genitive", w.text));
                    }
                }
            }
            // 4. commas
            let lw = w.lower.as_str();
            let is_kuris = KURIS.contains(&lw);
            if i > 0 && (CLAUSE_STARTERS.contains(&lw) || is_kuris) && adjacent[i] {
                let prev = toks[i - 1].lower.as_str();
                let nxt = if nxt_adjacent { toks[i + 1].lower.as_str() } else { "" };
                let indefinite = INTERROGATIVES.contains(&nxt) || KURIS.contains(&nxt)
                    || nxt.starts_with("kok") || nxt.starts_with("kur") || nxt.starts_with("kie");
                let skip = NO_COMMA_AFTER.contains(&prev)
                    || prep_cases(prev).is_some()
                    || first_upper(&w.text)
                    || chars.get(w.end) == Some(&'.')
                    || ((lw == "bet" || lw == "kai") && indefinite)
                    || (lw == "nors" && (interrogative_folded(&fold(prev)) || nxt == "ir")) // kas nors, koki nors
                    || (is_kuris && (prev == "bet" || prev == "kai" || verb_with_object(i)     // įmonė kuria ir parduoda
                        || ["nors", "laikui", "laiką", "laiko"].contains(&nxt)));
                if !skip {
                    add(&mut issues, Issue {
                        start: w.start, end: w.end, word: w.text.clone(), rule: "comma",
                        message: format!("comma needed before '{}'", w.text),
                        suggestions: vec![format!(", {}", w.text)],
                    });
                } else if (prev == "net" || prev == "ypač") // veikia, net jeigu ...
                    && i >= 2
                    && adjacent[i - 1]
                    && !NO_COMMA_AFTER.contains(&toks[i - 2].lower.as_str())
                    && prep_cases(&toks[i - 2].lower).is_none()
                    && !first_upper(&w.text)
                    && !first_upper(&toks[i - 1].text)
                {
                    let p = &toks[i - 1];
                    add(&mut issues, Issue {
                        start: p.start, end: p.end, word: p.text.clone(), rule: "comma",
                        message: format!("comma needed before '{} {}'", p.text, w.text),
                        suggestions: vec![format!(", {}", p.text)],
                    });
                }
            }
            if i > 0 && prep_cases(lw).is_some() && adjacent[i] && nxt_adjacent
                && KURIS.contains(&toks[i + 1].lower.as_str())
                && !NO_COMMA_AFTER.contains(&toks[i - 1].lower.as_str())
            {
                add(&mut issues, Issue {
                    start: w.start, end: w.end, word: w.text.clone(), rule: "comma",
                    message: format!("comma needed before '{} {}'", w.text, toks[i + 1].text),
                    suggestions: vec![format!(", {}", w.text)],
                });
            }
        }

        // a preposition that lost its diacritic and became a verb: kabo virs stalo -> virš
        // (only when the clause has another verb: mama virs sriubos = will boil)
        for (i, w) in toks.iter().enumerate() {
            let f = fold(&w.lower);
            let Some(prep) = PREP_LIST.iter().find(|p| fold(p) == f).copied() else { continue };
            if prep == w.lower || !w.known || i + 1 >= toks.len() || !adjacent[i + 1] {
                continue;
            }
            let span = phrase(i, false);
            let cases = prep_cases(prep).unwrap();
            if span.is_empty()
                || !toks[*span.last().unwrap()].is_noun(&g)
                || !span.iter().all(|&x| toks[x].known && cases.iter().any(|c| toks[x].can_be(&g, c)))
            {
                continue;
            }
            let mut j = i;
            while j > 0 && !starts_sentence(j) {
                j -= 1;
            }
            if (j..i).any(|k| verb_at(k)) {
                add(&mut issues, Issue {
                    start: w.start, end: w.end, word: w.text.clone(), rule: "case",
                    message: format!("'{}' before '{}' is the preposition '{prep}'", w.text, toks[*span.last().unwrap()].text),
                    suggestions: vec![w.cap(prep)],
                });
            }
        }

        // indefinite pronoun typed without diacritics: koki nors -> kokį nors, ka nors -> ką nors
        for i in 0..toks.len().saturating_sub(1) {
            let w = &toks[i];
            let l = w.lower.as_str();
            if toks[i + 1].lower != "nors" || !adjacent[i + 1] || INTERROGATIVES.contains(&l) || KURIS.contains(&l) {
                continue;
            }
            let fix: Vec<String> = w.variants(&g).iter()
                .filter(|(f, _)| { let fl = lower(f); INTERROGATIVES.contains(&fl.as_str()) || KURIS.contains(&fl.as_str()) })
                .map(|(f, _)| w.cap(f)).collect();
            if !fix.is_empty() {
                add(&mut issues, Issue {
                    start: w.start, end: w.end, word: w.text.clone(), rule: if w.known { "case" } else { "context" },
                    message: format!("'{} nors': an indefinite pronoun", w.text), suggestions: fix,
                });
            }
        }

        // 6. relative pronoun typed without diacritics: žodžių kuriu aš rašau -> kurių
        for i in 1..toks.len() {
            let (w, prev) = (&toks[i], &toks[i - 1]);
            let gap: String = chars[prev.end..w.start].iter().collect();
            if KURIS_ACC.contains(&w.lower.as_str()) || !(adjacent[i] || gap.trim() == ",") || !prev.is_noun(&g) {
                continue;
            }
            let fw = fold(&w.lower);
            let nouns: Vec<Reading> = prev.pos_readings(&g).into_iter().filter(|r| r.pos == Pos::Noun).collect();
            let agrees = |feats: &[(&str, Option<&str>)]| {
                nouns.iter().any(|r| feats.iter().any(|(num, gen)| {
                    (r.number.is_none() || r.number == Some(num)) && (gen.is_none() || r.gender.is_none() || r.gender == *gen)
                }))
            };
            if KURIS.contains(&w.lower.as_str()) {
                // its case comes from the verb of the clause: knyga kuria skaičiau -> kurią
                let mut cands: Vec<String> = KURIS_ACC.iter()
                    .filter(|k| fold(k) == fw && agrees(KURIS_FEATURES.iter().find(|(f, _)| f == *k).unwrap().1))
                    .map(|k| w.cap(k)).collect();
                let mut j = i + 1;
                let mut hit = false;
                while j < toks.len() && j <= i + 2 && adjacent[j] && !phrase_stop(&toks[j].lower) {
                    let an_j = g.analyses(&toks[j].text);
                    // (skaičiau is a verb here although the noun skaičius is more frequent)
                    if an_j.iter().any(|a| {
                        g.finite(a) && TRANSITIVE_VERBS.iter().any(|v| a.lemma.ends_with(v))
                            && !a.prefix.starts_with("ne") && !g.tag(a).ends_with(".refl")
                    }) {
                        hit = true;
                        break;
                    }
                    if an_j.iter().any(|a| g.finite(a)) && g.mostly_verb(&an_j) {
                        break;
                    }
                    j += 1;
                }
                if !hit {
                    cands.clear();
                }
                if !cands.is_empty() {
                    add(&mut issues, Issue {
                        start: w.start, end: w.end, word: w.text.clone(), rule: "relative",
                        message: format!("'{}' takes an accusative object", toks[j].text), suggestions: cands,
                    });
                }
                continue;
            }
            let cands: Vec<String> = KURIS_FEATURES.iter()
                .filter(|(k, feats)| fold(k) == fw && agrees(feats))
                .map(|(k, _)| w.cap(k)).collect();
            if cands.is_empty() || verb_with_object(i) {
                continue;
            }
            // the relative clause needs its own verb, else "kuriu" may be the verb ("dainas kuriu pats")
            let mut verb_follows = false;
            let mut j = i + 1;
            while j < toks.len() && j <= i + 5 && adjacent[j] {
                let an_j = g.analyses(&toks[j].text);
                if an_j.iter().any(|a| g.finite(a)) && g.mostly_verb(&an_j) {
                    verb_follows = true;
                    break;
                }
                j += 1;
            }
            if verb_follows {
                add(&mut issues, Issue {
                    start: w.start, end: w.end, word: w.text.clone(), rule: "relative",
                    message: format!("relative pronoun after '{}'", prev.text), suggestions: cands,
                });
            }
        }

        // 7. comma before an indirect question after a verb of seeing, knowing or saying:
        //    matau, ką man rašo / nežinau, kur jis gyvena (not: ką nors, ką tik)
        for i in 1..toks.len() {
            let (w, prev) = (&toks[i], &toks[i - 1]);
            if !INTERROGATIVES.contains(&w.lower.as_str())
                || !adjacent[i]
                || w.text.chars().next().is_some_and(|c| c.is_uppercase())
            {
                continue;
            }
            let nxt = if i + 1 < toks.len() && adjacent[i + 1] { toks[i + 1].lower.as_str() } else { "" };
            if ["nors", "tik", "ne"].contains(&nxt) {
                continue;
            }
            // a relative clause after a demonstrative: kuriu tai, kas reikalinga / viską, ką turiu
            // ("Tai kas dabar?" at the start of a sentence is a question)
            if KAS_FORMS.contains(&w.lower.as_str())
                && DEMONSTRATIVES.contains(&prev.lower.as_str())
                && !nxt.is_empty()
                && !(prev.lower == "tai" && (i < 2 || !adjacent[i - 1]))
                && !(i >= 2 && adjacent[i - 1] && prep_cases(&toks[i - 2].lower).is_some())
            {
                add(&mut issues, Issue {
                    start: w.start, end: w.end, word: w.text.clone(), rule: "comma",
                    message: format!("comma needed before '{}' after '{}'", w.text, prev.text),
                    suggestions: vec![format!(", {}", w.text)],
                });
                continue;
            }
            let pa = g.analyses(&prev.text);
            if !(pa.iter().any(|a| g.finite(a) && QUESTION_VERBS.iter().any(|v| a.lemma.ends_with(v))) && g.mostly_verb(&pa)) {
                continue;
            }
            // the question needs a verb of its own
            let mut verb_follows = false;
            let mut j = i + 1;
            while j < toks.len() && j <= i + 5 && adjacent[j] {
                let an_j = g.analyses(&toks[j].text);
                if an_j.iter().any(|a| g.finite(a)) && g.mostly_verb(&an_j) {
                    verb_follows = true;
                    break;
                }
                j += 1;
            }
            if verb_follows {
                add(&mut issues, Issue {
                    start: w.start, end: w.end, word: w.text.clone(), rule: "comma",
                    message: format!("comma needed before '{}'", w.text), suggestions: vec![format!(", {}", w.text)],
                });
            }
        }

        // 8. more commas: parenthetical words, greetings and address, repeated connectives,
        //    participial phrases, lists
        let comma_before = |issues: &mut BTreeMap<usize, Issue>, k: usize, why: String| {
            if k < toks.len() && adjacent[k] {
                let t = &toks[k];
                add(issues, Issue {
                    start: t.start, end: t.end, word: t.text.clone(), rule: "comma", message: why,
                    suggestions: vec![format!(", {}", t.text)],
                });
            }
        };
        let connective = |t: &Word| {
            let l = t.lower.as_str();
            NO_COMMA_AFTER.contains(&l) || CLAUSE_STARTERS.contains(&l) || KURIS.contains(&l) || prep_cases(l).is_some()
        };
        for (i, w) in toks.iter().enumerate() {
            let nxt_adjacent = i + 1 < toks.len() && adjacent[i + 1];
            let lw = w.lower.as_str();
            // Deja, neatėjo. / Kita vertus, ... / Jis, beje, sutiko.
            if starts_sentence(i) && nxt_adjacent {
                let pair = i + 2 < toks.len() && adjacent[i + 2] && INTRO_PAIRS.contains(&(lw, toks[i + 1].lower.as_str()));
                if pair {
                    comma_before(&mut issues, i + 2, format!("comma needed after '{} {}'", w.text, toks[i + 1].text));
                } else if INTRO_START.contains(&lw) && !first_upper(&toks[i + 1].text) {
                    let nx = &toks[i + 1];
                    // žinoma = "it is known" (Žinoma tik viena rūšis): only before a subject or verb
                    if lw != "žinoma" || SUBJECT_PRONOUNS.contains(&nx.lower.as_str()) || verb_at(i + 1) {
                        comma_before(&mut issues, i + 1, format!("comma needed after '{}'", w.text));
                    }
                }
            } else if INTRO_ANYWHERE.contains(&lw) && !first_upper(&w.text) && adjacent[i] && !connective(&toks[i - 1]) {
                comma_before(&mut issues, i, format!("'{}' is set off by commas", w.text));
                if nxt_adjacent {
                    comma_before(&mut issues, i + 1, format!("'{}' is set off by commas", w.text));
                }
            }
            // Labas, Jonai, kaip sekasi? / Ačiū, drauge.
            // (the gap may already hold the first comma: Labas, Jonai kaip ...)
            if starts_sentence(i) && GREETINGS.contains(&lw) && i + 1 < toks.len()
                && (adjacent[i + 1] || gap_of(i + 1).trim() == ",")
            {
                let nx = &toks[i + 1];
                let vocative = nx.known
                    && nx.own.iter().any(|r| r.case == "voc")
                    && !g.readings_of(lw).iter().filter(|a| a.pos == Pos::Adj).any(|a| nx.own.iter().any(|b| agree(a, b)));
                if vocative {
                    comma_before(&mut issues, i + 1, format!("the address '{}' is set off by commas", nx.text));
                    if i + 2 < toks.len() && adjacent[i + 2] && !toks[i + 2].own.iter().any(|r| r.case == "voc") {
                        comma_before(&mut issues, i + 2, format!("the address '{}' is set off by commas", nx.text));
                    }
                } else if SUBJECT_PRONOUNS.contains(&nx.lower.as_str())
                    || INTERROGATIVES.contains(&nx.lower.as_str())
                    || KURIS.contains(&nx.lower.as_str())
                {
                    comma_before(&mut issues, i + 1, format!("comma needed after '{}'", w.text));
                }
            }
            // comparison with a clause: geriau, negu tikėjausi
            if lw == "negu" && i > 0 && adjacent[i] && !connective(&toks[i - 1]) {
                let mut j = i + 1;
                while j < toks.len() && j <= i + 3 && adjacent[j] && !verb_at(j) {
                    j += 1;
                }
                if j < toks.len() && j <= i + 3 && adjacent[j] && verb_at(j) {
                    comma_before(&mut issues, i, format!("comma needed before '{}' + clause", w.text));
                }
            }
            // repeated connectives: nei Jonas, nei Petras / arba tu, arba aš / ar ateisi, ar ne
            // ("ar" = "or" in a sentence: only the question particle at the start counts)
            if ["nei", "arba", "ar"].contains(&lw) && (starts_sentence(i) || (lw != "ar" && gap_of(i).trim() == ",")) {
                let mut j = i + 1;
                while j < toks.len() && j <= i + 6 && adjacent[j] && toks[j].lower != w.lower {
                    j += 1;
                }
                if j < toks.len() && j <= i + 6 && adjacent[j] && j > i + 1 && !connective(&toks[j - 1]) {
                    comma_before(&mut issues, j, format!("repeated '{}': comma before the second one", w.text));
                }
            }
            // participial phrase after its noun: Žmogus, stovintis prie lango, žiūri
            if i > 0 && adjacent[i] && nxt_adjacent && toks[i - 1].known
                && !phrase_stop(&toks[i + 1].lower) && g.active_participle(&w.text)
            {
                let nr: Vec<&Reading> = toks[i - 1].own.iter().filter(|r| r.pos == Pos::Noun).collect();
                // a nominative past participle is mostly a predicate: Pavadinimas kilęs iš ..., Miestas įsikūręs
                let pap = g.analyses(&w.text).iter().any(|a| g.tag(a).starts_with("V.pap."));
                let pr: Vec<&Reading> = w.own.iter().filter(|r| r.pos == Pos::Adj && !(r.case == "nom" && pap)).collect();
                let agreeing: Vec<&Reading> = nr.iter().copied().filter(|b| pr.iter().any(|a| agree(a, b))).collect();
                let later = (i + 1..(i + 4).min(toks.len())).filter(|&k| adjacent[k]).any(|k| {
                    first_upper(&toks[k].text)
                        || pr.iter().any(|a| toks[k].own.iter().any(|b| b.pos == Pos::Noun && agree(a, b)))
                });
                // nominative: a predicate unless the sentence has a verb of its own (Laumės mėgstančios ...)
                let mut j = i;
                while j > 0 && !starts_sentence(j) {
                    j -= 1;
                }
                let sentence_verb = (j..(i + 8).min(toks.len()))
                    .filter(|&k| k != i && (k < i || (i + 1..=k).all(|m| adjacent[m])))
                    .any(|k| verb_at(k));
                if !agreeing.is_empty()
                    && !later // žygiavusia Aleksandro kariauna: attribute of the later noun
                    && agreeing.iter().any(|b| b.case != "gen") // upės buvusios ...: genitive chains are ambiguous
                    && (sentence_verb || agreeing.iter().all(|b| b.case != "nom"))
                {
                    comma_before(&mut issues, i, format!("the phrase '{} …' is set off by commas", w.text));
                    let mut j = i + 1;
                    while j < toks.len() && j <= i + 6 && adjacent[j] && !phrase_stop(&toks[j].lower) {
                        if verb_at(j) {
                            comma_before(&mut issues, j, format!("the phrase '{} …' is set off by commas", w.text));
                            break;
                        }
                        j += 1;
                    }
                }
            }
            // list: obuoliai, kriaušės ir slyvos
            if i > 0 && adjacent[i] && i + 2 < toks.len() && adjacent[i + 1] && adjacent[i + 2]
                && ["ir", "bei", "arba"].contains(&toks[i + 1].lower.as_str())
                && toks[i - 1].lower != w.lower
            {
                // tomis pačiomis spalvomis ir ...: a modifier may cover more than one word
                let modified = i >= 2 && adjacent[i - 1] && toks[i - 2].is_adj(&g);
                let three = [&toks[i - 1], w, &toks[i + 2]];
                // no genitive readings at all: bangos amplitudės ir fazės = "the wave's amplitude and phase"
                if !modified && three.iter().all(|t| {
                    t.known && first_lower(&t.text) && !t.own.is_empty()
                        && t.own.iter().all(|r| r.pos == Pos::Noun && r.case != "gen")
                }) {
                    let shared = three[0].own.iter().any(|r| {
                        three[1..].iter().all(|t| t.own.iter().any(|x| x.case == r.case && x.number == r.number))
                    });
                    let timey = three.iter().any(|t| g.analyses(&t.text).iter().any(|a| TIME_LEMMAS.contains(&a.lemma.as_str())));
                    if shared && !timey {
                        comma_before(&mut issues, i, format!("comma between list items '{}' and '{}'", toks[i - 1].text, w.text));
                    }
                }
            }
        }

        // an adverb that may stand between a verb and its object or subject: vakar, labai
        let between = |k: usize| {
            let t = &toks[k];
            let l = t.lower.as_str();
            (g.adverb(&t.text) || g.mostly_particle(&g.analyses(&t.text)))
                && !SUBJECT_NO_SKIP.contains(&l) && subject_person(l).is_none() && !NO_COMMA_AFTER.contains(&l)
                && !CLAUSE_STARTERS.contains(&l) && !KURIS.contains(&l) && prep_cases(l).is_none()
                && !INTERROGATIVES.contains(&l) && !t.is_quantity(&g)
        };
        // the verb at i has its subject in front of it: jis (vakar) nupirko, mano mama skaito
        let subject_before = |i: usize| {
            let mut k = i as isize - 1;
            while k >= 0 && adjacent[k as usize + 1] && between(k as usize) {
                k -= 1;
            }
            if k < 0 || !adjacent[k as usize + 1] {
                return false;
            }
            let k = k as usize;
            let t = &toks[k];
            if ["jis", "ji", "jie"].contains(&t.lower.as_str()) {
                return k == 0 || !COORDINATORS.contains(&toks[k - 1].lower.as_str()) || !adjacent[k];
            }
            // a noun that can only be the subject (not Knygą skaito mama, not kas/ką); by its most
            // frequent lemma (Jonas, not the accusative plural of Jona); mama is also instrumental
            let nouns: Vec<Analysis> = g.analyses(&t.text).into_iter().filter(|a| g.tag(a).starts_with("N.")).collect();
            let top = nouns.iter().map(|a| g.lemma_freq(a)).max().unwrap_or(0);
            let cases: Vec<&str> = nouns.iter().filter(|a| g.lemma_freq(a) == top)
                .map(|a| g.parts(a).last().unwrap().as_str()).collect();
            t.known && t.is_noun(&g)
                && cases.iter().all(|c| ["nom", "voc", "ins"].contains(c)) && cases.contains(&"nom")
                && !INTERROGATIVES.contains(&t.lower.as_str()) && !KURIS.contains(&t.lower.as_str())
                && !CLAUSE_WORDS.contains(&t.lower.as_str())
                && !(k > 0 && adjacent[k] && COORDINATORS.contains(&toks[k - 1].lower.as_str()))
        };

        // 5. verbs: negation + genitive, objects of 1st/2nd person verbs
        for (i, w) in toks.iter().enumerate() {
            if i + 1 >= toks.len() || !adjacent[i + 1] {
                continue;
            }
            let alls = g.analyses(&w.text);
            let verbs: Vec<&Analysis> = alls.iter().filter(|a| g.finite(a) || g.tag(a) == "V.inf").collect();
            if verbs.is_empty() || !g.mostly_verb(&alls) {
                continue;
            }
            if w.own.iter().any(|r| r.pos == Pos::Adj) && could_agree(&g, w, &toks[i + 1]) {
                continue;
            }
            let copula = verbs.iter().any(|a| COPULAS.contains(&a.lemma.as_str()))
                || COPULAS.contains(&w.lower.as_str())
                || COPULA_FORMS.contains(&w.lower.as_str());
            let nxt = &toks[i + 1];
            let negated = verbs.iter().any(|a| a.prefix.starts_with("ne"));

            if negated && !copula {
                if let Some(gen) = neg_pronoun(&nxt.lower) {
                    add(&mut issues, Issue {
                        start: nxt.start, end: nxt.end, word: nxt.text.clone(), rule: "negation",
                        message: format!("after the negated verb '{}' use the genitive", w.text),
                        suggestions: vec![nxt.cap(gen)],
                    });
                    continue;
                }
                let span = phrase(i, false);
                let timey = span.iter().any(|&x| {
                    let t = &toks[x];
                    TIME_WORDS.contains(&t.lower.as_str())
                        || t.is_quantity(&g)
                        || g.analyses(&t.text).iter().any(|a| TIME_LEMMAS.contains(&a.lemma.as_str()))
                });
                // an adverb reading is not an object: neatėjo laiku (on time), not laikų
                let adverbial = span.len() == 1
                    && g.analyses(&toks[span[0]].text).iter().any(|a| matches!(g.tag(a), "W" | "Adv"));
                if !span.is_empty() && toks[*span.last().unwrap()].is_noun(&g) && !timey && !adverbial {
                    for &x in &span {
                        let t = &toks[x];
                        let why = format!("after the negated verb '{}' use the genitive", w.text);
                        if !t.own.is_empty() && t.own.iter().all(|r| r.case == "acc") {
                            let fix = g.reinflect(t, |tg| tg.ends_with(".acc"), Some("gen"));
                            if !fix.is_empty() {
                                add(&mut issues, Issue {
                                    start: t.start, end: t.end, word: t.text.clone(), rule: "negation",
                                    message: why, suggestions: fix,
                                });
                                continue;
                            }
                        }
                        require(&mut issues, t, &["gen"], "negation", &why); // nepataiso visu žodžių -> visų
                    }
                }
                continue;
            }

            // verbs with a genitive object: lauksiu tavo zinutes -> žinutės, reikia pagalbą -> pagalbos
            if !negated && verbs.iter().any(|a| GENITIVE_VERBS.iter().any(|v| {
                a.lemma == *v || (a.lemma.ends_with(v) && VERB_PREFIXES.contains(&&a.lemma[..a.lemma.len() - v.len()]))
            })) {
                let mut k = i; // possessives stand before the noun: laukiu tavo žinutės
                while k + 1 < toks.len() && adjacent[k + 1] && POSSESSIVES.contains(&toks[k + 1].lower.as_str()) {
                    k += 1;
                }
                let span = phrase(k, false);
                let timey = span.iter().any(|&x| {
                    let t = &toks[x];
                    TIME_WORDS.contains(&t.lower.as_str())
                        || t.is_quantity(&g)
                        || g.analyses(&t.text).iter().any(|a| TIME_LEMMAS.contains(&a.lemma.as_str()))
                });
                if !span.is_empty() && toks[*span.last().unwrap()].is_noun(&g) && !timey {
                    for &x in &span {
                        require(&mut issues, &toks[x], &["gen"], "case", &format!("'{}' takes the genitive", w.text));
                    }
                }
                continue;
            }

            let persons: Vec<&str> = verbs.iter().filter(|a| g.finite(a)).map(|a| g.parts(a)[2].as_str()).collect();
            let transitive = verbs.iter().any(|a| TRANSITIVE_VERBS.iter().any(|v| a.lemma.ends_with(v)));
            // a real prefix, not reflexive: pamato, nupirko (not atsirado = atsi+rado)
            let plain_transitive = verbs.iter().any(|a| {
                TRANSITIVE_VERBS.iter().any(|v| {
                    a.lemma == *v || (a.lemma.ends_with(v) && VERB_PREFIXES.contains(&&a.lemma[..a.lemma.len() - v.len()]))
                }) && !a.prefix.contains("si")
            });
            // objects after a 1st/2nd person verb can't be its subject: matau namas -> namą;
            // nor after a 3rd person transitive verb whose subject came before it: Jonas mato namas
            if !persons.is_empty()
                && (persons.iter().all(|p| ["1sg", "2sg", "1pl", "2pl"].contains(p)) || (plain_transitive && subject_before(i)))
                && !copula
                && !negated
                && !verbs.iter().any(|a| g.tag(a).ends_with(".refl"))
            {
                let mut k = i; // dar, jau and adverbs may stand between: mačiau labai gražų namą
                while k + 1 < toks.len() && adjacent[k + 1] && (OBJECT_SKIP.contains(&toks[k + 1].lower.as_str()) || between(k + 1)) {
                    k += 1;
                }
                let mut span = phrase(k, transitive);
                if span.iter().any(|&x| g.analyses(&toks[x].text).iter().any(|a| g.tag(a) == "V.inf"))
                    || (span.len() == 1 && g.analyses(&toks[span[0]].text).iter().any(|a| matches!(g.tag(a), "W" | "Adv")))
                {
                    span.clear(); // turėtų būti suprantama, sutiko baigti; atsirado kartu (together)
                }
                let allowed: &[&str] = if transitive { &["nom", "voc", "ins"] } else { &["nom", "voc"] };
                // the whole phrase instrumental (radau nukritusia sagute), not tapusią vienuole; or
                // only the modifiers, once the noun is fixed (radau nukritusia sagutę)
                let ins_phrase = transitive && span.iter().all(|&x| toks[x].own.iter().any(|r| r.case == "ins"));
                let head_acc = transitive && !span.is_empty() && toks[*span.last().unwrap()].own.iter().any(|r| r.case == "acc");
                if !span.is_empty()
                    && toks[*span.last().unwrap()].is_noun(&g)
                    && !CLAUSE_WORDS.contains(&toks[span[0]].lower.as_str())
                {
                    for &x in &span {
                        let t = &toks[x];
                        let mut fix: Vec<String> = Vec::new();
                        if !t.own.is_empty()
                            && t.own.iter().all(|r| allowed.contains(&r.case))
                            && t.own.iter().any(|r| r.case == "nom" || r.case == "voc")
                        {
                            fix = g.reinflect(t, |tg| tg.ends_with(".nom"), Some("acc"));
                        }
                        if fix.is_empty()
                            && (ins_phrase || (head_acc && x != *span.last().unwrap()))
                            && t.own.iter().all(|r| r.case == "ins" || r.case == "voc")
                        {
                            // radau nukritusia sagute -> nukritusią sagutę (the accusative lost its diacritic);
                            // same part of speech, number and gender (tuo metu is not metų)
                            let own: Vec<&Reading> = t.own.iter().filter(|r| r.case == "ins").collect();
                            fix = t.variants(&g).iter()
                                .filter(|(_, rs)| rs.iter().any(|r| r.case == "acc" && own.iter().any(|o| {
                                    r.pos == o.pos && r.number == o.number && r.gender == o.gender
                                })))
                                .map(|(f, _)| t.cap(f)).collect();
                        }
                        if !fix.is_empty() {
                            add(&mut issues, Issue {
                                start: t.start, end: t.end, word: t.text.clone(), rule: "object",
                                message: format!("the object of '{}' takes the accusative", w.text),
                                suggestions: fix,
                            });
                        }
                    }
                }
            }
        }

        // subject pronoun + verb: aš buvo -> buvau
        for i in 0..toks.len().saturating_sub(1) {
            let pron = &toks[i];
            let Some(want) = subject_person(&pron.lower) else { continue };
            if !adjacent[i + 1] || (i > 0 && ["ir", "bei", "arba", "ar", "nei"].contains(&toks[i - 1].lower.as_str())) {
                continue; // aš ir jis buvome: a coordinated subject
            }
            // adverbs and particles may stand between: aš vakar buvo -> buvau
            let mut k = i + 1;
            while k + 1 < toks.len() && k <= i + 2 && adjacent[k + 1] && g.adverb(&toks[k].text) && {
                let l = toks[k].lower.as_str();
                !SUBJECT_NO_SKIP.contains(&l) && subject_person(l).is_none() && !NO_COMMA_AFTER.contains(&l)
                    && !CLAUSE_STARTERS.contains(&l) && !KURIS.contains(&l) && prep_cases(l).is_none()
                    && !INTERROGATIVES.contains(&l)
            } {
                k += 1;
            }
            let v = &toks[k];
            if issues.contains_key(&v.start) {
                continue;
            }
            if !v.known {
                // an unknown word: candidates that are verbs of that person first
                // (jis ziuri -> žiūri "looks", not žiuri "jury")
                let fix: Vec<String> = v.variants(&g).iter()
                    .filter(|(f, _)| g.analyses(f).iter().any(|a| g.finite(a) && g.parts(a)[2] == want))
                    .map(|(f, _)| v.cap(f)).collect();
                if !fix.is_empty() {
                    add(&mut issues, Issue {
                        start: v.start, end: v.end, word: v.text.clone(), rule: "context",
                        message: format!("'{}' needs the {} form of the verb", pron.text, person_name(want)),
                        suggestions: fix,
                    });
                }
                continue;
            }
            let fin: Vec<Analysis> = g.analyses(&v.text).into_iter().filter(|a| g.finite(a)).collect();
            if fin.is_empty() || fin.iter().any(|a| g.parts(a)[2] == want) {
                continue;
            }
            let mut fix: Vec<String> = Vec::new();
            for a in &fin {
                for f in g.inflect(a, &retag(g.tag(a), None, Some(want))) {
                    let f = v.cap(&f);
                    if !fix.contains(&f) {
                        fix.push(f);
                    }
                }
            }
            if !fix.is_empty() {
                add(&mut issues, Issue {
                    start: v.start, end: v.end, word: v.text.clone(), rule: "subject",
                    message: format!("'{}' needs the {} form of the verb", pron.text, person_name(want)),
                    suggestions: fix,
                });
            }
        }

        // predicate adjective: ji nedidele -> nedidelė, mergaitė buvo nedidele -> nedidelė
        let is_copula = |t: &Word| {
            COPULA_FORMS.contains(&t.lower.as_str())
                || g.analyses(&t.text).iter().any(|a| g.tag(a).starts_with("V.") && NOMINATIVE_COPULAS.contains(&a.lemma.as_str()))
        };
        let fits = |r: &Reading, feats: &[(Option<&str>, Option<&str>)]| {
            r.pos == Pos::Adj && r.case == "nom"
                && feats.iter().any(|(num, gen)| (r.number.is_none() || r.number == *num) && (r.gender.is_none() || r.gender == *gen))
        };
        for i in 0..toks.len().saturating_sub(1) {
            let sub = &toks[i];
            if !adjacent[i + 1] || (i > 0 && adjacent[i] && COORDINATORS.contains(&toks[i - 1].lower.as_str())) {
                continue;
            }
            let feats: Vec<(Option<&str>, Option<&str>)> = if let Some((num, gen)) = pronoun_features(&sub.lower) {
                vec![(Some(num), Some(gen))]
            } else if sub.known && sub.is_noun(&g) && (!first_upper(&sub.text) || starts_sentence(i)) {
                let nouns: Vec<Analysis> = g.analyses(&sub.text).into_iter().filter(|a| g.tag(a).starts_with("N.")).collect();
                let top = nouns.iter().map(|a| g.lemma_freq(a)).max().unwrap_or(0);
                let top_nouns: Vec<Analysis> = nouns.into_iter().filter(|a| g.lemma_freq(a) == top).collect();
                let best = g.readings(&top_nouns);
                if best.is_empty() || !best.iter().all(|r| ["nom", "voc", "ins"].contains(&r.case)) || !best.iter().any(|r| r.case == "nom") {
                    continue;
                }
                let mut f: Vec<(Option<&str>, Option<&str>)> = Vec::new();
                for r in best.iter().filter(|r| r.case == "nom") {
                    if !f.contains(&(r.number, r.gender)) {
                        f.push((r.number, r.gender));
                    }
                }
                f
            } else {
                continue;
            };
            let mut k = i + 1;
            while k + 1 < toks.len() && k <= i + 3 && adjacent[k + 1] && between(k) && !is_copula(&toks[k]) {
                k += 1;
            }
            if is_copula(&toks[k]) {
                k += 1;
                while k + 1 < toks.len() && k <= i + 5 && adjacent[k] && adjacent[k + 1] && between(k) {
                    k += 1;
                }
            } else if !["jis", "ji", "jie"].contains(&sub.lower.as_str()) {
                continue; // a noun needs the copula: jos (her) gražios suknelės
            }
            if k >= toks.len() || !adjacent[k] || k <= i {
                continue;
            }
            let a = &toks[k];
            let end = k + 1 == toks.len() || !adjacent[k + 1] || phrase_stop(&toks[k + 1].lower);
            if !end || !a.is_adj(&g) || a.is_participle(&g) || issues.contains_key(&a.start) {
                continue;
            }
            if a.known && a.own.iter().any(|r| fits(r, &feats)) {
                continue;
            }
            let fix: Vec<String> = a.variants(&g).iter()
                .filter(|(_, rs)| rs.iter().any(|r| fits(r, &feats)))
                .map(|(f, _)| a.cap(f)).collect();
            if a.known && a.own.is_empty() {
                continue;
            }
            if !fix.is_empty() {
                add(&mut issues, Issue {
                    start: a.start, end: a.end, word: a.text.clone(), rule: if a.known { "agreement" } else { "context" },
                    message: format!("'{} … {}': the predicate adjective agrees with the subject", sub.text, a.text),
                    suggestions: fix,
                });
            }
        }

        // 2. adjective-noun agreement
        for i in 1..toks.len() {
            let a = &toks[i - 1];
            let mut n = &toks[i];
            if !adjacent[i] || issues.contains_key(&a.start) {
                continue;
            }
            if !(a.is_adj(&g) && n.is_noun(&g)) || a.can_be_verb(&g) || !(a.known || n.known) {
                continue;
            }
            // viena kitą = each other (but: vienos eilutes -> eilutės)
            if ["vienas", "viena", "vieni", "vienos"].contains(&a.lower.as_str()) && n.lower.starts_with("kit") {
                continue;
            }
            let mut no_gen = false;
            if n.can_be(&g, "gen") && !a.can_be(&g, "gen") {
                let mut j = i;
                while j + 1 < toks.len() && adjacent[j + 1] && toks[j].known && toks[j].can_be(&g, "gen") && toks[j + 1].is_noun(&g) {
                    j += 1;
                }
                if j > i && !toks[j].can_be(&g, "gen") && toks[j].known {
                    n = &toks[j];
                } else if j > i || !n.own.iter().any(|r| r.pos == Pos::Noun && r.case != "gen") {
                    continue;
                } else {
                    no_gen = true; // no head follows: not a modifier (šita žmogų -> šitą)
                }
            }
            // participle as attribute (nukritusią sagutę), not with an object, place or predicate
            if a.is_participle(&g)
                && (n.can_be(&g, "acc")
                    || n.can_be(&g, "loc")
                    || g.analyses(&a.text).iter().any(|x| PREDICATIVE_VERBS.iter().any(|v| x.lemma.ends_with(v))))
            {
                continue;
            }
            if issues.contains_key(&n.start) {
                continue;
            }
            let ar: Vec<Reading> = a.pos_readings(&g).into_iter().filter(|r| r.pos == Pos::Adj).collect();
            let nr: Vec<Reading> =
                n.pos_readings(&g).into_iter().filter(|r| r.pos == Pos::Noun && !(no_gen && r.case == "gen")).collect();
            if a.known && n.known && ar.iter().any(|x| nr.iter().any(|y| agree(x, y))) {
                continue;
            }
            let mut fix_n: Vec<String> = n.variants(&g).iter()
                .filter(|(_, rs)| ar.iter().any(|x| rs.iter().any(|y| y.pos == Pos::Noun && agree(x, y))))
                .map(|(f, _)| n.cap(f)).collect();
            let mut fix_a: Vec<String> = a.variants(&g).iter()
                .filter(|(_, rs)| rs.iter().any(|x| x.pos == Pos::Adj && nr.iter().any(|y| agree(x, y))))
                .map(|(f, _)| a.cap(f)).collect();
            let msg = format!("'{} {}': adjective and noun must agree in case and number", a.text, n.text);
            if !n.known {
                fix_a.clear();
            }
            if !a.known {
                fix_n.clear();
            }
            // a preposition before decides the case: pro nedideles gyvenvietės -> gyvenvietes
            let prep = if i >= 2 && adjacent[i - 1] { prep_cases(&toks[i - 2].lower) } else { None };
            if let Some(cases) = prep {
                if !fix_n.is_empty() && !fix_a.is_empty() {
                    if !ar.iter().any(|r| cases.contains(&r.case)) {
                        fix_n.clear();
                    } else if !nr.iter().any(|r| cases.contains(&r.case)) {
                        fix_a.clear();
                    }
                }
            }
            // otherwise change the word typed without diacritics: nedidele mergaitė -> nedidelė (not mergaite)
            if !fix_a.is_empty() && !has_diacritics(&a.text) && has_diacritics(&n.text) && prep.is_none() {
                fix_n.clear();
            }
            if !fix_n.is_empty() {
                let rule = if n.known { "agreement" } else { "context" };
                add(&mut issues, Issue { start: n.start, end: n.end, word: n.text.clone(), rule, message: msg, suggestions: fix_n });
            } else if !fix_a.is_empty() {
                let rule = if a.known { "agreement" } else { "context" };
                add(&mut issues, Issue { start: a.start, end: a.end, word: a.text.clone(), rule, message: msg, suggestions: fix_a });
            }
        }

        // 9. a noun right before another noun is its genitive modifier: gyventoju skaičius ->
        //    gyventojų, vietoves gyventojai -> vietovės (the -ų/-ės lost their diacritics)
        for i in 0..toks.len().saturating_sub(1) {
            let w = &toks[i];
            if issues.contains_key(&w.start) || !adjacent[i + 1] || !w.known || (first_upper(&w.text) && !starts_sentence(i)) {
                continue;
            }
            let an_w = g.analyses(&w.text);
            let nouns: Vec<&Analysis> = an_w.iter().filter(|a| g.tag(a).starts_with("N.")).collect();
            if nouns.is_empty()
                || an_w.iter().any(|a| g.tag(a).ends_with(".gen") || matches!(g.tag(a), "W" | "Adv"))
                || (g.mostly_verb(&an_w) && an_w.iter().any(|a| g.finite(a)))
            {
                continue; // laiku (on time), metu (I throw) are not modifiers
            }
            let fix: Vec<String> = w.variants(&g).iter()
                .filter(|(f, _)| first_lower(f) && g.analyses(f).iter().any(|a| {
                    let t = g.tag(a);
                    t.starts_with("N.") && t.ends_with(".gen") && nouns.iter().any(|n| n.lemma == a.lemma)
                }))
                .map(|(f, _)| w.cap(f)).collect();
            if fix.is_empty() {
                continue;
            }
            let span = phrase(i, false);
            let Some(&h) = span.last() else { continue };
            let head = &toks[h];
            if !head.is_noun(&g) || !head.known || first_upper(&head.text)
                || g.analyses(&head.text).iter().any(|a| matches!(g.tag(a), "W" | "Adv"))
                || verb_at(i + span.len())
            {
                continue; // su broliu namo: namo is an adverb
            }
            if w.own.iter().any(|r| head.own.iter().any(|x| x.case == r.case))
                || (!head.own.is_empty() && head.own.iter().all(|r| r.case == "gen"))
            {
                continue; // one phrase: pilotu bandytoju, naktiniu gyvenimu; tarpininku liaudies švietime
            }
            if nouns.iter().all(|a| a.lemma == "metas") {
                continue; // vienu metu, tam tikru metu: "at a time"
            }
            // an adverbial instrumental seen as often as its genitive: Sovietmečiu, laikotarpiu, būdu
            let own_f = g.freq(&w.lower);
            let fix_f = fix.iter().map(|f| g.freq(f)).max().unwrap_or(0);
            if own_f > 0 && own_f * 3 >= fix_f {
                continue;
            }
            // modifiers before it must agree with the genitive too: branduoliniu ginklu -> branduolinių
            // ginklų; tuo metu žmonės stays (tuo has no genitive twin)
            let gen: Vec<Reading> = fix.iter().flat_map(|f| g.readings_of(&lower(f)))
                .filter(|r| r.pos == Pos::Noun && r.case == "gen").collect();
            let mut mods: Vec<(usize, Vec<String>)> = Vec::new();
            let mut k = i as isize - 1;
            let mut ok = true;
            while k >= 0 && adjacent[k as usize + 1] && toks[k as usize].is_adj(&g) {
                let m = &toks[k as usize];
                if !m.own.iter().any(|x| w.own.iter().any(|y| agree(x, y))) {
                    break;
                }
                let mf: Vec<String> = m.variants(&g).iter()
                    .filter(|(_, rs)| rs.iter().any(|x| x.pos == Pos::Adj && gen.iter().any(|y| agree(x, y))))
                    .map(|(f, _)| m.cap(f)).collect();
                if mf.is_empty() {
                    ok = false;
                    break;
                }
                mods.push((k as usize, mf));
                k -= 1;
            }
            if !ok {
                continue;
            }
            if k >= 0 && adjacent[k as usize + 1] {
                let p = &toks[k as usize];
                let an_p = g.analyses(&p.text);
                if prep_cases(&p.lower).is_some_and(|cs| w.own.iter().any(|r| cs.contains(&r.case))) {
                    continue; // su metaliniu lankeliu dugne
                }
                if an_p.iter().any(|a| g.tag(a).starts_with("V.")) && g.mostly_verb(&an_p) {
                    continue; // pirkęs žemes kaimuose, tapo kasdieniniu gėrimu: governed by the verb
                }
                let pr = p.pos_readings(&g); // an unknown word (typed without diacritics): its candidates
                if POSSESSIVES.contains(&p.lower.as_str()) || (!an_p.is_empty() && an_p.iter().all(|a| g.tag(a) == "W")) {
                    continue; // jos pasirodymu danguje, šiuo metu
                }
                // after a genitive (or a name) an instrumental is often its head: karo metu,
                // Vyriausybės potvarkiu, Aifelio dialektu; only a genitive the corpus knows well
                // wins there (vidaus reikalų, Čikagos lietuvių)
                if w.own.iter().any(|r| r.case == "ins")
                    && (pr.iter().any(|r| r.pos == Pos::Noun && r.case == "gen") || pr.is_empty())
                    && fix_f < 5
                {
                    continue;
                }
            }
            // a governor further left, across genitives: į Kalavijuočių ordino žemes,
            // tapo antruoju pagal dydį miestu
            let mut j = k;
            let mut governed = false;
            while j >= 0 && j >= k - 3 && adjacent[j as usize + 1] && !governed {
                let t = &toks[j as usize];
                governed = if let Some(cs) = prep_cases(&t.lower) {
                    w.own.iter().any(|r| cs.contains(&r.case))
                } else {
                    w.own.iter().any(|r| r.case == "ins")
                        && g.analyses(&t.text).iter().any(|a| g.tag(a).starts_with("V.") && PREDICATIVE_VERBS.iter().any(|v| a.lemma.ends_with(v)))
                };
                j -= 1;
            }
            if governed {
                continue;
            }
            let why = format!("'{} {}': a noun before another noun is usually its genitive", w.text, head.text);
            for (m, mf) in mods {
                let t = &toks[m];
                add(&mut issues, Issue { start: t.start, end: t.end, word: t.text.clone(), rule: "case", message: why.clone(), suggestions: mf });
            }
            add(&mut issues, Issue { start: w.start, end: w.end, word: w.text.clone(), rule: "case", message: why, suggestions: fix });
        }

        issues.into_values().collect()
    }
}
