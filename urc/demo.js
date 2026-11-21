// Demo de la presentación: atajos para la defensa, con las poses y los
// parámetros ya cargados. Aparece solo con #demo en la dirección
// (http://127.0.0.1:8766/#demo); sin eso, la página es la de siempre.
// Cada botón encadena órdenes de la misma API que usa el resto de la página
// y espera a que el robot termine: no agrega nada a la URC ni a los protocolos.
// Usa post, showError y el evento urc:estado de index.html.
(() => {
  const panel = document.getElementById("demo");
  // demo-barrido-ptp.json, puntos 1 y 2: J1 de −90° a +90° con el codo en
  // −60° y J4 en 40 mm. Con J1 = 0° la herramienta pasa por X 375, Y −217 mm:
  // ahí va la maceta, como en el ensayo C1. La maceta se pone con el robot ya
  // en el punto 1, porque el tramo desde el reposo también puede rozarla.
  // Al 50 % el barrido dura 4,3 s y el choque se alcanza a ver (al 100 %, ~2,5 s).
  const SWEEP_START = [-90, -60, 0, 40], SWEEP_END = [90, -60, 0, 40], SWEEP_SPEED = 50;
  const POT = { tipo: "maceta", x: 375, y: -217 };
  // F1 como en el ensayo de pérdida de pasos: 5 kg en total, M4 al 50 % y J4 de 60 a 10 mm.
  const F1_LOW = [0, 0, 0, 60], F1_HIGH = [0, 0, 0, 10], LOAD_G = 4850, F1_CURRENT = 50;
  const F5_J4 = 40;
  const REST = [0, 0, 0, 12000];
  const PLAYING = ["reproduciendo", "pausando", "pausada"];

  // Un bloque por fila, con los pasos numerados en el orden de la presentación.
  // Compacto a propósito: en media pantalla del proyector entran la tabla de
  // posiciones, este panel y el tráfico sin desplazarse.
  const GROUPS = [
    { title: "Arranque", note: "~1 min: busca los Hall de J4, J1, J2 y J3 y vuelve al reposo.", steps: [
      { label: "Habilitar y homing", run: home }] },
    { title: "Teach & play", note: "Jog: A/D J1 · W/S J2 · Q/E J3 · R/F J4 · Tab cartesiano · Espacio captura.", steps: [
      { label: "Trayectoria nueva",
        run: () => post("/api/trayectoria/nueva", { discard: true }).then(() => "Vacía, lista para capturar") },
      { label: "▶ Grabada", run: () => play() },
      { label: "▶ Cuadrado LIN", run: () => play("demo-cuadrado-lin.json") },
      { label: "▶ Pick and place", run: () => play("demo-pick-and-place.json") }] },
    { title: "Falla 1 · Maceta", note: "Barrido de J1 de −90° a +90° con el codo en −60°; maceta en X 375, Y −217.", steps: [
      { label: "1 · Ir y poner la maceta", run: pot },
      { label: "2 · Barrer", run: sweep },
      { label: "3 · Sacar la maceta", run: () => obstacle({ tipo: "ninguno" }).then(() => "Sin maceta: el brazo queda corrido") }] },
    { title: "Falla 2 · F1 y EV LOST", note: "5 kg en la herramienta y M4 con la mitad de corriente: menos par.", steps: [
      { label: "1 · J4 a 60 mm, 5 kg, M4 50 %", run: f1Prepare },
      { label: "2 · Subir J4", run: f1Up },
      { label: "3 · M4 100 % y estacionar", run: f1Park }] },
    { title: "Falla 3 · F5", note: "Sube J4 y reinicia el firmware: sin corriente, J4 cae. Sin referencia, solo reinicia.", steps: [
      { label: "Subir J4 y reiniciar la UCI", danger: true, run: f5 }] },
    { title: "Para ensayar", folded: true,
      note: "Restablecer: sin obstáculo ni carga, corrientes al 100 %, sin fallas. Recargar: vuelve al arranque.", steps: [
      { label: "Restablecer el banco", run: resetBench },
      { label: "Recargar el mundo", danger: true, always: true, run: reload }] },
  ];

  panel.innerHTML = `
    <div class="card-head" style="margin-bottom: 4px">
      <h2>Demo de la presentación</h2>
      <span class="grow"></span>
      <span class="badge">solo con #demo</span>
    </div>
    <div id="demo-steps"></div>
    <div class="demo-group"><strong>Tráfico scara/1</strong>
      <span class="demo-status">Sin S, PING, SEG ni OK: los que llegan decenas de veces por segundo.</span></div>
    <pre id="demo-traffic" style="max-height: none; min-height: 10.4em; margin-top: 4px"></pre>
    <div id="demo-folded" style="margin-top: 8px"></div>`;

  const $ = (id) => document.getElementById(id);
  const buttons = new Map();
  for (const group of GROUPS) {
    const element = document.createElement("div");
    element.className = "demo-group";
    const title = document.createElement("strong");
    title.textContent = group.title;
    const row = document.createElement("div");
    row.className = "row";
    const status = document.createElement("p");
    status.className = "demo-status";
    status.textContent = group.note;
    for (const step of group.steps) {
      const button = document.createElement("button");
      button.textContent = step.label;
      if (step.danger) button.className = "danger";
      button.addEventListener("click", () => run(step, status));
      row.append(button);
      buttons.set(step, button);
    }
    element.append(title, row, status);
    if (group.folded) {
      // Lo que no se usa frente al profesor, plegado: no ocupa lugar en pantalla.
      const details = document.createElement("details");
      const summary = document.createElement("summary");
      summary.className = "small muted";
      summary.textContent = group.title;
      details.append(summary, element);
      $("demo-folded").append(details);
    } else {
      $("demo-steps").append(element);
    }
  }

  // Un atajo por vez; recargar el mundo interrumpe cualquier cosa.
  let busy = false;
  async function run(step, status) {
    if (busy && !step.always) return;
    const started = Date.now();
    if (!step.always) {
      busy = true;
      for (const [other, element] of buttons) element.disabled = !other.always;
    }
    status.className = "demo-status";
    status.style.color = "var(--accent)";
    status.textContent = `${step.label}: en curso…`;
    try {
      const result = await step.run();
      status.style.color = "var(--ok)";
      status.textContent = `${result} · ${Math.round((Date.now() - started) / 1000)} s`;
    } catch (error) {
      status.style.color = "";
      status.className = "demo-status feedback";
      showError(status, error);
    } finally {
      if (!step.always) {
        busy = false;
        for (const element of buttons.values()) element.disabled = false;
      }
    }
  }

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const get = (path) => fetch(path, { signal: AbortSignal.timeout(2000) }).then((response) => response.json());

  // Espera a que test(estado, banco) dé algo verdadero, consultando a la URC.
  async function until(test, what, seconds) {
    const end = Date.now() + seconds * 1000;
    for (;;) {
      const [state, bench] = await Promise.all([get("/api/estado"), get("/api/banco")]);
      const value = await test(state, bench);
      if (value) return value;
      if (Date.now() > end) throw new Error(`No llegó a tiempo: ${what}`);
      await sleep(200);
    }
  }

  const still = (state) => state.connected && state.status && state.status.mode === "IDLE" && !state.jog
    && !state.segments.pending && state.segments.in_flight === null;
  // A un paso del destino, como AT_POINT de urc/playback.py: −60° no es una cantidad entera de pasos.
  const AT_POINT = [6, 6, 6, 1];
  const at = (state, units) => state.status.position.every((value, i) => Math.abs(value - units[i]) <= AT_POINT[i]);
  const units = (joints) => joints.map((value) => Math.round(value * 100));
  const mm = (value) => `${(value / 100).toFixed(2).replace(".", ",")} mm`;
  const degrees = (value) => `${(value / 100).toFixed(1).replace(".", ",").replace("-", "−")}°`;

  // Espera el fin del tramo en curso: llega a target o se frena (Stop, ERR).
  async function arrive(target, what) {
    return until((state) => {
      if (!still(state)) return null;
      if (at(state, target)) return state;
      if (state.tramo && state.tramo.cancelled) throw new Error(`Se frenó antes de llegar: ${state.tramo.cancelled}`);
      return null;
    }, what, 90);
  }

  async function ptp(joints, speed = 100) {
    await post("/api/ptp", { joints, speed, confirm: true });
    return arrive(units(joints), "fin del tramo PTP");
  }

  async function order(request, applied, what) {
    await post("/api/banco", request);
    return until((_, bench) => bench.connected && applied(bench), what, 5);
  }
  const obstacle = (value) => order({ obstaculo: value },
    (bench) => bench.obstacle && bench.obstacle.tipo === value.tipo, "obstáculo aplicado");
  const current = (motor, pct) => order({ falla: "F1", motor, corriente: pct },
    (bench) => bench.current_pct && bench.current_pct[motor - 1] === pct, `M${motor} al ${pct} %`);

  async function home() {
    await post("/api/enable");
    await until((state) => state.status && state.status.mode !== "OFF", "motores con corriente", 5);
    await post("/api/home");
    await until((state) => {
      const homing = state.homing;
      if (homing && homing.state.startsWith("abortado")) throw new Error(`Homing ${homing.state}`);
      return homing && homing.state === "terminado" && state.referenced && still(state) && at(state, REST);
    }, "fin del homing y vuelta al reposo", 240);
    return "Referenciado y en reposo";
  }

  async function play(file = null) {
    if (file) await post("/api/trayectoria/cargar", { file, discard: true });
    await post("/api/reproduccion/reproducir", { start: 0, speed: 100, loops: 1 });
    const player = await until(() => get("/api/reproduccion").then((p) => !PLAYING.includes(p.state) && p), "fin de la reproducción", 180);
    return player.message || player.state;
  }

  async function pot() {
    await ptp(SWEEP_START);
    await obstacle(POT);
    return "En el inicio del barrido, con la maceta";
  }

  async function sweep() {
    await post("/api/ptp", { joints: SWEEP_END, speed: SWEEP_SPEED, confirm: true });
    const state = await arrive(units(SWEEP_END), "fin del barrido");
    const bench = await get("/api/banco");
    const lost = (bench.lost_steps || []).map((steps, i) => `M${i + 1} ${steps}`).join(", ");
    return `J2 estimada ${degrees(state.status.position[1])} · simulada ${degrees(bench.simulated[1])}`
      + ` · pasos perdidos ${lost}. El firmware no se enteró`;
  }

  async function f1Prepare() {
    await ptp(F1_LOW);
    await order({ carga: LOAD_G }, (bench) => bench.load_g === LOAD_G, "carga aplicada");
    await current(4, F1_CURRENT);
    return "J4 en 60 mm con 5 kg y M4 al 50 %";
  }

  async function f1Up() {
    const state = await ptp(F1_HIGH);
    const bench = await get("/api/banco");
    return `Estimada ${mm(state.status.position[3])} · simulada ${mm(bench.simulated[3])}`;
  }

  async function f1Park() {
    await current(4, 100);
    await post("/api/park");
    const state = await arrive(REST, "fin del tramo al reposo");
    const lost = state.doubtful.map((item) => `EV LOST J${item.joint}: ${item.steps} pasos`).join(" · ");
    return lost ? `${lost} · referencia dudosa` : "Sin EV LOST: el Hall no vio pasos perdidos";
  }

  // Con referencia, sube J4 antes: sin corriente, se lo ve caer por su peso.
  async function f5() {
    const state = await get("/api/estado");
    if (state.referenced && still(state)) {
      await ptp([...state.status.position.slice(0, 3).map((value) => value / 100), F5_J4]);
    }
    const before = state.boots;
    await post("/api/banco", { falla: "F5" });
    await until((state) => state.boots > before && state.status && state.status.mode === "OFF", "BOOT de la UCI", 10);
    return "BOOT inesperado: sin corriente y sin referencia";
  }

  async function resetBench() {
    await obstacle({ tipo: "ninguno" });
    await order({ carga: 0 }, (bench) => bench.load_g === 0, "sin carga");
    for (const motor of [1, 2, 3, 4]) await current(motor, 100);
    for (const falla of ["F2", "F4"]) {
      await order({ falla, activa: false }, (bench) => bench.faults && !bench.faults[falla], `${falla} inactiva`);
    }
    for (const articulacion of [1, 2, 3, 4]) {
      await order({ falla: "F3", articulacion, estado: "libre" },
        (bench) => bench.faults && bench.faults.F3[articulacion - 1] === "libre", `Hall de J${articulacion} libre`);
    }
    return "Banco limpio";
  }

  async function reload() {
    await post("/api/banco", { recarga: true });
    await sleep(1500);
    await until((state, bench) => state.connected && state.status && bench.connected, "reconexión de Webots", 60);
    return "Mundo recargado: falta habilitar y hacer homing";
  }

  document.addEventListener("urc:estado", () => {
    if (panel.hidden || !urcState) return;
    // Seis líneas, las más nuevas abajo: entran sin barra de desplazamiento.
    const text = urcState.traffic.slice(-6).map((entry) => `${entry.direction} ${entry.line}`).join("\n");
    if ($("demo-traffic").textContent !== text) $("demo-traffic").textContent = text;
  });
  const toggle = () => { panel.hidden = location.hash !== "#demo"; };
  window.addEventListener("hashchange", toggle);
  toggle();
})();
