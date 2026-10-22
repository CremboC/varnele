//! JNI bridge: dev.imbrasas.varnele.Native.{warmUp, check, word, gestureNative}
//! The compiled data file is embedded in the library, so the app ships one .so.

use std::sync::{Mutex, OnceLock};

use jni::objects::{JClass, JFloatArray, JString};
use jni::sys::{jboolean, jint, jstring};
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
    let _ = ck.an.key_shift("ksbsd", 1); // and the key-shift prefix table
    let layout = varnele::gesture::Layout::qwerty();
    let path: Vec<(f32, f32)> = "labas".chars().filter_map(|c| layout.centre(c)).collect();
    let _ = ck.an.gesture(&path, &layout, false, "", 1, false); // and the gesture search's tables
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

/// The word being typed, for a keyboard: JSON {status, suggestions, contextRule, contextFixes, keyShift}.
/// `context` is the text before the word (a few previous words), may be empty; `formal`: spoken
/// forms get their standard form as a fix (contextRule "formal").
#[no_mangle]
pub extern "system" fn Java_dev_imbrasas_varnele_Native_word<'l>(
    mut env: JNIEnv<'l>,
    _class: JClass<'l>,
    word: JString<'l>,
    context: JString<'l>,
    key_shift: jboolean,
    formal: jboolean,
) -> jstring {
    let word: String = env.get_string(&word).map(Into::into).unwrap_or_default();
    let context: String = env.get_string(&context).map(Into::into).unwrap_or_default();
    let json = {
        let ck = checker().lock().unwrap();
        varnele::json::keyboard_word(&ck.keyboard_word(&word, &context, key_shift != 0, formal != 0))
    };
    env.new_string(json).map(|s| s.into_raw()).unwrap_or(std::ptr::null_mut())
}

fn floats(env: &mut JNIEnv, a: &JFloatArray) -> Vec<f32> {
    let n = env.get_array_length(a).unwrap_or(0) as usize;
    let mut v = vec![0f32; n];
    if env.get_float_array_region(a, 0, &mut v).is_err() {
        v.clear();
    }
    v
}

/// A swipe: the finger path and the letter keys' centres, all divided by the key width;
/// `keys` holds the letters in the order of `key_x`/`key_y`. Returns a JSON array of
/// candidates {w (the keys swiped, no diacritics), best (most likely real form), cost, shape};
/// `formal`: no spoken forms, their standard forms instead.
#[no_mangle]
#[allow(clippy::too_many_arguments)]
pub extern "system" fn Java_dev_imbrasas_varnele_Native_gestureNative<'l>(
    mut env: JNIEnv<'l>,
    _class: JClass<'l>,
    xs: JFloatArray<'l>,
    ys: JFloatArray<'l>,
    keys: JString<'l>,
    key_x: JFloatArray<'l>,
    key_y: JFloatArray<'l>,
    context: JString<'l>,
    n: jint,
    formal: jboolean,
) -> jstring {
    let (xs, ys) = (floats(&mut env, &xs), floats(&mut env, &ys));
    let (kx, ky) = (floats(&mut env, &key_x), floats(&mut env, &key_y));
    let keys: String = env.get_string(&keys).map(Into::into).unwrap_or_default();
    let context: String = env.get_string(&context).map(Into::into).unwrap_or_default();
    let path: Vec<(f32, f32)> = xs.into_iter().zip(ys).collect();
    let layout = varnele::gesture::Layout::new(keys.chars().zip(kx.into_iter().zip(ky)).map(|(c, (x, y))| (c, x, y)).collect());
    let json = {
        let ck = checker().lock().unwrap();
        varnele::json::gesture(&ck.an.gesture(&path, &layout, false, &context, n.max(1) as usize, formal != 0))
    };
    env.new_string(json).map(|s| s.into_raw()).unwrap_or(std::ptr::null_mut())
}
