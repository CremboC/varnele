//! WebAssembly bridge for the browser extension. The caller writes UTF-8 into memory it got from
//! `alloc`, calls `check` or `language`, and reads `result_len` bytes of JSON from the pointer it returns.
//! The compiled data file is embedded, so the extension ships one .wasm.

use std::sync::{Mutex, OnceLock};

use varnele::{Checker, Tally};

static DATA: &[u8] = include_bytes!("../../../data/varnele.bin");
static CHECKER: OnceLock<Mutex<Checker>> = OnceLock::new();
static RESULT: Mutex<String> = Mutex::new(String::new());

fn checker() -> &'static Mutex<Checker> {
    CHECKER.get_or_init(|| Mutex::new(Checker::from_bytes(DATA).expect("embedded data file is valid")))
}

#[no_mangle]
pub extern "C" fn alloc(len: usize) -> *mut u8 {
    let mut v = Vec::<u8>::with_capacity(len);
    let p = v.as_mut_ptr();
    std::mem::forget(v);
    p
}

/// Load the data so the first check is fast.
#[no_mangle]
pub extern "C" fn warm_up() {
    let ck = checker().lock().unwrap();
    let _ = ck.check_text("Labas rytas, sviesa.", false, true);
    let _ = ck.an.key_shift("ksbsd", 1); // also builds the key-shift prefix table
}

/// Check a text (takes over the buffer from `alloc`). Returns {"findings": [...], "tally": [words,
/// foreign, marked]}, with UTF-16 offsets, the units of JavaScript strings.
///
/// # Safety
/// `ptr` and `len` must come from `alloc(len)`, with `len` bytes of valid UTF-8 written.
#[no_mangle]
pub unsafe extern "C" fn check(ptr: *mut u8, len: usize, formal: bool) -> *const u8 {
    let text = String::from_utf8_unchecked(Vec::from_raw_parts(ptr, len, len));
    // character offset -> UTF-16 offset (emoji and other astral characters take two units)
    let mut utf16 = Vec::with_capacity(text.len() + 1);
    let mut n = 0;
    for c in text.chars() {
        utf16.push(n);
        n += c.len_utf16();
    }
    utf16.push(n);
    let fs = checker().lock().unwrap().check_text(&text, formal, true);
    let mut result = RESULT.lock().unwrap();
    let t = Tally::of(&text, &fs);
    *result = format!("{{\"findings\":{},\"tally\":[{},{},{}]}}", varnele::json::findings(&fs, |i| utf16[i]), t.words, t.foreign, t.marked as u8);
    result.as_ptr()
}

/// Is the text with this tally Lithuanian? 1 yes, 0 no, -1 too little to tell.
#[no_mangle]
pub extern "C" fn language(words: usize, foreign: usize, marked: bool) -> i32 {
    Tally { words, foreign, marked }.is_lithuanian().map_or(-1, i32::from)
}

#[no_mangle]
pub extern "C" fn result_len() -> usize {
    RESULT.lock().unwrap().len()
}
