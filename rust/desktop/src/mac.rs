//! The macOS side: an event tap sees every key, the engine decides, the fix is typed into the app.
//! Everything runs on the main thread, in the application's run loop. A tap blocks the keys behind
//! it while it runs, and CGEventTapPostEvent puts a fix ahead of them, so typing on can't overtake it.
//! No text is stored or logged; only the last fix is kept, for the menu.

use std::cell::RefCell;
use std::collections::BTreeSet;
use std::ffi::c_void;
use std::path::PathBuf;
use std::ptr::null_mut;

use objc2::rc::Retained;
use objc2::runtime::{AnyObject, NSObject, NSObjectProtocol, ProtocolObject};
use objc2::{define_class, msg_send, sel, MainThreadMarker, MainThreadOnly};
use objc2_app_kit::{
    NSApplication, NSApplicationActivationPolicy, NSControlStateValueOff, NSControlStateValueOn, NSMenu, NSMenuDelegate,
    NSMenuItem, NSSpellChecker, NSStatusBar, NSStatusItem, NSVariableStatusItemLength, NSWorkspace,
};
use objc2_foundation::{NSDictionary, NSNumber, NSString, NSTimer, NSURL};

use crate::engine::{Action, Edit, Engine, Key};

type Ref = *mut c_void;
type TapCallback = extern "C" fn(Ref, u32, Ref, *mut c_void) -> Ref;

#[link(name = "ApplicationServices", kind = "framework")]
extern "C" {
    fn CGEventTapCreate(tap: u32, place: u32, options: u32, mask: u64, callback: TapCallback, user: *mut c_void) -> Ref;
    fn CGEventTapEnable(tap: Ref, enable: bool);
    fn CGEventTapPostEvent(proxy: Ref, event: Ref);
    fn CGEventGetFlags(event: Ref) -> u64;
    fn CGEventSetFlags(event: Ref, flags: u64);
    fn CGEventGetIntegerValueField(event: Ref, field: u32) -> i64;
    fn CGEventKeyboardGetUnicodeString(event: Ref, max: usize, actual: *mut usize, buffer: *mut u16);
    fn CGEventKeyboardSetUnicodeString(event: Ref, length: usize, buffer: *const u16);
    fn CGEventCreateKeyboardEvent(source: Ref, key: u16, down: bool) -> Ref;
    fn AXIsProcessTrusted() -> bool;
    fn AXIsProcessTrustedWithOptions(options: *const c_void) -> bool;
}

#[link(name = "CoreFoundation", kind = "framework")]
extern "C" {
    fn CFMachPortCreateRunLoopSource(allocator: Ref, port: Ref, order: isize) -> Ref;
    fn CFRunLoopGetMain() -> Ref;
    fn CFRunLoopAddSource(run_loop: Ref, source: Ref, mode: Ref);
    fn CFRelease(object: Ref);
    static kCFRunLoopCommonModes: Ref;
}

#[link(name = "Carbon", kind = "framework")]
extern "C" {
    fn TISCopyCurrentKeyboardLayoutInputSource() -> Ref;
    fn TISGetInputSourceProperty(source: Ref, key: Ref) -> *const NSString;
    fn IsSecureEventInputEnabled() -> bool;
    static kTISPropertyInputSourceID: Ref;
}

const SESSION_TAP: u32 = 1;
const HEAD_INSERT: u32 = 0;
const KEY_DOWN: u32 = 10;
const MOUSE_DOWNS: [u32; 3] = [1, 3, 25];
const TAP_DISABLED: [u32; 2] = [0xFFFF_FFFE, 0xFFFF_FFFF];
const FIELD_KEYCODE: u32 = 9;
const FLAG_CONTROL: u64 = 0x40000;
const FLAG_OPTION: u64 = 0x80000;
const FLAG_COMMAND: u64 = 0x100000;

const KEY_V: i64 = 9;
const KEY_RETURN: i64 = 36;
const KEY_TAB: i64 = 48;
const KEY_BACKSPACE: i64 = 51;
const KEY_ENTER: i64 = 76;
/// keys with no character on them, or that the app acts on: escape, delete, home, end, arrows…
const KEYS_MOVING: [i64; 11] = [53, 117, 115, 119, 116, 121, 123, 124, 125, 126, 71];

/// how many UTF-16 units to send in one event
const CHUNK: usize = 16;

pub(crate) const BACKSPACE: u16 = KEY_BACKSPACE as u16;

const LITHUANIAN_LAYOUT: &str = "com.apple.keylayout.Lithuanian";
/// Off here from the start: what is typed in them is mostly not prose.
const APPS_OFF: [&str; 12] = [
    "com.apple.Terminal",
    "com.googlecode.iterm2",
    "dev.warp.Warp-Stable",
    "com.mitchellh.ghostty",
    "net.kovidgoyal.kitty",
    "org.alacritty",
    "com.github.wez.wezterm",
    "com.microsoft.VSCode",
    "com.todesktop.230313mzl4w4u92",
    "com.apple.dt.Xcode",
    "dev.zed.Zed",
    "com.sublimetext.4",
];
/// JetBrains IDEs, each with its own id
const APP_PREFIXES_OFF: [&str; 1] = ["com.jetbrains."];

thread_local! {
    static APP: RefCell<Option<App>> = const { RefCell::new(None) };
}

/// The checker, unless it is still loading: then the key just goes through.
macro_rules! ck_or_return {
    ($event:expr) => {
        match crate::checker().try_lock() {
            Ok(ck) => ck,
            Err(_) => return $event,
        }
    };
}
struct Settings {
    enabled: bool,
    formal: bool,
    any_layout: bool,
    apps_off: BTreeSet<String>,
}

impl Settings {
    fn path() -> PathBuf {
        let home = std::env::var("HOME").unwrap_or_default();
        PathBuf::from(home).join("Library/Application Support/Varnele/settings")
    }

    fn load() -> Settings {
        let mut s = Settings {
            enabled: true,
            formal: false,
            any_layout: false,
            apps_off: APPS_OFF.iter().map(|a| a.to_string()).collect(),
        };
        let Ok(text) = std::fs::read_to_string(Self::path()) else { return s };
        s.apps_off.clear();
        for line in text.lines() {
            match line.split_once(' ') {
                Some(("enabled", v)) => s.enabled = v == "1",
                Some(("formal", v)) => s.formal = v == "1",
                Some(("any_layout", v)) => s.any_layout = v == "1",
                Some(("off", app)) => {
                    s.apps_off.insert(app.to_string());
                }
                _ => {}
            }
        }
        s
    }

    fn save(&self) {
        let mut text = format!("enabled {}\nformal {}\nany_layout {}\n", self.enabled as u8, self.formal as u8, self.any_layout as u8);
        for app in &self.apps_off {
            text.push_str(&format!("off {app}\n"));
        }
        let path = Self::path();
        if let Some(dir) = path.parent() {
            let _ = std::fs::create_dir_all(dir);
        }
        let _ = std::fs::write(path, text);
    }

    fn app_is_off(&self, id: &str) -> bool {
        self.apps_off.contains(id) || APP_PREFIXES_OFF.iter().any(|p| id.starts_with(p))
    }
}

struct App {
    mtm: MainThreadMarker,
    engine: Engine,
    settings: Settings,
    tap: Ref,
    /// the frontmost app: pid, bundle id, name
    front: (i32, String, String),
    last_fix: Option<String>,
    /// the self-test's record of what was typed into the app
    trace: Option<Vec<String>>,
    status: Option<Retained<NSStatusItem>>,
}

fn layout_is_lithuanian() -> bool {
    unsafe {
        let source = TISCopyCurrentKeyboardLayoutInputSource();
        if source.is_null() {
            return false;
        }
        let id = TISGetInputSourceProperty(source, kTISPropertyInputSourceID);
        let lithuanian = !id.is_null() && (*id).to_string() == LITHUANIAN_LAYOUT;
        CFRelease(source);
        lithuanian
    }
}

impl App {
    fn watch_front(&mut self) {
        let Some(app) = NSWorkspace::sharedWorkspace().frontmostApplication() else { return };
        let pid = app.processIdentifier();
        if pid != self.front.0 {
            let id = app.bundleIdentifier().map(|s| s.to_string()).unwrap_or_default();
            let name = app.localizedName().map(|s| s.to_string()).unwrap_or_default();
            self.front = (pid, id, name);
            self.engine.new_app();
        }
    }

    /// Why nothing is fixed right now, if so.
    fn resting(&self) -> Option<String> {
        if !self.settings.enabled {
            return Some("Off".into());
        }
        if self.tap.is_null() {
            return Some("Waiting for the Accessibility permission".into());
        }
        if self.settings.app_is_off(&self.front.1) {
            return Some(format!("Off in {}", self.front.2));
        }
        if !self.settings.any_layout && !layout_is_lithuanian() {
            return Some("Resting: not the Lithuanian keyboard layout".into());
        }
        None
    }

    fn event(&mut self, proxy: Ref, kind: u32, event: Ref) -> Ref {
        if TAP_DISABLED.contains(&kind) {
            unsafe { CGEventTapEnable(self.tap, true) };
            self.engine.new_app();
            return event;
        }
        if MOUSE_DOWNS.contains(&kind) {
            let ck = ck_or_return!(event);
            self.engine.key(&ck, Key::Reset);
            return event;
        }
        if kind == KEY_DOWN {
            self.key_down(proxy, event)
        } else {
            event
        }
    }

    fn key_down(&mut self, proxy: Ref, event: Ref) -> Ref {
        let flags = unsafe { CGEventGetFlags(event) };
        let code = unsafe { CGEventGetIntegerValueField(event, FIELD_KEYCODE) };
        if code == KEY_V && flags & FLAG_CONTROL != 0 && flags & FLAG_OPTION != 0 {
            self.toggle(|s| s.enabled = !s.enabled);
            return null_mut();
        }
        self.watch_front();
        let ck = ck_or_return!(event);
        if self.resting().is_some() || unsafe { IsSecureEventInputEnabled() } {
            self.engine.key(&ck, Key::Reset);
            return event;
        }
        for key in decode(event, code, flags) {
            match self.engine.key(&ck, key) {
                Action::Pass => {}
                Action::Before(edit) => {
                    type_edit(proxy, &edit);
                    self.trace(&edit);
                    self.last_fix = self.engine.last_fix().map(|(a, b)| format!("{a} → {b}"));
                }
                Action::Instead(edit) => {
                    type_edit(proxy, &edit);
                    self.trace(&edit);
                    self.last_fix = None;
                    return null_mut();
                }
            }
        }
        event
    }

    fn trace(&mut self, edit: &Edit) {
        if let Some(trace) = &mut self.trace {
            trace.push(format!("-{} +{:?}", edit.delete, edit.insert));
        }
    }

    fn toggle(&mut self, change: impl FnOnce(&mut Settings)) {
        change(&mut self.settings);
        self.settings.save();
        self.engine.formal = self.settings.formal;
        self.engine.new_app();
        self.show_status();
    }

    fn show_status(&self) {
        let Some(item) = &self.status else { return };
        if let Some(button) = item.button(self.mtm) {
            let on = self.settings.enabled && !self.tap.is_null();
            button.setTitle(&NSString::from_str(if on { "✓" } else { "·" }));
        }
    }

    fn start_tap(&mut self) {
        if !self.tap.is_null() || !unsafe { AXIsProcessTrusted() } {
            return;
        }
        let mask = MOUSE_DOWNS.iter().fold(1u64 << KEY_DOWN, |m, k| m | 1 << k);
        unsafe {
            let tap = CGEventTapCreate(SESSION_TAP, HEAD_INSERT, 0, mask, on_event, null_mut());
            if tap.is_null() {
                return;
            }
            let source = CFMachPortCreateRunLoopSource(null_mut(), tap, 0);
            CFRunLoopAddSource(CFRunLoopGetMain(), source, kCFRunLoopCommonModes);
            CFRelease(source);
            CGEventTapEnable(tap, true);
            self.tap = tap;
        }
        self.show_status();
    }
}

fn decode(event: Ref, code: i64, flags: u64) -> Vec<Key> {
    if flags & (FLAG_COMMAND | FLAG_CONTROL) != 0 || (code == KEY_BACKSPACE && flags & FLAG_OPTION != 0) {
        return vec![Key::Moved];
    }
    match code {
        KEY_BACKSPACE => return vec![Key::Backspace],
        KEY_RETURN | KEY_ENTER | KEY_TAB => return vec![Key::Enter],
        c if KEYS_MOVING.contains(&c) => return vec![Key::Moved],
        _ => {}
    }
    let mut buffer = [0u16; 8];
    let mut n = 0;
    unsafe { CGEventKeyboardGetUnicodeString(event, buffer.len(), &mut n, buffer.as_mut_ptr()) };
    let text = String::from_utf16_lossy(&buffer[..n]);
    // nothing: a dead key; private use: a function key
    if text.is_empty() || text.chars().any(|c| c.is_control() || ('\u{e000}'..='\u{f8ff}').contains(&c)) {
        return vec![Key::Moved];
    }
    text.chars().map(Key::Char).collect()
}

fn post_key(proxy: Ref, code: u16, text: &[u16]) {
    for down in [true, false] {
        unsafe {
            let event = CGEventCreateKeyboardEvent(null_mut(), code, down);
            if event.is_null() {
                return;
            }
            CGEventSetFlags(event, 0);
            if !text.is_empty() {
                CGEventKeyboardSetUnicodeString(event, text.len(), text.as_ptr());
            }
            CGEventTapPostEvent(proxy, event);
            CFRelease(event);
        }
    }
}

fn type_edit(proxy: Ref, edit: &Edit) {
    for _ in 0..edit.delete {
        post_key(proxy, KEY_BACKSPACE as u16, &[]);
    }
    let units: Vec<u16> = edit.insert.encode_utf16().collect();
    for chunk in units.chunks(CHUNK) {
        post_key(proxy, 0, chunk);
    }
}

extern "C" fn on_event(proxy: Ref, kind: u32, event: Ref, _user: *mut c_void) -> Ref {
    APP.with_borrow_mut(|app| match app {
        Some(app) => app.event(proxy, kind, event),
        None => event,
    })
}

/// What the app typed since the last call (self-test).
pub(crate) fn take_trace() -> Vec<String> {
    APP.with_borrow_mut(|app| app.as_mut().and_then(|a| a.trace.as_mut()).map(std::mem::take).unwrap_or_default())
}

/// The system's English dictionary. Main thread only.
pub fn english() -> Box<dyn Fn(&str) -> bool> {
    let checker = NSSpellChecker::sharedSpellChecker();
    let language = NSString::from_str("en");
    Box::new(move |word| {
        let word = NSString::from_str(word);
        let miss = unsafe {
            checker.checkSpellingOfString_startingAt_language_wrap_inSpellDocumentWithTag_wordCount(
                &word, 0, Some(&language), false, 0, null_mut(),
            )
        };
        miss.length == 0
    })
}

const TAG_ENABLED: isize = 1;
const TAG_APP: isize = 2;
const TAG_LAYOUT: isize = 3;
const TAG_FORMAL: isize = 4;
const TAG_PERMISSION: isize = 5;
const TAG_QUIT: isize = 6;

define_class!(
    #[unsafe(super(NSObject))]
    #[thread_kind = MainThreadOnly]
    #[name = "VarneleMenu"]
    struct Menu;

    unsafe impl NSObjectProtocol for Menu {}

    unsafe impl NSMenuDelegate for Menu {
        #[unsafe(method(menuNeedsUpdate:))]
        fn menu_needs_update(&self, menu: &NSMenu) {
            self.fill(menu);
        }
    }

    impl Menu {
        #[unsafe(method(choose:))]
        fn choose(&self, item: &NSMenuItem) {
            let mtm = self.mtm();
            match item.tag() {
                TAG_QUIT => NSApplication::sharedApplication(mtm).terminate(None),
                TAG_PERMISSION => {
                    let url = "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility";
                    if let Some(url) = NSURL::URLWithString(&NSString::from_str(url)) {
                        NSWorkspace::sharedWorkspace().openURL(&url);
                    }
                }
                tag => APP.with_borrow_mut(|app| {
                    let Some(app) = app else { return };
                    let id = app.front.1.clone();
                    app.toggle(|s| match tag {
                        TAG_ENABLED => s.enabled = !s.enabled,
                        TAG_LAYOUT => s.any_layout = !s.any_layout,
                        TAG_FORMAL => s.formal = !s.formal,
                        TAG_APP if !s.apps_off.remove(&id) => {
                            s.apps_off.insert(id);
                        }
                        _ => {}
                    });
                }),
            }
        }

        #[unsafe(method(tick:))]
        fn tick(&self, timer: &NSTimer) {
            APP.with_borrow_mut(|app| {
                let Some(app) = app else { return };
                app.start_tap();
                if !app.tap.is_null() {
                    timer.invalidate();
                }
            });
        }
    }
);

impl Menu {
    fn new(mtm: MainThreadMarker) -> Retained<Menu> {
        let this = Menu::alloc(mtm).set_ivars(());
        unsafe { msg_send![super(this), init] }
    }

    fn add(&self, menu: &NSMenu, title: &str, tag: isize, state: Option<bool>) {
        let mtm = self.mtm();
        let action = (tag != 0).then_some(sel!(choose:));
        let item = unsafe {
            NSMenuItem::initWithTitle_action_keyEquivalent(NSMenuItem::alloc(mtm), &NSString::from_str(title), action, &NSString::new())
        };
        if tag == 0 {
            item.setEnabled(false);
        } else {
            let target: &AnyObject = self.as_ref();
            unsafe { item.setTarget(Some(target)) };
            item.setTag(tag);
        }
        if let Some(on) = state {
            item.setState(if on { NSControlStateValueOn } else { NSControlStateValueOff });
        }
        menu.addItem(&item);
    }

    fn fill(&self, menu: &NSMenu) {
        let mtm = self.mtm();
        menu.removeAllItems();
        APP.with_borrow_mut(|app| {
            let Some(app) = app else { return };
            app.watch_front();
            let line = app.resting().unwrap_or_else(|| {
                if app.engine.is_english() { "Resting: this text looks English".into() } else { format!("Fixing in {}", app.front.2) }
            });
            self.add(menu, &line, 0, None);
            if let Some(fix) = &app.last_fix {
                self.add(menu, &format!("Last fix: {fix}"), 0, None);
            }
            if app.tap.is_null() {
                self.add(menu, "Grant the Accessibility permission…", TAG_PERMISSION, None);
            }
            menu.addItem(&NSMenuItem::separatorItem(mtm));
            let s = &app.settings;
            self.add(menu, "Autocorrect (⌃⌥V)", TAG_ENABLED, Some(s.enabled));
            if !app.front.1.is_empty() {
                self.add(menu, &format!("Off in {}", app.front.2), TAG_APP, Some(s.app_is_off(&app.front.1)));
            }
            self.add(menu, "On every keyboard layout", TAG_LAYOUT, Some(s.any_layout));
            self.add(menu, "Formal Lithuanian", TAG_FORMAL, Some(s.formal));
        });
        menu.addItem(&NSMenuItem::separatorItem(mtm));
        self.add(menu, "Quit Varnelė", TAG_QUIT, None);
    }
}

/// The app, for one self-test: keys typed into `field`, which ends up in `out`.
pub fn run(selftest: Option<String>) {
    let mtm = MainThreadMarker::new().expect("on the main thread");
    std::thread::spawn(|| {
        let ck = crate::checker().lock().unwrap();
        let _ = ck.check_text("Labas rytas, sviesa.", false, true);   // also builds lazy indexes
    });

    let application = NSApplication::sharedApplication(mtm);
    application.setActivationPolicy(NSApplicationActivationPolicy::Accessory);

    let mut settings = Settings::load();
    settings.any_layout |= selftest.is_some();
    let mut engine = Engine::new();
    engine.formal = settings.formal;
    engine.english = Some(english());
    let item = NSStatusBar::systemStatusBar().statusItemWithLength(NSVariableStatusItemLength);
    let delegate = Menu::new(mtm);
    let menu = NSMenu::new(mtm);
    menu.setAutoenablesItems(false);
    menu.setDelegate(Some(ProtocolObject::from_ref(&*delegate)));
    item.setMenu(Some(&menu));

    let app = App {
        mtm,
        engine,
        settings,
        tap: null_mut(),
        front: (0, String::new(), String::new()),
        last_fix: None,
        trace: selftest.is_some().then(Vec::new),
        status: Some(item),
    };
    app.show_status();
    APP.with_borrow_mut(|a| *a = Some(app));

    // asks for the permission once; the timer starts the tap when it is granted
    let prompt = NSString::from_str("AXTrustedCheckOptionPrompt");
    let yes = NSNumber::numberWithBool(true);
    let options = NSDictionary::from_slices(&[&*prompt], &[&*yes]);
    unsafe { AXIsProcessTrustedWithOptions(Retained::as_ptr(&options).cast()) };
    let target: &AnyObject = delegate.as_ref();
    unsafe { NSTimer::scheduledTimerWithTimeInterval_target_selector_userInfo_repeats(1.0, target, sel!(tick:), None, true) };

    if let Some(out) = selftest {
        crate::mac_selftest::start(mtm, out);
    }
    application.run();
}
