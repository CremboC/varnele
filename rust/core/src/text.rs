//! Character-level helpers. All positions in this crate are counted in
//! characters (Unicode scalar values), which for Lithuanian text equal the
//! UTF-16 offsets Android uses.

pub const LT_ALPHABET: &str = "aąbcčdeęėfghiįyjklmnoprsštuųūvzž";
/// sorted(set(fold(LT_ALPHABET))) in the Python version
pub const FOLDED_ALPHABET: [char; 22] = [
    'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'r', 's', 't',
    'u', 'v', 'z',
];

/// Letters that differ only by diacritics / length / nasality share a folded form.
#[inline]
pub fn fold_char(c: char) -> char {
    match c {
        'ą' => 'a',
        'č' => 'c',
        'ę' | 'ė' => 'e',
        'į' | 'y' => 'i',
        'š' => 's',
        'ų' | 'ū' => 'u',
        'ž' => 'z',
        _ => c,
    }
}

pub fn fold(s: &str) -> String {
    s.chars().map(fold_char).collect()
}

pub fn lower(s: &str) -> String {
    s.to_lowercase()
}

pub fn clen(s: &str) -> usize {
    s.chars().count()
}

/// Byte offset of the n-th character (or the string length).
pub fn cidx(s: &str, n: usize) -> usize {
    s.char_indices().nth(n).map(|(i, _)| i).unwrap_or(s.len())
}

/// Python's s[:n] / s[n:] on characters.
pub fn chead(s: &str, n: usize) -> &str {
    &s[..cidx(s, n)]
}
pub fn ctail(s: &str, n: usize) -> &str {
    &s[cidx(s, n)..]
}

/// Python str.isupper(): has a cased character and no lowercase ones.
pub fn is_upper(s: &str) -> bool {
    s.chars().any(|c| c.is_uppercase()) && !s.chars().any(|c| c.is_lowercase())
}

pub fn first_upper(s: &str) -> bool {
    s.chars().next().map_or(false, |c| c.is_uppercase())
}

pub fn first_lower(s: &str) -> bool {
    s.chars().next().map_or(false, |c| c.is_lowercase())
}

/// Python str.capitalize()
pub fn capitalize(s: &str) -> String {
    let mut it = s.chars();
    match it.next() {
        Some(c) => c.to_uppercase().chain(it.flat_map(|c| c.to_lowercase())).collect(),
        None => String::new(),
    }
}

pub fn upper_first(s: &str) -> String {
    let mut it = s.chars();
    match it.next() {
        Some(c) => c.to_uppercase().chain(it).collect(),
        None => String::new(),
    }
}

pub fn lower_first(s: &str) -> String {
    let mut it = s.chars();
    match it.next() {
        Some(c) => c.to_lowercase().chain(it).collect(),
        None => String::new(),
    }
}

/// Give `form` a capital first letter if `like` has one.
pub fn cap_like(like: &str, form: &str) -> String {
    if first_upper(like) {
        upper_first(form)
    } else {
        form.to_string()
    }
}

pub fn is_foreign(word: &str) -> bool {
    lower(word).chars().any(|c| !LT_ALPHABET.contains(c))
}

/// Undo the č/dž softening to recover an underlying t/d stem.
pub fn underlying(stem: &str) -> String {
    if let Some(s) = stem.strip_suffix("dž") {
        format!("{s}d")
    } else if let Some(s) = stem.strip_suffix('č') {
        format!("{s}t")
    } else {
        stem.to_string()
    }
}

/// The letters a word token is made of (Python: [^\W\d_]).
#[inline]
pub fn is_word_char(c: char) -> bool {
    c.is_alphabetic()
}

/// Word tokens: letters, optionally joined by hyphens (Python WORD regex).
/// Returns (start, end) in characters.
pub fn word_spans(chars: &[char]) -> Vec<(usize, usize)> {
    let mut out = Vec::new();
    let mut i = 0;
    while i < chars.len() {
        if !is_word_char(chars[i]) {
            i += 1;
            continue;
        }
        let start = i;
        while i < chars.len() && is_word_char(chars[i]) {
            i += 1;
        }
        while i + 1 < chars.len()
            && (chars[i] == '-' || chars[i] == '‑')
            && is_word_char(chars[i + 1])
        {
            i += 1;
            while i < chars.len() && is_word_char(chars[i]) {
                i += 1;
            }
        }
        out.push((start, i));
    }
    out
}

pub fn substr(chars: &[char], a: usize, b: usize) -> String {
    chars[a..b].iter().collect()
}

/// One-edit neighbours (delete, replace, swap, insert), like the Python _edits1.
pub fn edits1(w: &str, alphabet: &[char]) -> Vec<String> {
    let cs: Vec<char> = w.chars().collect();
    let mut out = crate::fx::FxSet::default();
    for i in 0..=cs.len() {
        let (l, r) = cs.split_at(i);
        if !r.is_empty() {
            out.insert(l.iter().chain(&r[1..]).collect::<String>());
            for &c in alphabet {
                out.insert(l.iter().chain(std::iter::once(&c)).chain(&r[1..]).collect::<String>());
            }
        }
        if r.len() > 1 {
            out.insert(l.iter().chain([&r[1], &r[0]]).chain(&r[2..]).collect::<String>());
        }
        for &c in alphabet {
            out.insert(l.iter().chain(std::iter::once(&c)).chain(r).collect::<String>());
        }
    }
    out.remove(w);
    let mut v: Vec<String> = out.into_iter().collect();
    v.sort();
    v
}
