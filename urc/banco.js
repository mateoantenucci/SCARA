// Banco de ensayo (solo simulación, ADR 0004, D59): las fallas F1–F5 y la
// carga, con lo que está vigente en el simulador. Sin canal de
// instrumentación, como con el robot real, el panel no aparece. La posición
// simulada va junto a la estimada, en la columna de la derecha de la página.
//
// Lo pedido y lo vigente van separados (D79): un campo que el operador editó
// no lo pisa el polling; al lado dice lo vigente, y «aplicando…» hasta que el
// estado SIM muestra la orden aplicada. La URC anota en el registro de
// eventos lo que cambió y si una orden no se aplicó.
// Usa post, benchState, benchSummary y el evento urc:estado de index.html.
(() => {
  const panel = document.getElementById("banco");
  const NAMES = ["J1", "J2", "J3", "J4"];
  const STUCK = { libre: "libre", activo: "trabado activo", inactivo: "trabado inactivo" };

  panel.innerHTML = `
    <h2>Banco de ensayo (solo simulación)</h2>
    <p class="muted small">Llega por el canal de instrumentación, que el robot real no tiene. La URC no usa estos datos para capturar ni planificar: siempre usa la posición estimada por pasos. La posición simulada está junto a la estimada, a la derecha.</p>
    <p class="hint" id="banco-now"></p>
    <h3>Carga</h3>
    <div class="row">
      <label>Carga en la herramienta (g) <input type="number" id="banco-load" min="0" step="50" style="width: 6em"></label>
      <button id="banco-load-set">Aplicar</button>
      <span class="small" id="banco-load-state"></span>
    </div>
    <h3>Fallas</h3>
    <div class="row">
      <label>F1 · Corriente del driver de <select id="banco-f1-motor"></select></label>
      <label>al <input type="number" id="banco-f1-current" min="10" max="100" step="10" style="width: 5em"> % de la nominal</label>
      <button id="banco-f1-set">Aplicar</button>
      <span class="small" id="banco-f1-state"></span>
    </div>
    <p class="muted small">Con menos corriente el motor tiene menos par: con carga o al arrancar, pierde pasos.</p>
    <div class="row">
      <label><input type="checkbox" id="banco-f2"> F2 · Driver de M4 sin corriente (J4 cae)</label>
      <span class="small" id="banco-f2-state"></span>
    </div>
    <div class="row" id="banco-f3">F3 · Hall trabado: </div>
    <div class="row">
      <label><input type="checkbox" id="banco-f4"> F4 · Cortar el enlace scara/1 (actúa el watchdog)</label>
      <span class="small" id="banco-f4-state"></span>
    </div>
    <div class="row">
      <button id="banco-f5">F5 · Reiniciar la UCI…</button>
      <button id="banco-reload" class="danger">Recargar el mundo…</button>
    </div>
    <div id="banco-feedback" class="feedback" role="status" aria-live="polite"></div>
    <h3>Motores en el simulador</h3>
    <table>
      <thead><tr><th>Motor</th><th>Con corriente</th><th>Corriente del driver</th><th>Pasos perdidos</th></tr></thead>
      <tbody id="banco-motors"></tbody>
    </table>
    <p class="muted small" id="banco-hall"></p>`;

  const $ = (id) => document.getElementById(id);
  const f1 = $("banco-f1-motor");
  NAMES.forEach((_, index) => f1.add(new Option(`M${index + 1}`, String(index + 1))));
  const f3 = $("banco-f3");
  NAMES.forEach((name, index) => {
    const label = document.createElement("label");
    label.textContent = `${name} `;
    const select = document.createElement("select");
    select.dataset.joint = String(index + 1);
    for (const [value, text] of Object.entries(STUCK)) select.add(new Option(text, value));
    label.append(select);
    f3.append(label);
  });
  const f3State = document.createElement("span");
  f3State.className = "small";
  f3.append(f3State);
  $("banco-motors").replaceChildren(...NAMES.map((_, index) => {
    const row = document.createElement("tr");
    row.innerHTML = `<td>M${index + 1}</td><td></td><td></td><td></td>`;
    return row;
  }));

  // Orden enviada y todavía sin el estado que la confirme: clave → hasta
  // cuándo (ms). Cubre el viaje del pedido y una consulta más; después manda
  // el pending de la URC, que la anotó antes de responder.
  const applying = new Map();
  const pending = (key) => (applying.get(key) || 0) > Date.now()
    || Boolean(benchState && benchState.pending.some((item) => item.key === key));

  const feedback = (error) => { $("banco-feedback").textContent = error ? error.message : ""; };
  async function order(key, request, done = null) {
    if (key) applying.set(key, Date.now() + 3000);
    try {
      await post("/api/banco", request);
      if (key) applying.set(key, Date.now() + 2 * POLL_MS);
      feedback(null);
      if (done) done();
    } catch (error) {
      applying.delete(key);
      feedback(error);
    }
  }

  // Un campo editado queda marcado hasta aplicarlo: el polling no lo pisa.
  for (const input of [$("banco-load"), $("banco-f1-current")]) {
    input.addEventListener("input", () => { input.dataset.edited = "1"; });
  }
  const applied = (input) => () => { delete input.dataset.edited; };

  $("banco-load-set").addEventListener("click", () =>
    order("carga", { carga: Number($("banco-load").value) }, applied($("banco-load"))));
  $("banco-f1-set").addEventListener("click", () => order(`F1 ${f1.value}`, {
    falla: "F1", motor: Number(f1.value), corriente: Number($("banco-f1-current").value),
  }, applied($("banco-f1-current"))));
  $("banco-f2").addEventListener("change", (event) => order("F2", { falla: "F2", activa: event.target.checked }));
  $("banco-f4").addEventListener("change", (event) => order("F4", { falla: "F4", activa: event.target.checked }));
  f3.addEventListener("change", (event) => {
    const joint = Number(event.target.dataset.joint);
    order(`F3 ${joint}`, { falla: "F3", articulacion: joint, estado: event.target.value });
  });
  // Otro motor: el porcentaje muestra el suyo, salvo que se haya editado.
  f1.addEventListener("change", render);
  $("banco-f5").addEventListener("click", () => {
    if (confirm("¿Reiniciar la UCI? El firmware vuelve a arrancar sin corriente y sin referencia (F5).")) {
      order(null, { falla: "F5" });
    }
  });
  $("banco-reload").addEventListener("click", () => {
    if (confirm("¿Recargar el mundo de Webots? La UCI vuelve a arrancar sin referencia.")) order(null, { recarga: true });
  });

  // El control muestra lo vigente, salvo que lo estén editando o la orden no se haya confirmado.
  function sync(element, value, key) {
    if (pending(key) || element.dataset.edited || (element.type === "number" && document.activeElement === element)) return;
    const property = element.type === "checkbox" ? "checked" : "value";
    if (element[property] !== value) element[property] = value;
  }

  function state(element, key, current, input = null) {
    const edited = input && input.dataset.edited && input.value !== String(current.raw);
    const text = pending(key) ? "aplicando…" : `vigente: ${current.text}${edited ? " · sin aplicar" : ""}`;
    if (element.textContent !== text) element.textContent = text;
    element.style.color = pending(key) ? "var(--accent)" : edited ? "var(--warn)" : "var(--muted)";
    if (input) input.classList.toggle("edited", Boolean(edited));
  }

  function render() {
    const bench = benchState;
    panel.hidden = !bench;
    if (!bench || !bench.simulated) return;
    const { load, faults } = benchSummary(bench);
    const now = `Vigente en el simulador: carga ${load} · ${faults.length ? faults.join(" · ") : "sin fallas"}`;
    if ($("banco-now").textContent !== now) $("banco-now").textContent = now;
    $("banco-now").className = faults.length ? "hint warn" : "hint";

    // El tope es LOAD_MAX de la URC (urc/instrumentation.py): no se repite acá.
    if ($("banco-load").max !== String(bench.load_max)) $("banco-load").max = bench.load_max;
    sync($("banco-load"), String(bench.load_g), "carga");
    state($("banco-load-state"), "carga", { text: `${bench.load_g} g`, raw: bench.load_g }, $("banco-load"));
    const motor = Number(f1.value);
    const current = bench.current_pct[motor - 1];
    sync($("banco-f1-current"), String(current), `F1 ${motor}`);
    state($("banco-f1-state"), `F1 ${motor}`, { text: `M${motor} al ${current} %`, raw: current }, $("banco-f1-current"));
    sync($("banco-f2"), bench.faults.F2, "F2");
    state($("banco-f2-state"), "F2", { text: bench.faults.F2 ? "activa" : "inactiva" });
    sync($("banco-f4"), bench.faults.F4, "F4");
    state($("banco-f4-state"), "F4", { text: bench.faults.F4 ? "activa (enlace cortado)" : "inactiva" });
    for (const select of f3.querySelectorAll("select")) {
      const joint = Number(select.dataset.joint);
      sync(select, bench.faults.F3[joint - 1], `F3 ${joint}`);
    }
    const stuckPending = NAMES.some((_, index) => pending(`F3 ${index + 1}`));
    f3State.textContent = stuckPending ? "aplicando…" : "";
    f3State.style.color = "var(--accent)";

    NAMES.forEach((_, joint) => {
      const cells = $("banco-motors").rows[joint].cells;
      const texts = [bench.power >> joint & 1 ? "sí" : "no", `${bench.current_pct[joint]} %`, String(bench.lost_steps[joint])];
      texts.forEach((text, i) => { if (cells[i + 1].textContent !== text) cells[i + 1].textContent = text; });
      cells[3].style.color = bench.lost_steps[joint] ? "var(--error)" : "";
    });
    const hall = `Hall que ve el firmware: ${bench.hall.toString(2).padStart(4, "0")} (bit 0 = J1)`;
    if ($("banco-hall").textContent !== hall) $("banco-hall").textContent = hall;
  }

  document.addEventListener("urc:estado", render);
})();
