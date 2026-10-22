//! varnele [--data PATH] check FILE [--formal] [--no-grammar] | json FILE | words W... | kb WORD [CONTEXT...]
//!         | swipe WORD... | serve | bench | fst (stdin KEY<TAB>VALUE lines -> FST bytes, for the export)

use std::io::Read;
use std::time::Instant;

use varnele::gesture::{key_word, Layout};
use varnele::Checker;

/// "x,y x,y ..." in key widths
fn parse_path(s: &str) -> Vec<(f32, f32)> {
    s.split_whitespace()
        .filter_map(|p| p.split_once(',').and_then(|(x, y)| Some((x.parse().ok()?, y.parse().ok()?))))
        .collect()
}

/// The ideal path of a word: straight lines through its key centres (repeated keys once).
fn ideal_path(word: &str, layout: &Layout) -> Vec<(f32, f32)> {
    let mut out: Vec<(f32, f32)> = Vec::new();
    for c in key_word(word).chars() {
        if let Some(p) = layout.centre(c) {
            if out.last() != Some(&p) {
                out.push(p);
            }
        }
    }
    out
}

fn read_input(path: &str) -> String {
    if path == "-" {
        let mut s = String::new();
        std::io::stdin().read_to_string(&mut s).unwrap();
        s
    } else {
        std::fs::read_to_string(path).unwrap_or_else(|e| panic!("{path}: {e}"))
    }
}

fn main() {
    let mut args: Vec<String> = std::env::args().skip(1).collect();
    if args.first().map(String::as_str) == Some("fst") {
        // build a count table for `python3 -m varnele export` (needs no data file)
        use std::io::Write;
        let mut input = String::new();
        std::io::stdin().read_to_string(&mut input).unwrap();
        let pairs = input
            .lines()
            .filter_map(|l| l.rsplit_once('\t').and_then(|(k, v)| Some((k.to_string(), v.parse().ok()?))))
            .collect();
        std::io::stdout().write_all(&varnele::counts::build(pairs)).unwrap();
        return;
    }
    let mut data_path = "data/varnele.bin".to_string();
    if let Some(i) = args.iter().position(|a| a == "--data") {
        data_path = args[i + 1].clone();
        args.drain(i..i + 2);
    }
    let t = Instant::now();
    let bytes = std::fs::read(&data_path).unwrap_or_else(|e| panic!("{data_path}: {e}"));
    let ck = Checker::from_bytes(&bytes).unwrap();
    let load = t.elapsed();
    let formal = args.iter().any(|a| a == "--formal");
    let grammar = !args.iter().any(|a| a == "--no-grammar");
    match args.first().map(String::as_str) {
        Some("words") => {
            for w in &args[1..] {
                let (st, sugg) = ck.check_word(w);
                println!("{w}: {st:?}{}", if sugg.is_empty() { String::new() } else { format!(" -> {}", sugg.join(", ")) });
                for a in ck.an.analyze(w).iter().take(8) {
                    let pre = if a.prefix.is_empty() { String::new() } else { format!("{}+", a.prefix) };
                    println!("    {pre}{}  {}", a.lemma, ck.an.tag_str(a));
                }
            }
        }
        Some("check") => {
            let text = read_input(&args[1]);
            for f in ck.check_text(&text, formal, grammar) {
                let line = text.chars().take(f.start).filter(|&c| c == '\n').count() + 1;
                let sugg = if f.suggestions.is_empty() { String::new() } else { format!(" -> {}", f.suggestions.join(", ")) };
                let msg = if f.message.is_empty() { String::new() } else { format!("   ({})", f.message) };
                println!("{line}:{} {}{sugg}{msg}", f.rule, f.word);
            }
        }
        Some("json") => {
            // one finding per line, for comparing with the Python implementation
            let text = read_input(&args[1]);
            let t = Instant::now();
            let fs = ck.check_text(&text, formal, grammar);
            for f in &fs {
                println!("{}", varnele::json::finding(f, |i| i));
            }
            eprintln!("load {:?}, check {:?}", load, t.elapsed());
        }
        Some("kb") => {
            // keyboard view of a word: varnele kb WORD [CONTEXT...]
            let ctx = args[2..].iter().filter(|a| !a.starts_with("--")).cloned().collect::<Vec<_>>().join(" ");
            println!("{}", varnele::json::keyboard_word(&ck.keyboard_word(&args[1], &ctx, !args.iter().any(|a| a == "--no-key-shift"))));
        }
        Some("swipe") => {
            // decode each word's ideal path: varnele swipe WORD...
            let layout = Layout::qwerty();
            for w in &args[1..] {
                let t = Instant::now();
                let cands = ck.an.gesture(&ideal_path(w, &layout), &layout, false, "", 5);
                let list: Vec<String> = cands.iter().map(|c| format!("{} ({}, {:.2}, {:.3})", c.word, c.best, c.cost, c.shape)).collect();
                println!("{w}: {}   {:?}", list.join(", "), t.elapsed());
            }
        }
        Some("serve") => {
            // one request per stdin line, for evaluations that make thousands of calls:
            //   kb<TAB>WORD<TAB>CONTEXT  -> one JSON line
            //   json<TAB>TEXT            -> one finding per line, then an empty line
            //   gesture<TAB>X,Y X,Y ...<TAB>CAP(0/1)<TAB>N<TAB>CONTEXT  -> JSON list of N candidates (QWERTY, key widths)
            //   predict<TAB>CONTEXT<TAB>PREFIX<TAB>N  -> JSON list of N next words
            let layout = Layout::qwerty();
            use std::io::{BufRead, Write};
            let mut out = std::io::stdout().lock();
            for line in std::io::stdin().lock().lines() {
                let line = line.unwrap();
                let parts: Vec<&str> = line.split('\t').collect();
                match parts[0] {
                    "kb" => writeln!(out, "{}", varnele::json::keyboard_word(
                        &ck.keyboard_word(parts[1], parts.get(2).copied().unwrap_or(""), true))).unwrap(),
                    "json" => {
                        for f in ck.check_text(parts.get(1).copied().unwrap_or(""), formal, grammar) {
                            writeln!(out, "{}", varnele::json::finding(&f, |i| i)).unwrap();
                        }
                        writeln!(out).unwrap();
                    }
                    "gesture" => {
                        let path = parse_path(parts.get(1).copied().unwrap_or(""));
                        let cap = parts.get(2) == Some(&"1");
                        let n = parts.get(3).and_then(|n| n.parse().ok()).unwrap_or(5);
                        let context = parts.get(4).copied().unwrap_or("");
                        writeln!(out, "{}", varnele::json::gesture(&ck.an.gesture(&path, &layout, cap, context, n))).unwrap();
                    }
                    "predict" => {
                        let context = parts.get(1).copied().unwrap_or("");
                        let n = parts.get(3).and_then(|n| n.parse().ok()).unwrap_or(3);
                        let ctx = ck.an.lm_context(context);
                        let words = ck.an.predict_words(&ctx, context, parts.get(2).copied().unwrap_or(""), n);
                        let items: Vec<String> = words.iter().map(|(w, p)| format!("{{\"w\":{},\"p\":{p:.6}}}", varnele::json::string(w))).collect();
                        writeln!(out, "[{}]", items.join(",")).unwrap();
                    }
                    _ => writeln!(out, "{{\"error\":\"unknown request\"}}").unwrap(),
                }
                out.flush().unwrap();
            }
        }
        Some("bench") => {
            // per-call latency: correct words, misspellings (with suggestions), sentences
            let time = |label: &str, items: &[&str], f: &dyn Fn(&str)| {
                let mut ts: Vec<f64> = Vec::new();
                for round in 0..3 {
                    for it in items {
                        let t = Instant::now();
                        f(it);
                        if round > 0 { ts.push(t.elapsed().as_secs_f64() * 1000.0); }
                    }
                }
                ts.sort_by(|a, b| a.partial_cmp(b).unwrap());
                println!("{label:28} median {:7.3} ms   max {:7.3} ms", ts[ts.len() / 2], ts[ts.len() - 1]);
            };
            let t = Instant::now();
            let _ = ck.check_word("sviesa");
            println!("first suggestion (builds lookup tables): {:?}", t.elapsed());
            time("correct word", &["šviesa", "namas", "mačiau", "nusiprausė", "Vilniaus", "kavinę"], &|w| { ck.check_word(w); });
            time("misspelled + suggestions", &["maciau", "pakeiciau", "dziaugias", "isvaziavo", "temperaturos", "pulininkai", "virma", "atuželti"], &|w| { ck.check_word(w); });
            let _ = ck.an.key_shift("fofrkua", 3);
            time("key-shift search (7 letters)", &["fofrkua", "fifekua", "nakas", "ksbsd"], &|w| { ck.an.key_shift(w, 3); });
            let layout = Layout::qwerty();
            let paths: Vec<Vec<(f32, f32)>> = ["labas", "nežinau", "mačiau", "kodėl", "dienų", "pasakojimas"]
                .iter().map(|w| ideal_path(w, &layout)).collect();
            let _ = ck.an.gesture(&paths[0], &layout, false, "", 5);
            let mut ts: Vec<f64> = Vec::new();
            for _ in 0..3 {
                for p in &paths {
                    let t = Instant::now();
                    ck.an.gesture(p, &layout, false, "", 5);
                    ts.push(t.elapsed().as_secs_f64() * 1000.0);
                }
            }
            ts.sort_by(|a, b| a.partial_cmp(b).unwrap());
            println!("{:28} median {:7.3} ms   max {:7.3} ms", "gesture (ideal paths)", ts[ts.len() / 2], ts[ts.len() - 1]);
            time("sentence (12 words)", &["Vakar maciau, kad pries pora dienu jis nuėjo į didele kavine su draugais."], &|s| { ck.check_text(s, false, true); });
        }
        _ => eprintln!("usage: varnele [--data PATH] check FILE [--formal] [--no-grammar] | json FILE | words W..."),
    }
}
