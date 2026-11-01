// Gestor de trayectorias (D29, D34). La trayectoria la guarda la URC; la
// página la muestra y pide cada cambio por /api/trayectoria/*. La
// reproducción va por /api/reproduccion/* y también la planifica la URC.
// Usa post, format, lastStatus y stopJog de index.html.
(() => {
  const panel = document.getElementById("trajectory");
  panel.innerHTML = `
    <h2>Trayectoria: <span id="tr-name"></span> <span class="badge warn" id="tr-dirty" hidden>cambios sin guardar</span></h2>
    <p class="muted"><kbd>Espacio</kbd> captura la posición estimada por pasos después del punto seleccionado (robot referenciado y quieto).
      <kbd>Retroceso</kbd> borra el seleccionado; después de capturar, es el último capturado. <kbd>Enter</kbd> termina y pide el nombre.
      Cada fila dice cómo se llega a ese punto: tipo de tramo, velocidad y espera.</p>
    <div class="row">
      <button id="tr-new">Nueva</button>
      <select id="tr-files" aria-label="Trayectorias guardadas"></select>
      <button id="tr-load">Cargar</button>
      <button id="tr-save">Guardar</button>
      <button id="tr-save-as">Guardar como…</button>
    </div>
    <table style="margin-top: 12px">
      <thead><tr><th>#</th><th>X (mm)</th><th>Y (mm)</th><th>Z (mm)</th><th>Rumbo</th><th>Codo</th>
        <th>Tramo</th><th>Vel. (%)</th><th>Espera (s)</th><th></th></tr></thead>
      <tbody id="tr-points"></tbody>
    </table>
    <p id="tr-empty" class="muted">Sin puntos: capturá con <kbd>Espacio</kbd> o escribí uno abajo.</p>
    <div class="row" style="margin-top: 12px">
      <button id="tr-capture">Capturar <kbd>Espacio</kbd></button>
      <button id="tr-overwrite">Sobrescribir con la pose actual</button>
      <button id="tr-go">Ir al punto…</button>
      <button id="tr-delete">Borrar <kbd>Retroceso</kbd></button>
    </div>
    <h2 style="margin-top: 18px">Reproducción</h2>
    <p class="muted">Antes de mover, la URC valida todos los tramos. El robot llega primero al punto de partida con el tramo 0,
      un PTP al 25 % × la velocidad global, salvo que ya esté ahí. Con loop, la vuelta del último punto al primero usa los
      parámetros del punto 1. La velocidad global no se guarda en el archivo. <kbd>Esc</kbd> frena todo.</p>
    <div class="row">
      <label>Velocidad global (%) <input id="pl-speed" type="number" min="10" max="100" step="10" value="100" style="width: 5em"></label>
      <label>Loop <select id="pl-loop"><option value="1">Sin loop</option><option value="n">N vueltas</option><option value="inf">Sin fin</option></select></label>
      <label id="pl-times-label" hidden>Vueltas <input id="pl-times" type="number" min="2" step="1" value="2" style="width: 5em"></label>
    </div>
    <div class="row" style="margin-top: 8px">
      <button id="pl-play">▶ Desde el principio</button>
      <button id="pl-play-selected">▶ Desde el seleccionado</button>
      <button id="pl-pause">Pausa</button>
      <button id="pl-resume">Reanudar</button>
      <button id="pl-stop">Stop <kbd>Esc</kbd></button>
    </div>
    <p id="pl-status" class="muted"></p>
    <div id="pl-feedback" class="feedback" role="status" aria-live="polite"></div>
    <h2 style="margin-top: 18px">Punto escrito</h2>
    <p class="muted">En XYZ, un punto nuevo usa el codo elegido; uno editado conserva el suyo (para cambiarlo, editá J1–J4).</p>
    <div class="row">
      <label><input type="radio" name="tr-kind" value="pose" checked> Punto de herramienta</label>
      <label><input type="radio" name="tr-kind" value="joints"> Articulaciones</label>
    </div>
    <div class="row fields" id="tr-pose">
      <label>X (mm) <input type="number" step="0.1" value="433"></label>
      <label>Y (mm) <input type="number" step="0.1" value="0"></label>
      <label>Z (mm) <input type="number" step="0.1" value="34.7"></label>
      <label>Rumbo (°) <input type="number" step="0.1" value="-20"></label>
      <label>Codo <select id="tr-elbow"><option value="-1">J2 negativo (preferido)</option><option value="1">J2 positivo</option></select></label>
    </div>
    <div class="row fields" id="tr-joints" hidden>
      <label>J1 (°) <input type="number" step="0.01" value="0"></label>
      <label>J2 (°) <input type="number" step="0.01" value="0"></label>
      <label>J3 (°) <input type="number" step="0.01" value="0"></label>
      <label>J4 (mm) <input type="number" step="0.01" value="120"></label>
    </div>
    <div class="row">
      <button id="tr-add">Agregar después del seleccionado</button>
      <button id="tr-apply">Aplicar al seleccionado</button>
    </div>
    <div id="tr-feedback" class="feedback" role="status" aria-live="polite"></div>
    <dialog id="tr-name-dialog">
      <form method="dialog">
        <h2>Guardar la trayectoria</h2>
        <label>Nombre <input type="text" id="tr-name-input" maxlength="60" required></label>
        <div class="row" style="margin-top: 12px">
          <button value="save">Guardar</button>
          <button value="cancel" formnovalidate>Cancelar</button>
        </div>
      </form>
    </dialog>`;

  const $ = (id) => document.getElementById(id);
  const ELBOWS = { "-1": "J2 −", "0": "estirado", "1": "J2 +" };
  let trajectory = { points: [], dirty: false }, selected = null, playback = { state: "inactiva", current: null };

  const feedback = (error) => { $("tr-feedback").textContent = error ? error.message : ""; };

  // Un 409 es un pedido que descartaría trabajo: se pregunta y se repite con el permiso.
  async function send(path, body = {}, allow = null) {
    const response = await fetch(`/api/trayectoria/${path}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const data = await response.json();
    if (response.status === 409 && allow && confirm(data.error)) return send(path, { ...body, [allow]: true });
    if (response.status === 409 && allow) return null;
    if (!response.ok) throw new Error(data.error);
    return data;
  }

  async function act(path, body, allow) {
    try {
      const data = await send(path, body, allow);
      if (data) show(data);
      feedback(null);
      return data;
    } catch (error) {
      feedback(error);
      return null;
    }
  }

  function show(data) {
    trajectory = data;
    selected = data.selected;
    $("tr-name").textContent = data.name || "sin nombre";
    $("tr-dirty").hidden = !data.dirty;
    $("tr-empty").hidden = data.points.length > 0;
    const body = $("tr-points");
    body.replaceChildren(...data.points.map(row));
    paint();
  }

  // El punto al que va el tramo en ejecución, según el estado S de la UCI.
  function paint() {
    const current = playback.current;
    for (const tr of $("tr-points").children) {
      const index = Number(tr.dataset.index);
      const running = current && current.point === index;
      tr.style.background = running ? "#ffe2a8" : index === selected ? "#d9eef0" : "";
      tr.style.fontWeight = running ? "700" : "";
    }
  }

  function row(point, index) {
    const tr = document.createElement("tr");
    tr.dataset.index = index;
    const t = point.tool;
    // Solo el número se arrastra: en una fila arrastrable los campos no se editan bien.
    tr.innerHTML = `<td draggable="true" title="Arrastrar para reordenar" style="cursor: grab">⠿ ${index + 1}</td><td>${t.x.toFixed(2)}</td><td>${t.y.toFixed(2)}</td><td>${t.z.toFixed(2)}</td>` +
      `<td>${t.heading.toFixed(2)}°</td><td>${ELBOWS[point.elbow]}</td>` +
      `<td><select data-field="kind"><option>LIN</option><option>PTP</option></select></td>` +
      `<td><input data-field="speed" type="number" min="1" max="100" step="1" value="${point.speed}" style="width: 4.5em"></td>` +
      `<td><input data-field="wait" type="number" min="0" max="600" step="0.1" value="${point.wait}" style="width: 4.5em"></td>` +
      `<td><button data-move="-1" title="Subir">↑</button> <button data-move="1" title="Bajar">↓</button></td>`;
    tr.querySelector("select").value = point.kind;
    return tr;
  }

  // Al seleccionar, los campos del punto escrito muestran su pose.
  function fill(point) {
    const pose = $("tr-pose").querySelectorAll("input");
    [point.tool.x, point.tool.y, point.tool.z, point.tool.heading].forEach((v, i) => { pose[i].value = v; });
    $("tr-joints").querySelectorAll("input").forEach((input, i) => { input.value = (point.joints[i] / 100).toFixed(2); });
  }

  function select(index) {
    show({ ...trajectory, selected: index });
    fill(trajectory.points[index]);
  }

  const points = $("tr-points");
  points.addEventListener("click", (event) => {
    const tr = event.target.closest("tr");
    if (!tr) return;
    const index = Number(tr.dataset.index);
    const move = event.target.closest("[data-move]");
    if (move) {
      const to = index + Number(move.dataset.move);
      if (to >= 0 && to < trajectory.points.length) act("mover", { index, to });
    } else if (!event.target.closest("input, select")) {
      select(index);
    }
  });
  points.addEventListener("change", (event) => {
    const field = event.target.dataset.field;
    if (!field) return;
    const index = Number(event.target.closest("tr").dataset.index);
    const value = field === "kind" ? event.target.value : Number(event.target.value);
    act("editar", { index, [field]: value }).then((data) => { if (!data) show(trajectory); });
  });
  // Reordenar arrastrando una fila.
  let dragged = null;
  points.addEventListener("dragstart", (event) => {
    dragged = Number(event.target.closest("tr").dataset.index);
    event.dataTransfer.setData("text/plain", String(dragged));  // Firefox no arrastra sin datos
  });
  points.addEventListener("dragover", (event) => event.preventDefault());
  points.addEventListener("drop", (event) => {
    event.preventDefault();
    const tr = event.target.closest("tr");
    if (tr && dragged !== null && Number(tr.dataset.index) !== dragged) {
      act("mover", { index: dragged, to: Number(tr.dataset.index) });
    }
    dragged = null;
  });

  const after = () => (selected === null ? trajectory.points.length - 1 : selected);
  const needSelected = () => {
    if (selected === null) throw new Error("Seleccioná un punto de la lista");
    return selected;
  };
  const guarded = (action) => () => { try { return action(); } catch (error) { feedback(error); } };

  const capture = () => act("capturar", { after: after() });
  const remove = () => {
    if (!trajectory.points.length) return;
    act("borrar", { index: selected === null ? trajectory.points.length - 1 : selected });
  };

  function written() {
    const inputs = [...document.querySelectorAll(`#tr-${kind()} input`)];
    const numbers = inputs.map((input) => {
      if (input.value.trim() === "") throw new Error(`Falta ${input.parentElement.textContent.trim()}`);
      return Number(input.value);
    });
    if (kind() === "joints") return { joints: numbers };
    const [x, y, z, heading] = numbers;
    return { pose: { x, y, z, heading } };
  }
  const kind = () => document.querySelector("input[name=tr-kind]:checked").value;
  for (const radio of document.querySelectorAll("input[name=tr-kind]")) {
    radio.addEventListener("change", () => {
      $("tr-pose").hidden = kind() !== "pose";
      $("tr-joints").hidden = kind() !== "joints";
    });
  }

  $("tr-capture").addEventListener("click", capture);
  $("tr-delete").addEventListener("click", remove);
  $("tr-overwrite").addEventListener("click", guarded(() => {
    const index = needSelected();
    if (confirm(`¿Sobrescribir el punto ${index + 1} con la pose actual?`)) act("sobrescribir", { index });
  }));
  $("tr-add").addEventListener("click", guarded(() => {
    const request = written();
    if (request.pose) request.pose.elbow = Number($("tr-elbow").value);
    act("punto", { ...request, after: after() });
  }));
  $("tr-apply").addEventListener("click", guarded(() => act("editar", { index: needSelected(), ...written() })));
  // «Ir al punto»: primero planifica y muestra la duración; después mueve (D29).
  $("tr-go").addEventListener("click", guarded(async () => {
    const index = needSelected();
    stopJog();
    try {
      const plan = await send("ir", { index });
      if (plan.segments === 0) {
        feedback(new Error("El robot ya está en ese punto."));
        return;
      }
      const target = plan.target.map((value, joint) => format(joint, value)).join(", ");
      if (!confirm(`PTP al punto ${index + 1} (${target}) al ${plan.speed * 100} %: ${plan.duration_s.toFixed(2)} s. ¿Mover el robot?`)) return;
      await send("ir", { index, confirm: true, target: plan.target });
      feedback(null);
    } catch (error) {
      feedback(error);
    }
  }));

  async function files() {
    try {
      const list = (await (await fetch("/api/trayectorias")).json()).files;
      const choice = $("tr-files").value;
      $("tr-files").replaceChildren(...list.map((file) => new Option(file, file)));
      if (list.includes(choice)) $("tr-files").value = choice;
      else if (trajectory.file) $("tr-files").value = trajectory.file;
    } catch (error) {
      feedback(error);
    }
  }

  // Enter y «Guardar como» piden el nombre; «Guardar» usa el del archivo abierto.
  const dialog = $("tr-name-dialog");
  function askName() {
    if (!trajectory.points.length) {
      feedback(new Error("La trayectoria no tiene puntos todavía"));
      return;
    }
    stopJog();
    $("tr-name-input").value = trajectory.name || "";
    dialog.showModal();
  }
  dialog.addEventListener("close", async () => {
    if (dialog.returnValue !== "save") return;
    if (await act("guardar", { name: $("tr-name-input").value }, "overwrite")) files();
  });
  $("tr-save").addEventListener("click", () => (trajectory.file ? act("guardar", {}) : askName()));
  $("tr-save-as").addEventListener("click", askName);
  $("tr-new").addEventListener("click", () => act("nueva", {}, "discard"));
  $("tr-load").addEventListener("click", () => {
    if ($("tr-files").value) act("cargar", { file: $("tr-files").value }, "discard");
  });
  $("tr-files").addEventListener("focus", files);
  window.addEventListener("beforeunload", (event) => {
    if (trajectory.dirty) event.preventDefault();
  });

  // Teclas del gestor (D12). Escribiendo o con un diálogo abierto no actúan.
  document.addEventListener("keydown", (event) => {
    if (event.repeat || event.ctrlKey || event.metaKey || event.altKey) return;
    if (!["Space", "Backspace", "Enter"].includes(event.code)) return;
    const typing = event.target.closest && event.target.closest("input:not([type=checkbox]):not([type=radio]), select, textarea");
    if (typing || document.querySelector("dialog[open]")) return;
    event.preventDefault();
    // Un botón con el foco no se activa además con Espacio o Enter.
    if (document.activeElement instanceof HTMLButtonElement) document.activeElement.blur();
    if (event.code === "Space") capture();
    else if (event.code === "Backspace") remove();
    else askName();
  });

  // --- Reproducción (D29, D32, D33) ---
  const ACTIVE = ["reproduciendo", "pausando", "pausada"];
  const plFeedback = (error) => { $("pl-feedback").textContent = error ? error.message : ""; };
  const seconds = (value) => `${value.toFixed(2)} s`;

  function describe(state) {
    const parts = [state.message];
    const approach = state.approach;
    if (approach && state.state !== "inactiva") {
      parts.push(approach.skipped ? `Tramo 0 omitido: el robot ya estaba en el punto ${approach.point + 1}`
        : `Tramo 0, aproximación PTP al punto ${approach.point + 1}: ${seconds(approach.duration_s)}`);
      parts.push(state.duration_s === null ? "loop sin fin" : `duración planificada ${seconds(state.duration_s)}`);
    }
    const current = state.current;
    if (current) {
      const loop = state.loops === 1 ? "" : ` · vuelta ${current.cycle}${state.loops ? ` de ${state.loops}` : ""}`;
      const what = current.approach ? "tramo 0, aproximación PTP"
        : current.label === "vuelta" ? `vuelta al punto 1 (${current.kind})` : `tramo ${current.label} (${current.kind})`;
      parts.push(`${current.waiting ? `Esperando en el punto ${current.point + 1}` : `En ejecución: ${what}`}${loop}`);
    }
    return parts.join(" · ");
  }

  function showPlayback(state) {
    playback = state;
    const active = ACTIVE.includes(state.state);
    $("pl-status").textContent = describe(state);
    $("pl-play").disabled = $("pl-play-selected").disabled = active || state.state === "validando";
    $("pl-pause").disabled = state.state !== "reproduciendo";
    $("pl-resume").disabled = state.state !== "pausada";
    $("pl-stop").disabled = !active;
    paint();
  }

  function loops() {
    const choice = $("pl-loop").value;
    if (choice === "inf") return null;
    if (choice === "1") return 1;
    const times = Number($("pl-times").value);
    if (!Number.isInteger(times) || times < 2) throw new Error("Las vueltas del loop son un entero de 2 o más");
    return times;
  }
  $("pl-loop").addEventListener("change", () => { $("pl-times-label").hidden = $("pl-loop").value !== "n"; });

  async function play(start) {
    stopJog();
    try {
      const body = { start, speed: Number($("pl-speed").value), loops: loops() };
      $("pl-status").textContent = "Validando la trayectoria completa…";
      showPlayback(await post("/api/reproduccion/reproducir", body));
      plFeedback(null);
    } catch (error) {
      plFeedback(error);
      refreshPlayback();
    }
  }
  const command = (path) => () => post(`/api/reproduccion/${path}`).then((state) => { showPlayback(state); plFeedback(null); }, plFeedback);

  $("pl-play").addEventListener("click", () => play(0));
  $("pl-play-selected").addEventListener("click", guarded(() => play(needSelected())));
  $("pl-pause").addEventListener("click", command("pausa"));
  $("pl-resume").addEventListener("click", command("reanudar"));
  $("pl-stop").addEventListener("click", command("stop"));

  async function refreshPlayback() {
    try {
      showPlayback(await (await fetch("/api/reproduccion")).json());
    } catch (error) {
      // La URC no responde: lo informa la cabecera de la página.
    }
  }

  fetch("/api/trayectoria").then((response) => response.json()).then(show, feedback);
  files();
  refreshPlayback();
  setInterval(refreshPlayback, 200);
})();
