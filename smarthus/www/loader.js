// Laster alltid nyeste versjon av Smarthus, uten at nettleseren henger igjen på en gammel kopi.
let version = "0";
try {
  version = (await (await fetch("/local/smarthus/version.txt", { cache: "no-store" })).text()).trim();
} catch (e) {
  /* bruker siste kjente */
}
await import(`/local/smarthus/smarthus-card.js?v=${encodeURIComponent(version)}`);
