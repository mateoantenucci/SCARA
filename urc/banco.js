// Banco de ensayo (solo simulación, ADR 0004, D59): la verdad del simulador
// junto a lo que sabe el robot, y las fallas F2–F5. Sin canal de
// instrumentación, como con el robot real, el panel no aparece.
(() => {
  const panel = document.getElementById("banco");
  const NAMES = ["J1", "J2", "J3", "J4"];
  const format = (joint, value) => joint === 3 ? `${(value / 100).toFixed(2)} mm` : `${(value / 100).toFixed(2)}°`;

  panel.innerHTML = `
    <h2>Banco de ensayo (solo simulación)</h2>
    <p class="muted">Llega por el canal de instrumentación, que el robot real no tiene. La URC no usa estos datos para capturar ni planificar: siempre usa la posición estimada por pasos.</p>
    <table>
      <thead><tr><th>Articulación</th><th>Estimada</th><th>Simulado</th><th>Diferencia</th><th>Motor con corriente</th></tr></thead>
      <tbody id="banco-joints"></tbody>
    </table>
    <p class="muted" id="banco-link"></p>
    <h3>Fallas</h3>
    <div class="row">
      <label><input type="checkbox" id="banco-f2"> F2 · Driver de M4 sin corriente (J4 cae)</label>
    </div>
    <div class="row" id="banco-f3">F3 · Hall trabado:</div>
    <div class="row">
      <label><input type="checkbox" id="banco-f4"> F4 · Cortar el enlace scara/1 (actúa el watchdog)</label>
      <button id="banco-f5">F5 · Reiniciar la UCI…</button>
    </div>
    <h3>Carga y mundo</h3>
    <div class="row">
      <label>Carga en la herramienta (g) <input type="number" id="banco-load" min="0" max="5000" step="50"></label>
      <button id="banco-load-set">Aplicar</button>
      <button id="banco-reload" class="danger">Recargar el mundo…</button>
    </div>
    <div id="banco-feedback" class="feedback" role="status" aria-live="polite"></div>`;

  const f3 = document.getElementById("banco-f3");
  NAMES.forEach((name, index) => {
    const label = document.createElement("label");
    label.textContent = `${name} `;
    const select = document.createElement("select");
    select.dataset.joint = String(index + 1);
    for (const state of ["libre", "activo", "inactivo"]) select.add(new Option(state, state));
    label.append(select);
    f3.append(label);
  });

  const feedback = (error) => {
    document.getElementById("banco-feedback").textContent = error ? error.message : "";
  };
  async function order(request) {
    try {
      const response = await fetch("/api/banco", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(request),
      });
      if (!response.ok) throw new Error((await response.json()).error);
      feedback(null);
    } catch (error) {
      feedback(error);
    }
  }

  document.getElementById("banco-f2").addEventListener("change", (event) =>
    order({ falla: "F2", activa: event.target.checked }));
  document.getElementById("banco-f4").addEventListener("change", (event) =>
    order({ falla: "F4", activa: event.target.checked }));
  f3.addEventListener("change", (event) =>
    order({ falla: "F3", articulacion: Number(event.target.dataset.joint), estado: event.target.value }));
  document.getElementById("banco-f5").addEventListener("click", () => {
    if (confirm("¿Reiniciar la UCI? El firmware vuelve a arrancar sin corriente y sin referencia (F5).")) {
      order({ falla: "F5" });
    }
  });
  document.getElementById("banco-load-set").addEventListener("click", () =>
    order({ carga: Number(document.getElementById("banco-load").value) }));
  document.getElementById("banco-reload").addEventListener("click", () => {
    if (confirm("¿Recargar el mundo de Webots? La UCI vuelve a arrancar sin referencia.")) order({ recarga: true });
  });

  // Los controles reflejan el estado del simulador, salvo el que se está tocando.
  function sync(id, value) {
    const element = document.getElementById(id);
    if (document.activeElement !== element) element[element.type === "checkbox" ? "checked" : "value"] = value;
  }

  async function refresh() {
    try {
      const [bench, state] = await Promise.all(["/api/banco", "/api/estado"].map((path) =>
        fetch(path).then((response) => response.json())));
      panel.hidden = !bench.connected;
      if (!bench.connected || !bench.simulated) return;
      const status = state.connected ? state.status : null;
      document.getElementById("banco-joints").innerHTML = "";
      NAMES.forEach((name, joint) => {
        const row = document.getElementById("banco-joints").insertRow();
        const estimated = status ? status.position[joint] : null;
        const simulated = bench.simulated[joint];
        const motor = bench.power >> joint & 1 ? "sí" : "no";
        for (const text of [name, estimated === null ? "—" : format(joint, estimated), format(joint, simulated),
          estimated === null ? "—" : format(joint, simulated - estimated), `M${joint + 1}: ${motor}`]) {
          row.insertCell().textContent = text;
        }
      });
      const age = status ? status.age_s : null;
      document.getElementById("banco-link").textContent =
        `Hall que ve el firmware: ${bench.hall.toString(2).padStart(4, "0")} (bit 0 = J1) · ` +
        (age === null ? "sin estado S de la UCI" : `último estado S hace ${age.toFixed(1)} s`) +
        (bench.faults.F4 ? " · enlace scara/1 cortado" : "");
      sync("banco-f2", bench.faults.F2);
      sync("banco-f4", bench.faults.F4);
      sync("banco-load", bench.load_g);
      for (const select of f3.querySelectorAll("select")) {
        if (document.activeElement !== select) select.value = bench.faults.F3[Number(select.dataset.joint) - 1];
      }
    } catch (error) {
      panel.hidden = true;
    }
  }
  refresh();
  setInterval(refresh, 250);
})();
