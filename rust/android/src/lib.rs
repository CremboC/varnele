//! JNI bridge: dev.imbrasas.varnele.Native.{warmUp, check, word, gestureNative, predictNative, ghostNative,
//! softNative, user*Native (the user's own language model)}
//! The compiled data file is embedded in the library, so the app ships one .so.

use std::sync::{Mutex, OnceLock};

use jni::objects::{JClass, JFloatArray, JString};
use jni::sys::{jboolean, jint, jstring};
use jni::JNIEnv;
use varnele::Checker;

static DATA: &[u8] = include_bytes!("../../../data/varnele.bin");
static CHECKER: OnceLock<Mutex<Checker>> = OnceLock::new();

/// where the user model is saved (set by userLoadNative)
static USER_PATH: Mutex<String> = Mutex::new(String::new());

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
    let _ = ck.keyboard_predict("Labas, kaip", "", 3, false); // and the language model's frequent words
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

/// Next-word predictions: the words likeliest to follow `context` (the text before the cursor,
/// up to a paragraph) that start with `prefix` (empty before a word is begun; diacritics may be
/// left out). `formal`: spoken forms as their standard forms. Returns a JSON array of {w, p},
/// likeliest first.
#[no_mangle]
pub extern "system" fn Java_dev_imbrasas_varnele_Native_predictNative<'l>(
    mut env: JNIEnv<'l>,
    _class: JClass<'l>,
    context: JString<'l>,
    prefix: JString<'l>,
    n: jint,
    formal: jboolean,
) -> jstring {
    let context: String = env.get_string(&context).map(Into::into).unwrap_or_default();
    let prefix: String = env.get_string(&prefix).map(Into::into).unwrap_or_default();
    let json = {
        let ck = checker().lock().unwrap();
        let items: Vec<String> = ck
            .keyboard_predict(&context, &prefix, n.max(1) as usize, formal != 0)
            .iter()
            .map(|(w, p)| format!("{{\"w\":{},\"p\":{p:.6}}}", varnele::json::string(w)))
            .collect();
        format!("[{}]", items.join(","))
    };
    env.new_string(json).map(|s| s.into_raw()).unwrap_or(std::ptr::null_mut())
}

/// The ghost for the word being typed (`typed`, after `context`): its completion, maybe with the
/// next word ("kodėl tu"); empty when there is none worth showing. `formal` as for predictNative.
#[no_mangle]
pub extern "system" fn Java_dev_imbrasas_varnele_Native_ghostNative<'l>(
    mut env: JNIEnv<'l>,
    _class: JClass<'l>,
    context: JString<'l>,
    typed: JString<'l>,
    formal: jboolean,
) -> jstring {
    let context: String = env.get_string(&context).map(Into::into).unwrap_or_default();
    let typed: String = env.get_string(&typed).map(Into::into).unwrap_or_default();
    let ghost = checker().lock().unwrap().keyboard_ghost(&context, &typed, formal != 0).unwrap_or_default();
    env.new_string(ghost).map(|s| s.into_raw()).unwrap_or(std::ptr::null_mut())
}

/// The keyboard's own diacritics decided again (Checker::keyboard_soft): `committed` is the sentence as
/// it stands, `typed` the same with the words the keyboard gave diacritics as typed. Returns a JSON
/// array of {start, end, word} (UTF-16 offsets) to put in their place.
#[no_mangle]
pub extern "system" fn Java_dev_imbrasas_varnele_Native_softNative<'l>(
    mut env: JNIEnv<'l>,
    _class: JClass<'l>,
    committed: JString<'l>,
    typed: JString<'l>,
) -> jstring {
    let committed: String = env.get_string(&committed).map(Into::into).unwrap_or_default();
    let typed: String = env.get_string(&typed).map(Into::into).unwrap_or_default();
    let mut utf16 = Vec::with_capacity(committed.len() + 1);
    let mut n = 0;
    for c in committed.chars() {
        utf16.push(n);
        n += c.len_utf16();
    }
    utf16.push(n);
    let fixes = checker().lock().unwrap().keyboard_soft(&committed, &typed);
    let items: Vec<String> = fixes.iter()
        .map(|(a, b, w)| format!("{{\"start\":{},\"end\":{},\"word\":{}}}", utf16[*a], utf16[*b], varnele::json::string(w)))
        .collect();
    env.new_string(format!("[{}]", items.join(","))).map(|s| s.into_raw()).unwrap_or(std::ptr::null_mut())
}

/// The user's language model: load its counts from `path` (an app-private file; missing = empty)
/// and save them there from now on.
#[no_mangle]
pub extern "system" fn Java_dev_imbrasas_varnele_Native_userLoadNative<'l>(mut env: JNIEnv<'l>, _class: JClass<'l>, path: JString<'l>) {
    let path: String = env.get_string(&path).map(Into::into).unwrap_or_default();
    checker().lock().unwrap().an.user.write().unwrap().load(&path);
    *USER_PATH.lock().unwrap() = path;
}

/// Learn and use the user's words (the setting); off: neither.
#[no_mangle]
pub extern "system" fn Java_dev_imbrasas_varnele_Native_userEnabledNative(_env: JNIEnv, _class: JClass, on: jboolean) {
    checker().lock().unwrap().an.user.write().unwrap().enabled = on != 0;
}

/// The text before the cursor after a finished word, as it ends up: finished sentences are learned.
/// `cut`: the text is the end of a longer one (its first sentence may be a piece).
#[no_mangle]
pub extern "system" fn Java_dev_imbrasas_varnele_Native_userObserveNative<'l>(
    mut env: JNIEnv<'l>,
    _class: JClass<'l>,
    text: JString<'l>,
    cut: jboolean,
) {
    let text: String = env.get_string(&text).map(Into::into).unwrap_or_default();
    checker().lock().unwrap().an.user.write().unwrap().observe(&text, cut != 0);
}

/// The message is done: learn its last sentence too. `gone`: sent or the field cleared (the same
/// text can't be seen again); otherwise the field was left.
#[no_mangle]
pub extern "system" fn Java_dev_imbrasas_varnele_Native_userCommitNative(_env: JNIEnv, _class: JClass, gone: jboolean) {
    checker().lock().unwrap().an.user.write().unwrap().commit(gone != 0);
}

/// Save the counts if they changed. Returns false if the file could not be written.
#[no_mangle]
pub extern "system" fn Java_dev_imbrasas_varnele_Native_userSaveNative(_env: JNIEnv, _class: JClass) -> jboolean {
    let path = USER_PATH.lock().unwrap().clone();
    if path.is_empty() {
        return 1;
    }
    checker().lock().unwrap().an.user.write().unwrap().save(&path).is_ok() as jboolean
}

/// Forget everything learned, and delete the file.
#[no_mangle]
pub extern "system" fn Java_dev_imbrasas_varnele_Native_userForgetNative(_env: JNIEnv, _class: JClass) {
    checker().lock().unwrap().an.user.write().unwrap().clear();
    let path = USER_PATH.lock().unwrap().clone();
    if !path.is_empty() {
        let _ = std::fs::remove_file(&path);
    }
    // nothing to save until something is learned again
    checker().lock().unwrap().an.user.write().unwrap().dirty = false;
}

/// How many words the user model has learned (counts after halving), for the settings screen.
#[no_mangle]
pub extern "system" fn Java_dev_imbrasas_varnele_Native_userWordsNative(_env: JNIEnv, _class: JClass) -> jint {
    checker().lock().unwrap().an.user.read().unwrap().total() as jint
}
