// Gestor de trayectorias (D29, D34). La trayectoria la guarda la URC; la
// página la muestra y pide cada cambio por /api/trayectoria/*. La
// reproducción va por /api/reproduccion/* y también la planifica la URC.
// Usa post, format, copyHere, stopJog, missing, ask y pollSoon de index.html,
// y deja el estado de la reproducción en urcPlayback para la barra de estado.
(() => {
  const panel = document.getElementById("trajectory");
  const ICON_GRIP = '<svg viewBox="0 0 12 12" aria-hidden="true"><circle cx="4" cy="2.5" r="1.2" fill="currentColor"/><circle cx="8" cy="2.5" r="1.2" fill="currentColor"/><circle cx="4" cy="6" r="1.2" fill="currentColor"/><circle cx="8" cy="6" r="1.2" fill="currentColor"/><circle cx="4" cy="9.5" r="1.2" fill="currentColor"/><circle cx="8" cy="9.5" r="1.2" fill="currentColor"/></svg>';
  const ICON_UP = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 10l4.5-4.5 4.5 4.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  const ICON_DOWN = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 6l4.5 4.5L12.5 6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';

  panel.innerHTML = `
    <div class="card-head">
      <h2>Trayectoria</h2>
      <span class="badge" id="tr-name"></span>
      <span class="badge warn" id="tr-dirty" hidden>cambios sin guardar</span>
      <span class="grow"></span>
      <button id="tr-new">Nueva</button>
      <select id="tr-files" aria-label="Trayectorias guardadas"></select>
      <button id="tr-load">Cargar</button>
      <button id="tr-save">Guardar</button>
      <button id="tr-save-as">Guardar como…</button>
    </div>
    <div class="scroll"><table>
      <thead><tr><th>#</th><th>X (mm)</th><th>Y (mm)</th><th>Z (mm)</th><th>Rumbo</th><th>Codo</th>
        <th>Tramo</th><th>Vel. (%)</th><th>Espera (s)</th><th></th></tr></thead>
      <tbody id="tr-points"></tbody>
    </table></div>
    <p id="tr-empty" class="note" style="margin-top: 8px">Sin puntos. Llevá el robot con el jog y capturá con <kbd>Espacio</kbd>, o escribí un punto más abajo.</p>
    <div class="row" style="margin-top: 12px">
      <button id="tr-capture" class="primary" data-needs="referencia">Capturar <kbd>Espacio</kbd></button>
      <button id="tr-overwrite" data-needs="referencia">Sobrescribir con la pose actual</button>
      <button id="tr-go" data-needs="referencia">Ir al punto…</button>
      <span class="sep"></span>
      <button id="tr-delete" class="danger">Borrar <kbd>Retroceso</kbd></button>
    </div>
    <p class="blocked" data-blocked="referencia" data-what="Capturar, sobrescribir e ir al punto" hidden></p>
    <div id="tr-feedback" class="feedback" role="status" aria-live="polite"></div>
    <details class="help" id="tr-written">
      <summary>Escribir un punto</summary>
      <div class="row" style="margin-top: 10px">
        <div class="seg" role="group" aria-label="Cómo se escribe el punto">
          <label><input type="radio" name="tr-kind" value="pose" checked> Punto de herramienta</label>
          <label><input type="radio" name="tr-kind" value="joints"> Articulaciones</label>
        </div>
        <button id="tr-here" type="button">Copiar la pose actual</button>
      </div>
      <div class="row fields" id="tr-pose" style="margin-top: 10px">
        <label class="field">X (mm) <input type="number" step="0.1" value="433"></label>
        <label class="field">Y (mm) <input type="number" step="0.1" value="0"></label>
        <label class="field">Z (mm) <input type="number" step="0.1" value="34.7"></label>
        <label class="field">Rumbo (°) <input type="number" step="0.1" value="-20"></label>
      </div>
      <div class="row fields" id="tr-joints" style="margin-top: 10px" hidden>
        <label class="field">J1 (°) <input type="number" step="0.01" value="0"></label>
        <label class="field">J2 (°) <input type="number" step="0.01" value="0"></label>
        <label class="field">J3 (°) <input type="number" step="0.01" value="0"></label>
        <label class="field">J4 (mm) <input type="number" step="0.01" value="120"></label>
      </div>
      <div class="row" style="margin-top: 10px">
        <button id="tr-add">Agregar después del seleccionado</button>
        <button id="tr-apply">Aplicar al seleccionado</button>
      </div>
      <p>El punto se guarda como X, Y, Z y rumbo, también si se escribe en J1–J4. El codo no se elige: al reproducir, cada punto mantiene el del anterior mientras llegue; la columna Codo dice cuál toma.</p>
    </details>
    <details class="help">
      <summary>Cómo funciona</summary>
      <p><kbd>Espacio</kbd> captura la posición estimada por pasos después del punto seleccionado (robot referenciado y quieto). <kbd>Retroceso</kbd> borra el seleccionado; después de capturar, es el último capturado. <kbd>Enter</kbd> termina y pide el nombre.</p>
      <p>Cada fila dice cómo se llega a ese punto: tipo de tramo (LIN, recta del punto de herramienta; PTP, las articulaciones a la vez), velocidad y espera al llegar. Las filas se reordenan con las flechas o arrastrando el número.</p>
    </details>
    <dialog id="tr-name-dialog">
      <form method="dialog">
        <h2>Guardar la trayectoria</h2>
        <label class="field" style="display: flex; margin-top: 10px">Nombre <input type="text" id="tr-name-input" maxlength="60" required></label>
        <div class="row">
          <button value="cancel" formnovalidate>Cancelar</button>
          <button value="save" class="primary">Guardar</button>
        </div>
      </form>
    </dialog>`;

  document.getElementById("playback").innerHTML = `
    <div class="card-head">
      <h2>Reproducción</h2>
      <span class="grow"></span>
      <label class="field">Velocidad global (%) <input id="pl-speed" type="number" min="10" max="100" step="10" value="100" style="width: 5.5em"></label>
      <label class="field">Loop <select id="pl-loop"><option value="1">Sin loop</option><option value="n">N vueltas</option><option value="inf">Sin fin</option></select></label>
      <label class="field" id="pl-times-label" hidden>Vueltas <input id="pl-times" type="number" min="2" step="1" value="2" style="width: 5em"></label>
    </div>
    <div class="row">
      <button id="pl-play" class="primary">▶ Desde el principio</button>
      <button id="pl-play-selected">▶ Desde el seleccionado</button>
      <span class="sep"></span>
      <button id="pl-pause">Pausa</button>
      <button id="pl-resume">Reanudar</button>
      <button id="pl-stop" class="danger">Stop <kbd>Esc</kbd></button>
    </div>
    <p id="pl-blocked" class="blocked" hidden></p>
    <p id="pl-status" class="status-line"></p>
    <div id="pl-feedback" class="feedback" role="status" aria-live="polite"></div>
    <details class="help">
      <summary>Cómo funciona</summary>
      <p>Antes de mover, la URC valida todos los tramos. El robot llega primero al punto de partida con el tramo 0, un PTP al 25 % × la velocidad global, salvo que ya esté ahí. Con loop, la vuelta del último punto al primero usa los parámetros del punto 1. La velocidad global no se guarda en el archivo. <kbd>Esc</kbd> frena todo.</p>
    </details>`;

  const $ = (id) => document.getElementById(id);
  const ELBOWS = { "-1": "J2 −", "0": "estirado", "1": "J2 +" };
  let trajectory = { points: [], dirty: false }, selected = null, playback = { state: "inactiva", current: null };

  const feedback = (error) => showError($("tr-feedback"), error);

  // Un 409 es un pedido que descartaría trabajo: se pregunta y se repite con el permiso.
  async function send(path, body = {}, allow = null) {
    const response = await fetch(`/api/trayectoria/${path}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const data = await response.json();
    if (response.status === 409 && allow) {
      const ok = await ask(data.error, { title: "Hay trabajo que se perdería",
        confirm: allow === "discard" ? "Descartar los cambios" : "Reemplazar", danger: true });
      return ok ? send(path, { ...body, [allow]: true }) : null;
    }
    if (!response.ok) {
      pollSoon();  // el aviso del rechazo sale del registro de eventos
      throw requestError(data);
    }
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
      tr.classList.toggle("running", Boolean(current && current.point === index));
      tr.classList.toggle("selected", index === selected);
    }
  }

  function row(point, index) {
    const tr = document.createElement("tr");
    tr.dataset.index = index;
    const t = point.tool;
    // Solo el número se arrastra: en una fila arrastrable los campos no se editan bien.
    tr.innerHTML = `<td><span class="grip" draggable="true" title="Arrastrar para reordenar">${ICON_GRIP}<strong>${index + 1}</strong></span></td>` +
      `<td>${t.x.toFixed(2)}</td><td>${t.y.toFixed(2)}</td><td>${t.z.toFixed(2)}</td>` +
      `<td>${t.heading.toFixed(2)}°</td><td>${ELBOWS[point.elbow]}</td>` +
      `<td><select data-field="kind" aria-label="Tipo de tramo"><option>LIN</option><option>PTP</option></select></td>` +
      `<td><input data-field="speed" type="number" min="1" max="100" step="1" value="${point.speed}" aria-label="Velocidad"></td>` +
      `<td><input data-field="wait" type="number" min="0" max="600" step="0.1" value="${point.wait}" aria-label="Espera"></td>` +
      `<td><span class="moves"><button class="quiet" data-move="-1" title="Subir" aria-label="Subir">${ICON_UP}</button><button class="quiet" data-move="1" title="Bajar" aria-label="Bajar">${ICON_DOWN}</button></span></td>`;
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
  // Un error al preparar la orden, sincrónico o de una promesa, va a la línea de resultado.
  const guarded = (action) => () => {
    try {
      const result = action();
      if (result && typeof result.catch === "function") result.catch(feedback);
    } catch (error) {
      feedback(error);
    }
  };

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

  $("tr-here").addEventListener("click", guarded(() => {
    const clipped = copyHere("tr", kind());
    feedback(clipped ? new Error(clipped) : null);
  }));
  $("tr-capture").addEventListener("click", capture);
  $("tr-delete").addEventListener("click", remove);
  $("tr-overwrite").addEventListener("click", guarded(async () => {
    const index = needSelected();
    if (await ask(`El punto ${index + 1} toma la posición estimada actual del robot.`,
      { title: `¿Sobrescribir el punto ${index + 1}?`, confirm: "Sobrescribir" })) act("sobrescribir", { index });
  }));
  $("tr-add").addEventListener("click", guarded(() => {
    act("punto", { ...written(), after: after() });
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
      const ok = await ask(`PTP al punto ${index + 1} (${target}) al ${plan.speed * 100} %. Tarda ${plan.duration_s.toFixed(2)} s.`,
        { title: "¿Mover el robot?", confirm: "Mover" });
      if (!ok) return;
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
  const plFeedback = (error) => showError($("pl-feedback"), error);
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
    playback = urcPlayback = state;
    const active = ACTIVE.includes(state.state);
    $("pl-status").textContent = describe(state);
    // Sin referencia, con la referencia dudosa (D68) o sin puntos, reproducir
    // queda bloqueado y dice por qué (D78). La URC igual lo verifica.
    const blocked = active || state.state === "validando" ? null
      : missing("seguro") || (trajectory.points.length ? null : "la trayectoria no tiene puntos");
    $("pl-blocked").hidden = !blocked;
    $("pl-blocked").textContent = blocked ? `Reproducir bloqueado: ${lower(blocked)}.` : "";
    $("pl-play").title = $("pl-play-selected").title = blocked || "";
    $("pl-play").disabled = $("pl-play-selected").disabled = active || state.state === "validando" || Boolean(blocked);
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
