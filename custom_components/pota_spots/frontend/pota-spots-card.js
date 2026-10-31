// POTA Spots card loader – registered by the pota_spots integration as an extra frontend module.
//
// Extra modules are imported in parallel with Home Assistant's app bundle and, being small,
// often run first. The app then replaces window.customElements (and HTMLElement) with a
// scoped-registry polyfill, which drops any element defined before that point ("custom
// element doesn't exist", e.g. in the companion app). So wait until the frontend has defined
// its root element in the current registry, then load the actual card.

const whenFrontendReady = () =>
  new Promise((resolve) => {
    const check = () =>
      customElements.get("home-assistant") ? resolve() : setTimeout(check, 50);
    check();
  });

// Keep the ?v= cache buster of this URL for the card itself.
const cardUrl = new URL(`./pota-spots-card-impl.js${new URL(import.meta.url).search}`, import.meta.url);

whenFrontendReady()
  .then(() => import(cardUrl.href))
  .catch((err) => console.error("POTA Spots card failed to load", err));
