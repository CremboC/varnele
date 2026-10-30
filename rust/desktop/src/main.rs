//! Varnelė for the desktop: autocorrect in every text field. `--sim TEXT...` types text through the
//! engine and prints what the field would hold, without touching the system. `--selftest OUT`
//! (macOS) types into a window of its own, through the real event path, and writes what it got.

mod engine;
#[cfg(target_os = "macos")]
mod mac;
#[cfg(target_os = "macos")]
mod mac_selftest;

use std::sync::{Mutex, OnceLock};

use varnele::Checker;

static DATA: &[u8] = include_bytes!("../../../data/varnele.bin");
static CHECKER: OnceLock<Mutex<Checker>> = OnceLock::new();

fn checker() -> &'static Mutex<Checker> {
    CHECKER.get_or_init(|| Mutex::new(Checker::from_bytes(DATA).expect("embedded data file is valid")))
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.first().is_some_and(|a| a == "--sim") {
        let ck = checker().lock().unwrap();
        let given: Vec<String> = args[1..].iter().filter(|a| !a.starts_with("--")).cloned().collect();
        let lines: Vec<String> = if given.is_empty() { std::io::stdin().lines().map_while(Result::ok).collect() } else { given };
        for line in lines {
            let mut e = engine::Engine::new();
            #[cfg(target_os = "macos")]
            if !args.iter().any(|a| a == "--no-english") {
                e.english = Some(mac::english());
            }
            println!("{}", engine::simulate(&mut e, &ck, &format!("{line} ")));
        }
        return;
    }
    #[cfg(target_os = "macos")]
    mac::run(args.iter().position(|a| a == "--selftest").and_then(|i| args.get(i + 1).cloned()));
    #[cfg(not(target_os = "macos"))]
    eprintln!("this platform has no key listener yet; --sim works");
}
