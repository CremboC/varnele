// The checker, in one place for all tabs. Chrome stops this worker when idle; it loads again in
// about 0.1 s at the next check, so its 60 MB are not held while nothing is typed.

let engine = null;

async function load() {
  const { instance } = await WebAssembly.instantiateStreaming(fetch(chrome.runtime.getURL("varnele.wasm")), {});
  const w = instance.exports;
  w.warm_up();
  const encoder = new TextEncoder();
  const decoder = new TextDecoder();
  return {
    check(text, formal) {
      const bytes = encoder.encode(text);
      const ptr = w.alloc(bytes.length);
      new Uint8Array(w.memory.buffer, ptr, bytes.length).set(bytes);
      const result = w.check(ptr, bytes.length, formal);
      return JSON.parse(decoder.decode(new Uint8Array(w.memory.buffer, result, w.result_len())));
    },
    language: (tally) => w.language(tally[0], tally[1], tally[2]),
  };
}

chrome.runtime.onMessage.addListener((message, sender, reply) => {
  engine ??= load();
  if (message.type === "check") {
    engine.then((e) => reply(message.texts.map((t) => e.check(t, message.formal))));
  } else if (message.type === "language") {
    engine.then((e) => reply(message.tallies.map((t) => e.language(t))));
  } else {
    return false;
  }
  return true;
});
