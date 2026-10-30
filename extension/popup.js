const enabled = document.getElementById("enabled");
const formal = document.getElementById("formal");
const site = document.getElementById("site");

async function main() {
  const settings = await chrome.storage.local.get({ enabled: true, formal: false, offSites: [] });
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  let host = null;
  try {
    host = new URL(tab.url).hostname;
  } catch {
    // a tab with no address of its own
  }
  enabled.checked = settings.enabled;
  formal.checked = settings.formal;
  if (host) {
    document.getElementById("host").textContent = host;
    site.checked = !settings.offSites.includes(host);
  } else {
    site.disabled = true;
  }
  enabled.addEventListener("change", () => chrome.storage.local.set({ enabled: enabled.checked }));
  formal.addEventListener("change", () => chrome.storage.local.set({ formal: formal.checked }));
  site.addEventListener("change", async () => {
    const { offSites } = await chrome.storage.local.get({ offSites: [] });
    const others = offSites.filter((h) => h !== host);
    chrome.storage.local.set({ offSites: site.checked ? others : [...others, host] });
  });
}

main();
