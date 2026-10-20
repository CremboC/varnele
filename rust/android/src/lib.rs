//! JNI bridge: dev.imbrasas.varnele.Native.{warmUp, check}
//! The compiled data file is embedded in the library, so the app ships one .so.

use std::sync::{Mutex, OnceLock};

use jni::objects::{JClass, JString};
use jni::sys::{jboolean, jstring};
use jni::JNIEnv;
use varnele::Checker;

static DATA: &[u8] = include_bytes!("../../../data/varnele.bin");
static CHECKER: OnceLock<Mutex<Checker>> = OnceLock::new();

fn checker() -> &'static Mutex<Checker> {
    CHECKER.get_or_init(|| Mutex::new(Checker::from_bytes(DATA).expect("embedded data file is valid")))
}

/// Load the data (takes a moment the first time) so the first check is fast.
#[no_mangle]
pub extern "system" fn Java_dev_imbrasas_varnele_Native_warmUp(_env: JNIEnv, _class: JClass) {
    let ck = checker().lock().unwrap();
    let _ = ck.check_text("Labas rytas, sviesa.", false, true); // also builds lazy indexes
}

/// Same as warmUp, for the HeliBoard bridge (which wraps it in a Kotlin warmUp()).
#[no_mangle]
pub extern "system" fn Java_dev_imbrasas_varnele_Native_warmUpNative(env: JNIEnv, class: JClass) {
    Java_dev_imbrasas_varnele_Native_warmUp(env, class)
}

/// Check a text. Returns a JSON array of findings with UTF-16 offsets.
#[no_mangle]
pub extern "system" fn Java_dev_imbrasas_varnele_Native_check<'l>(
    mut env: JNIEnv<'l>,
    _class: JClass<'l>,
    text: JString<'l>,
    formal: jboolean,
) -> jstring {
    let text: String = match env.get_string(&text) {
        Ok(s) => s.into(),
        Err(_) => String::new(),
    };
    // character offset -> UTF-16 offset (emoji and other astral characters take two units)
    let mut utf16 = Vec::with_capacity(text.len() + 1);
    let mut n = 0;
    for c in text.chars() {
        utf16.push(n);
        n += c.len_utf16();
    }
    utf16.push(n);
    let json = {
        let ck = checker().lock().unwrap();
        let fs = ck.check_text(&text, formal != 0, true);
        varnele::json::findings(&fs, |i| utf16[i])
    };
    env.new_string(json).map(|s| s.into_raw()).unwrap_or(std::ptr::null_mut())
}

/// The word being typed, for a keyboard: JSON {status, suggestions, contextRule, contextFixes}.
/// `context` is the text before the word (a few previous words), may be empty.
#[no_mangle]
pub extern "system" fn Java_dev_imbrasas_varnele_Native_word<'l>(
    mut env: JNIEnv<'l>,
    _class: JClass<'l>,
    word: JString<'l>,
    context: JString<'l>,
) -> jstring {
    let word: String = env.get_string(&word).map(Into::into).unwrap_or_default();
    let context: String = env.get_string(&context).map(Into::into).unwrap_or_default();
    let json = {
        let ck = checker().lock().unwrap();
        varnele::json::keyboard_word(&ck.keyboard_word(&word, &context))
    };
    env.new_string(json).map(|s| s.into_raw()).unwrap_or(std::ptr::null_mut())
}
