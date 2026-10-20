//! Minimal JSON output for findings (no dependencies).

use crate::checker::Finding;

pub fn string(s: &str) -> String {
    let mut o = String::with_capacity(s.len() + 2);
    o.push('"');
    for c in s.chars() {
        match c {
            '"' => o.push_str("\\\""),
            '\\' => o.push_str("\\\\"),
            '\n' => o.push_str("\\n"),
            c if (c as u32) < 0x20 => o.push_str(&format!("\\u{:04x}", c as u32)),
            c => o.push(c),
        }
    }
    o.push('"');
    o
}

/// One finding as a JSON object. `offset` maps character offsets to the
/// caller's units (identity, or UTF-16 for Java).
pub fn finding(f: &Finding, offset: impl Fn(usize) -> usize) -> String {
    let s: Vec<String> = f.suggestions.iter().map(|x| string(x)).collect();
    format!(
        "{{\"start\":{},\"end\":{},\"word\":{},\"rule\":{},\"message\":{},\"suggestions\":[{}]}}",
        offset(f.start),
        offset(f.end),
        string(&f.word),
        string(f.rule),
        string(&f.message),
        s.join(",")
    )
}

pub fn findings(fs: &[Finding], offset: impl Fn(usize) -> usize + Copy) -> String {
    let items: Vec<String> = fs.iter().map(|f| finding(f, offset)).collect();
    format!("[{}]", items.join(","))
}
