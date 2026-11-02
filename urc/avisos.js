// Avisos de la página (D78). La URC lleva el registro de eventos: lo que
// informa la UCI, lo que decide la URC, las órdenes del operador (aceptadas o
// rechazadas) y los cambios del banco, cada uno con número y hora. La página
// lo muestra entero en «Registro de eventos» y saca de él los avisos
// emergentes: solo lo que el operador tiene que ver ahora, esté donde esté en
// la página. Lo que vale ahora (enlace, motores, referencia, banco) no es un
// evento: lo muestra la barra de estado de index.html.
const avisos = (() => {
  const MAX_TOASTS = 5;
  // Cuánto queda un aviso emergente, por nivel; null: hasta cerrarlo. Un
  // error (EV LOST, BOOT inesperado, ERR, enlace cortado) puede llegar con
  // el operador mirando Webots: no se va solo.
  const LIFE = { ok: 5000, aviso: 10000, error: null };
  const SOURCES = { UCI: "UCI", URC: "URC", Banco: "Banco de ensayo", Operador: "Orden" };
  const events = new Map();        // número → evento, como lo da /api/eventos
  const toasts = new Map();        // clave → elemento
  let version = 0, loaded = false, busy = false;

  const $ = (id) => document.getElementById(id);
  const clock = (seconds) => new Date(seconds * 1000).toLocaleTimeString("es-AR", { hour12: false });
  const heading = (event) => (event.rejected ? `${event.source}: rechazado` : SOURCES[event.source] || event.source);

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function detailBlock(detail) {
    const block = element("details", "detail");
    block.append(element("summary", "", "Por qué y qué probar"), element("p", "", detail));
    return block;
  }

  // Un aviso emergente. key lo identifica: el mismo evento repetido actualiza
  // el que ya está a la vista en lugar de apilar otro.
  function notify(key, { level, title, text, detail = null, meta = "", life = LIFE[level] }) {
    let toast = toasts.get(key);
    if (!toast) {
      toast = element("div", "toast");
      toast.addEventListener("mouseenter", () => clearTimeout(toast.timer));
      toast.addEventListener("mouseleave", () => schedule(key, toast));
      toasts.set(key, toast);
      $("toasts").prepend(toast);
      // Si hay demasiados, se va el más viejo que se cierra solo; si no, el más viejo.
      if (toasts.size > MAX_TOASTS) {
        const all = [...toasts.entries()];
        const [old] = all.find(([, t]) => t.life !== null) || all[0];
        dismiss(old);
      }
    }
    toast.className = `toast ${level}`;
    toast.setAttribute("role", level === "error" ? "alert" : "status");
    toast.life = life;
    toast.text = text;
    const close = element("button", "close", "×");
    close.title = "Cerrar";
    close.addEventListener("click", () => dismiss(key));
    const head = element("div", "head");
    head.append(element("strong", "", title), element("span", "meta", meta), close);
    const open = toast.querySelector("details[open]") !== null;
    toast.replaceChildren(head, element("p", "", text));
    if (detail) toast.append(detailBlock(detail));
    if (open) toast.querySelector("details").open = true;
    schedule(key, toast);
  }

  function schedule(key, toast) {
    clearTimeout(toast.timer);
    if (toast.life !== null) toast.timer = setTimeout(() => dismiss(key), toast.life);
  }

  function dismiss(key) {
    const toast = toasts.get(key);
    if (!toast) return;
    clearTimeout(toast.timer);
    toast.remove();
    toasts.delete(key);
  }

  // Cierra los avisos de un problema que ya se resolvió (el enlace volvió, el
  // homing limpió la duda): quedan en el registro, no en pantalla.
  function settle(prefix) {
    for (const [key, toast] of [...toasts]) if (toast.text.startsWith(prefix)) dismiss(key);
  }

  function meta(event) {
    return `#${event.n} · ${clock(event.time)}${event.repeats > 1 ? ` · ×${event.repeats}` : ""}`;
  }

  // Los eventos info (las órdenes aceptadas, lo que la URC va haciendo)
  // quedan solo en el registro.
  function announce(event) {
    if (event.level === "info") return;
    notify(`evento ${event.n}`, { level: event.level, title: heading(event), text: event.text, detail: event.detail,
      meta: meta(event) });
  }

  function render() {
    const important = $("events-important").checked;
    const shown = [...events.values()].reverse().filter((event) => !important || event.level !== "info");
    const now = Date.now() / 1000;
    // Un detalle abierto sigue abierto cuando llega otro evento.
    const open = new Set([...$("events").querySelectorAll("details[open]")].map((block) => block.closest("li").dataset.n));
    $("events").replaceChildren(...shown.map((event) => {
      const item = element("li", `event ${event.level}${now - event.last < 8 ? " new" : ""}`);
      item.dataset.n = event.n;
      const head = element("div", "head");
      head.append(element("span", "n", `#${event.n}`), element("time", "", clock(event.time)),
        element("span", "source", heading(event)));
      if (event.repeats > 1) head.append(element("span", "repeats", `×${event.repeats} (última ${clock(event.last)})`));
      item.append(head, element("div", "text", event.text));
      if (event.detail) {
        const block = detailBlock(event.detail);
        block.open = open.has(String(event.n));
        item.append(block);
      }
      return item;
    }));
    $("events-empty").hidden = shown.length > 0;
    $("events-count").textContent = events.size ? `${events.size}` : "";
  }

  // Trae lo nuevo cuando la versión del registro cambió (llega con /api/estado).
  async function update(current) {
    if (busy || current === version) return;
    busy = true;
    try {
      let data = await (await fetch(`/api/eventos?desde=${version}`)).json();
      if (data.version < version) {
        // La URC se reinició: el registro empieza de nuevo.
        events.clear();
        data = await (await fetch("/api/eventos?desde=0")).json();
      }
      for (const event of data.events) {
        events.set(event.n, event);
        // Lo que ya estaba al abrir la página es historia: no se anuncia.
        if (loaded) announce(event);
      }
      for (const n of [...events.keys()].slice(0, Math.max(0, events.size - 200))) events.delete(n);
      version = data.version;
      loaded = true;
      render();
    } catch (error) {
      // La URC no responde: lo dice la barra de estado.
    } finally {
      busy = false;
    }
  }

  $("events-important").addEventListener("change", render);
  return { update, notify, dismiss, settle };
})();
