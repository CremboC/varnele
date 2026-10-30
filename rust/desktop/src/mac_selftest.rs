//! The real path end to end, which needs the permission and so can't be a unit test: a window with
//! a text view, keys posted like a keyboard's, the event tap fixing them. Run through
//! `open -n -a Varnele --args --selftest FILE`, then `open -a Varnele` to bring it forward (macOS
//! doesn't let it take the focus itself); the window takes the keyboard for a few seconds.

use std::cell::RefCell;
use std::collections::VecDeque;
use std::ffi::c_void;
use std::ptr::null_mut;

use objc2::rc::Retained;
use objc2::runtime::{AnyObject, NSObject, NSObjectProtocol};
use objc2::{define_class, msg_send, sel, MainThreadMarker, MainThreadOnly};
use objc2_app_kit::{NSApplication, NSBackingStoreType, NSTextView, NSWindow, NSWindowStyleMask};
use objc2_foundation::{NSPoint, NSRect, NSSize, NSString, NSTimer};

type Ref = *mut c_void;

#[link(name = "ApplicationServices", kind = "framework")]
extern "C" {
    fn CGEventCreateKeyboardEvent(source: Ref, key: u16, down: bool) -> Ref;
    fn CGEventPost(tap: u32, event: Ref);
    fn CFRelease(object: Ref);
}

const HID_TAP: u32 = 0;
const KEY_SPACE: u16 = 49;
const KEY_PERIOD: u16 = 47;
const KEY_COMMA: u16 = 43;
/// the keys of a QWERTY layout, by key code
const LETTERS: &[u8] = b"asdfhgzxcv bqweryt";
const LETTERS_2: &[(char, u16)] = &[('o', 31), ('u', 32), ('i', 34), ('p', 35), ('l', 37), ('j', 38), ('k', 40), ('n', 45), ('m', 46)];

/// typed key by key: \u{8} is backspace
const CASES: &[&str] = &[
    "maciau ",                 // a word short of its diacritics
    "kodel nepataiso as buvo ",   // context: aš buvau
    "the man is in the house, ",  // English stays
    "maciau \u{8}",            // backspace takes the fix back: maciau, and the space stays
    "www.google.com ",
    "prasau pagalbos. ",
    "is this the best, ",
    "the man is in the house, ",  // the same with the view's own text checking off, the last case
];

struct Test {
    window: Retained<NSWindow>,
    text: Retained<NSTextView>,
    keys: VecDeque<u16>,
    case: usize,
    wait: u32,
    lines: Vec<String>,
    out: String,
}

thread_local! {
    static TEST: RefCell<Option<Test>> = const { RefCell::new(None) };
}

fn key_code(c: char) -> Option<u16> {
    match c {
        ' ' => Some(KEY_SPACE),
        '.' => Some(KEY_PERIOD),
        ',' => Some(KEY_COMMA),
        '\u{8}' => Some(crate::mac::BACKSPACE),
        _ => LETTERS_2.iter().find(|(l, _)| *l == c).map(|(_, k)| *k)
            .or_else(|| LETTERS.iter().position(|&b| b as char == c && c != ' ').map(|i| i as u16)),
    }
}

fn view_settings(text: &NSTextView) -> String {
    format!(
        "spelling correction {}, replacement {}, completion {}, continuous {}",
        text.isAutomaticSpellingCorrectionEnabled(),
        text.isAutomaticTextReplacementEnabled(),
        text.isAutomaticTextCompletionEnabled(),
        text.isContinuousSpellCheckingEnabled(),
    )
}

fn post(code: u16) {
    for down in [true, false] {
        unsafe {
            let event = CGEventCreateKeyboardEvent(null_mut(), code, down);
            CGEventPost(HID_TAP, event);
            CFRelease(event);
        }
    }
}

define_class!(
    #[unsafe(super(NSObject))]
    #[thread_kind = MainThreadOnly]
    #[name = "VarneleSelfTest"]
    struct Runner;

    unsafe impl NSObjectProtocol for Runner {}

    impl Runner {
        #[unsafe(method(step:))]
        fn step(&self, _timer: &NSTimer) {
            TEST.with_borrow_mut(|t| {
                let Some(t) = t else { return };
                let application = NSApplication::sharedApplication(self.mtm());
                if t.wait > 0 {
                    t.wait -= 1;
                } else if let Some(k) = t.keys.pop_front() {
                    post(k);
                } else if t.case == 0 && t.lines.is_empty() && !t.window.isKeyWindow() {
                    application.activate();     // not in front yet
                } else {
                    let text = t.text.string().to_string();
                    t.lines.push(format!("{text}\t{:?}", crate::mac::take_trace()));
                    t.text.setString(&NSString::new());
                    t.case += 1;
                    if t.case == CASES.len() {
                        t.lines.push(view_settings(&t.text));
                        t.text.setAutomaticSpellingCorrectionEnabled(false);
                        t.text.setAutomaticTextReplacementEnabled(false);
                        t.text.setAutomaticTextCompletionEnabled(false);
                        t.text.setContinuousSpellCheckingEnabled(false);
                    }
                    if t.case > CASES.len() {
                        let _ = std::fs::write(&t.out, t.lines[1..].join("\n") + "\n");
                        application.terminate(None);
                        return;
                    }
                    t.keys = CASES[t.case - 1].chars().filter_map(key_code).collect();
                    t.wait = 20;
                }
            });
        }
    }
);

pub fn start(mtm: MainThreadMarker, out: String) {
    let frame = NSRect::new(NSPoint::new(200.0, 400.0), NSSize::new(500.0, 200.0));
    let style = NSWindowStyleMask::Titled;
    let window = unsafe {
        NSWindow::initWithContentRect_styleMask_backing_defer(NSWindow::alloc(mtm), frame, style, NSBackingStoreType::Buffered, false)
    };
    unsafe { window.setReleasedWhenClosed(false) };
    window.setTitle(&NSString::from_str("Varnelė self-test"));
    let text = NSTextView::initWithFrame(NSTextView::alloc(mtm), frame);
    window.setContentView(Some(&text));
    window.makeKeyAndOrderFront(None);
    window.makeFirstResponder(Some(&text));
    NSApplication::sharedApplication(mtm).activate();
    // the data and the tap come first
    let test = Test { window, text, keys: VecDeque::new(), case: 0, wait: 150, lines: Vec::new(), out };
    TEST.with_borrow_mut(|t| *t = Some(test));
    let runner: Retained<Runner> = unsafe { msg_send![super(Runner::alloc(mtm).set_ivars(())), init] };
    let target: &AnyObject = runner.as_ref();
    unsafe { NSTimer::scheduledTimerWithTimeInterval_target_selector_userInfo_repeats(0.02, target, sel!(step:), None, true) };
    std::mem::forget(runner);
}
