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
        | "vidur" => &["gen"],
        "už" => &["acc", "gen"],
        "su" | "sulig" => &["ins"],
        "ties" => &["gen", "ins"],
        _ => return None,
    })
}
const PREP_LIST: &[&str] = &[
    "į", "per", "pro", "prieš", "apie", "pagal", "palei", "pas", "aplink", "iš", "be", "nuo",
    "prie", "iki", "ligi", "dėl", "ant", "virš", "tarp", "anot", "pasak", "šalia", "vietoj",
    "netoli", "anapus", "šiapus", "abipus", "vidury", "vidur", "už", "su", "sulig", "ties",
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
        let mut out = Vec::new();
        for a in self.an.analyze(w) {
            let parts = self.parts(&a);
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
        self.c.readings.borrow_mut().insert(w.to_string(), out.clone());
        out
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
                    || (lw == "nors" && (INTERROGATIVES.contains(&prev) || KURIS.contains(&prev) || nxt == "ir"))
                    || (is_kuris && (prev == "bet" || prev == "kai" || ["nors", "laikui", "laiką", "laiko"].contains(&nxt)));
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
            if cands.is_empty() {
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
        let gap_of = |i: usize| -> String { if i == 0 { String::new() } else { chars[toks[i - 1].end..toks[i].start].iter().collect() } };
        let starts_sentence = |i: usize| i == 0 || gap_of(i).chars().any(|c| SENTENCE_GAP.contains(c));
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
        let verb_at = |k: usize| {
            let an_k = g.analyses(&toks[k].text);
            an_k.iter().any(|a| g.finite(a)) && g.mostly_verb(&an_k)
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
                if !span.is_empty() && toks[*span.last().unwrap()].is_noun(&g) && !timey {
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

            let persons: Vec<&str> = verbs.iter().filter(|a| g.finite(a)).map(|a| g.parts(a)[2].as_str()).collect();
            if !persons.is_empty()
                && persons.iter().all(|p| ["1sg", "2sg", "1pl", "2pl"].contains(p))
                && !copula
                && !negated
                && !verbs.iter().any(|a| g.tag(a).ends_with(".refl"))
            {
                let mut k = i;
                while k + 1 < toks.len() && adjacent[k + 1] && OBJECT_SKIP.contains(&toks[k + 1].lower.as_str()) {
                    k += 1;
                }
                let transitive = verbs.iter().any(|a| TRANSITIVE_VERBS.iter().any(|v| a.lemma.ends_with(v)));
                let span = phrase(k, transitive);
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
            if ["vienas", "viena", "vieni", "vienos"].contains(&a.lower.as_str()) {
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
            if !fix_n.is_empty() {
                let rule = if n.known { "agreement" } else { "context" };
                add(&mut issues, Issue { start: n.start, end: n.end, word: n.text.clone(), rule, message: msg, suggestions: fix_n });
            } else if !fix_a.is_empty() {
                let rule = if a.known { "agreement" } else { "context" };
                add(&mut issues, Issue { start: a.start, end: a.end, word: a.text.clone(), rule, message: msg, suggestions: fix_a });
            }
        }

        issues.into_values().collect()
    }
}
