//! Varnelė: a rule-based Lithuanian spell and grammar checker.
//!
//! The grammar (paradigms, sound rules) is compiled by the Python package into
//! one data file; this crate is the fast runtime that checks text with it.
//!
//! ```no_run
//! let data = std::fs::read("data/varnele.bin").unwrap();
//! let ck = varnele::Checker::from_bytes(&data).unwrap();
//! for f in ck.check_text("Grįžau pries pora dienų.", false, true) {
//!     println!("{} {} -> {:?}", f.rule, f.word, f.suggestions);
//! }
//! ```

pub mod analyzer;
pub mod checker;
pub mod data;
pub mod derivation;
pub mod fx;
pub mod gesture;
pub mod grammar;
pub mod json;
pub mod lm;
pub mod suggest;
pub mod text;

pub use checker::{Checker, Finding, KeyboardWord, WordStatus};
