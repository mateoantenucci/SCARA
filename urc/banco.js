// Banco de ensayo (solo simulación, ADR 0004, D59): las fallas F1–F5 y la
// carga, con lo que está vigente en el simulador. Sin canal de
// instrumentación, como con el robot real, el panel no aparece. La posición
// simulada va junto a la estimada, en la columna de la derecha de la página.
//
// Lo pedido y lo vigente van separados (D79): un campo que el operador editó
// no lo pisa el polling; al lado dice lo vigente, y «aplicando…» hasta que el
// estado SIM muestra la orden aplicada. La URC anota en el registro de
// eventos lo que cambió y si una orden no se aplicó.
// Usa post, ask, benchState, benchSummary y el evento urc:estado de index.html.
(() => {
  const panel = document.getElementById("banco");
  const NAMES = ["J1", "J2", "J3", "J4"];
  const STUCK = { libre: "libre", activo: "trabado activo", inactivo: "trabado inactivo" };

  panel.innerHTML = `
    <div class="card-head">
      <h2>Banco de ensayo (solo simulación)</h2>
      <span class="badge" id="banco-now"></span>
    </div>
    <div class="row fields">
      <label class="field">Carga en la herramienta (g) <input type="number" id="banco-load" min="0" step="50" style="width: 6em"></label>
      <button id="banco-load-set">Aplicar</button>
      <span class="small" id="banco-load-state"></span>
    </div>
    <h3>Movido a mano sin corriente</h3>
    <div class="row fields">
      <label class="field">Mover a mano <select id="banco-hand-joint"></select></label>
      <label class="field">Posición (<span id="banco-hand-unit">°</span>) <input type="number" id="banco-hand-position" value="10" step="0.1" style="width: 6em"></label>
      <button id="banco-hand-set">Mover a mano…</button>
      <span class="small" id="banco-hand-state"></span>
    </div>
    <h3>Fallas</h3>
    <div class="row fields">
      <label class="field">F1 · Corriente del driver de <select id="banco-f1-motor"></select></label>
      <label class="field">% de la nominal <input type="number" id="banco-f1-current" min="10" max="100" step="10" style="width: 5em"></label>
      <button id="banco-f1-set">Aplicar</button>
      <span class="small" id="banco-f1-state"></span>
    </div>
    <div class="row">
      <label class="check"><input type="checkbox" id="banco-f2"> F2 · Driver de M4 sin corriente (J4 cae)</label>
      <span class="small" id="banco-f2-state"></span>
    </div>
    <div class="row fields" id="banco-f3"><span class="small" style="font-weight: 600; padding-bottom: 7px">F3 · Hall trabado</span></div>
    <div class="row">
      <label class="check"><input type="checkbox" id="banco-f4"> F4 · Cortar el enlace scara/1 (actúa el watchdog)</label>
      <span class="small" id="banco-f4-state"></span>
    </div>
    <div class="row" style="margin-top: 12px">
      <button id="banco-f5" class="danger">F5 · Reiniciar la UCI…</button>
      <button id="banco-reload" class="danger">Recargar el mundo…</button>
    </div>
    <div id="banco-feedback" class="feedback" role="status" aria-live="polite"></div>
    <h3>Obstáculo de ensayo</h3>
    <p class="note">El banco muestra el contacto; el robot continúa y puede perder pasos.</p>
    <div class="row fields">
      <label class="field">Tipo <select id="banco-obstacle-type"><option value="maceta">maceta</option><option value="mesa">mesa</option></select></label>
      <label class="field">X (mm) <input id="banco-obstacle-x" type="number" min="-1000" max="1000" step="1" value="375"></label>
      <label class="field">Y (mm) <input id="banco-obstacle-y" type="number" min="-1000" max="1000" step="1" value="-217"></label>
      <label class="field">Altura mesa (mm) <input id="banco-obstacle-height" type="number" min="-20" max="90" step="1" value="40" style="width: 5em"></label>
      <button id="banco-obstacle-set">Poner obstáculo</button>
      <button id="banco-obstacle-remove">Sacar obstáculo</button>
      <span class="small" id="banco-obstacle-state"></span>
    </div>
    <h3>Empujón en la punta</h3>
    <div class="row fields">
      <label class="field">Fuerza (N) <input id="banco-push-force" type="number" min="0.5" max="50" step="0.5" value="12" style="width: 5em"></label>
      <label class="field">Dirección (°) <input id="banco-push-dir" type="number" min="-180" max="180" step="5" value="90" style="width: 5em"></label>
      <button id="banco-push-set">Aplicar empujón…</button>
      <span class="small" id="banco-push-state"></span>
    </div>
    <h3>Motores en el simulador</h3>
    <div class="scroll"><table>
      <thead><tr><th>Motor</th><th>Con corriente</th><th>Corriente del driver</th><th>Pasos perdidos</th></tr></thead>
      <tbody id="banco-motors"></tbody>
    </table></div>
    <p class="note" id="banco-contact" role="status" aria-live="polite"></p>
    <p class="note" id="banco-effort"></p>
    <p class="note" id="banco-hall" style="margin-top: 8px"></p>
    <details class="help">
      <summary>Cómo funciona</summary>
      <p>La maceta es un cilindro fijo de ⌀120 × 150 mm y la mesa un bloque fijo de 160 × 160 mm con tapa a la altura indicada; X e Y se miden desde la torre. El banco los pone en Webots. Capturar, planificar y comprobar choques siguen usando el robot conocido por la URC: el obstáculo de ensayo solo existe en la planta. Un contacto no frena automáticamente el robot.</p>
      <p>El empujón aplica una fuerza horizontal breve (0,5 s) en la punta con los motores energizados: por debajo del par de retención el rotor cede dentro del ciclo eléctrico y vuelve; si lo supera, salta ciclos completos y queda corrido sin aviso hasta pasar por un Hall o hacer homing.</p>
      <p>Los picos son esfuerzos articulares (J1–J3 en N·m; J4 en N), desde que se puso el obstáculo. Los límites provisionales vienen de las aceleraciones de D76 con 5 kg: superar ese uso normal no demuestra rotura. Los pasos perdidos permanecen después de sacar el obstáculo; el Hall puede avisarlos más adelante.</p>
      <p>Llega por el canal de instrumentación, que el robot real no tiene. La URC no usa estos datos para capturar ni planificar: siempre usa la posición estimada por pasos. La posición simulada está junto a la estimada, a la derecha.</p>
      <p>F1: con menos corriente el motor tiene menos par; con carga o al arrancar, pierde pasos. Cada orden se confirma cuando el simulador la muestra aplicada: al lado del control dice lo vigente y «aplicando…» mientras tanto.</p>
      <p>Mover a mano coloca una articulación en la posición indicada, solo con todos los drivers sin corriente (DISABLE). La estimada no cambia; al habilitar se retiene la posición física, pero sigue sin referencia. Hacé homing o llevá el robot a las marcas antes de la referencia manual: declararla fuera del reposo deja la trayectoria corrida sin aviso.</p>
    </details>`;

  const $ = (id) => document.getElementById(id);
  const f1 = $("banco-f1-motor");
  const hand = $("banco-hand-joint");
  NAMES.forEach((name, index) => hand.add(new Option(name, String(index + 1))));
  NAMES.forEach((_, index) => f1.add(new Option(`M${index + 1}`, String(index + 1))));
  const f3 = $("banco-f3");
  NAMES.forEach((name, index) => {
    const label = document.createElement("label");
    label.className = "field";
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
  hand.addEventListener("change", render);
  $("banco-obstacle-type").addEventListener("change", render);
  $("banco-hand-set").addEventListener("click", async () => {
    const joint = Number(hand.value), position = Number($("banco-hand-position").value);
    if (!Number.isFinite(position) || $("banco-hand-position").value === "") {
      feedback(new Error("Indicá la posición para mover a mano"));
      return;
    }
    if (await ask(`J${joint} se colocará en ${position} ${joint === 4 ? "mm" : "°"}, sin modificar la posición estimada por pasos.`,
      { title: "¿Mover a mano sin corriente?", confirm: "Mover a mano" })) {
      order("mano", { mano: { articulacion: joint, posicion: Math.round(position * 100) } });
    }
  });
  $("banco-obstacle-set").addEventListener("click", () => {
    const tipo = $("banco-obstacle-type").value;
    const obstaculo = {
      tipo, x: Number($("banco-obstacle-x").value), y: Number($("banco-obstacle-y").value),
    };
    if (tipo === "mesa") obstaculo.altura = Number($("banco-obstacle-height").value);
    order("obstaculo", { obstaculo });
  });
  $("banco-obstacle-remove").addEventListener("click", () =>
    order("obstaculo", { obstaculo: { tipo: "ninguno" } }));
  $("banco-push-set").addEventListener("click", async () => {
    const fuerza_n = Number($("banco-push-force").value), direccion = Number($("banco-push-dir").value);
    if (!Number.isFinite(fuerza_n) || !Number.isFinite(direccion)) {
      feedback(new Error("Indicá fuerza y dirección del empujón"));
      return;
    }
    if (await ask(`Se aplicará un empujón horizontal de ${fuerza_n} N a ${direccion}° en la punta durante 0,5 s.`,
      { title: "¿Aplicar empujón en la punta?", confirm: "Empujar" })) {
      order("empujon", { empujon: { fuerza_n, direccion } });
    }
  });

  $("banco-f5").addEventListener("click", async () => {
    if (await ask("El firmware vuelve a arrancar sin corriente y sin referencia (F5).",
      { title: "¿Reiniciar la UCI?", confirm: "Reiniciar", danger: true })) order(null, { falla: "F5" });
  });
  $("banco-reload").addEventListener("click", async () => {
    if (await ask("La UCI vuelve a arrancar sin referencia.",
      { title: "¿Recargar el mundo de Webots?", confirm: "Recargar", danger: true })) order(null, { recarga: true });
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
    const joint = Number(hand.value);
    $("banco-hand-unit").textContent = joint === 4 ? "mm" : "°";
    const bounds = bench.manual_limits[joint - 1];
    $("banco-hand-position").min = bounds[0] / 100;
    $("banco-hand-position").max = bounds[1] / 100;
    $("banco-hand-set").disabled = bench.power !== 0 || pending("mano");
    $("banco-hand-state").textContent = pending("mano") ? "aplicando…" : bench.power ? "Requiere DISABLE: todos los drivers sin corriente" : "Sin corriente · posición física y estimada a la derecha";
    const { load, faults } = benchSummary(bench);
    const now = `Vigente en el simulador: carga ${load} · ${faults.length ? faults.join(" · ") : "sin fallas"}`;
    if ($("banco-now").textContent !== now) $("banco-now").textContent = now;
    $("banco-now").className = faults.length ? "badge warn" : "badge";

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
    $("banco-obstacle-height").disabled = $("banco-obstacle-type").value !== "mesa";
    const obstacle = bench.obstacle;
    $("banco-obstacle-state").textContent = pending("obstaculo") ? "aplicando…" : obstacle
      ? `vigente: ${obstacle.tipo}${obstacle.tipo !== "ninguno" ? `, X ${obstacle.x}, Y ${obstacle.y}${obstacle.tipo === "mesa" ? `, altura ${obstacle.altura}` : ""} mm` : ""}` : "sin datos";
    const push = bench.push;
    $("banco-push-state").textContent = pending("empujon") ? "aplicando…" : push
      ? `último: ${push.fuerza_n} N a ${push.direccion}° (${push.duracion_ms} ms)` : "sin empujón aplicado";
    $("banco-contact").textContent = bench.contact ? `Contacto: ${bench.contact} con ${obstacle?.tipo || "entorno"}` : "Sin contacto";
    $("banco-contact").className = bench.contact ? "note warn" : "note";
    $("banco-effort").textContent = bench.peak_effort ? "Pico / límite provisional: " + bench.peak_effort.map((peak, i) =>
      `J${i + 1}: ${peak.toFixed(2)} / ${bench.effort_limit[i].toFixed(2)} ${i === 3 ? "N" : "N·m"}`).join(" · ") : "";
    const hall = `Hall que ve el firmware: ${bench.hall.toString(2).padStart(4, "0")} (bit 0 = J1)`;
    if ($("banco-hall").textContent !== hall) $("banco-hall").textContent = hall;
  }

  document.addEventListener("urc:estado", render);
})();
