from fastapi.responses import HTMLResponse


def render_service_ui(service: str, title: str) -> HTMLResponse:
    html = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>__TITLE__</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    .glass { background: rgba(15,23,42,.68); backdrop-filter: blur(10px); }
  </style>
</head>
<body class="min-h-screen bg-[radial-gradient(circle_at_10%_10%,#164e63_0%,transparent_35%),radial-gradient(circle_at_95%_0%,#9a3412_0%,transparent_30%),linear-gradient(165deg,#020617,#0b1120,#111827)] text-slate-100">
  <div class="mx-auto max-w-7xl p-4 md:p-8">
    <header class="glass mb-6 rounded-3xl border border-slate-700/80 p-6">
      <h1 class="text-3xl font-black tracking-tight md:text-4xl">__TITLE__ Workspace</h1>
      <p class="mt-2 text-slate-300">Panel visual del servicio <b>__SERVICE__</b> con autenticación y operaciones.</p>
      <p class="mt-1 text-sm text-slate-400">Vista centralizada recomendada: <a class="text-cyan-300 underline" href="https://shopnow-gateway.onrender.com/ui" target="_blank" rel="noopener">https://shopnow-gateway.onrender.com/ui</a></p>
    </header>

    <div class="grid gap-6 lg:grid-cols-[280px_1fr]">
      <aside class="glass rounded-3xl border border-slate-700/80 p-5">
        <h2 class="mb-3 text-lg font-bold text-cyan-300">Acceso</h2>
        <label class="mb-2 block text-xs uppercase tracking-wide text-slate-400">Usuario</label>
        <input id="username" value="admin" class="mb-3 w-full rounded-xl border border-slate-600 bg-slate-800 px-3 py-2" />
        <label class="mb-2 block text-xs uppercase tracking-wide text-slate-400">Contrasena</label>
        <input id="password" value="admin123" type="password" class="mb-4 w-full rounded-xl border border-slate-600 bg-slate-800 px-3 py-2" />
        <button onclick="login()" class="w-full rounded-xl bg-cyan-400 px-4 py-2 font-bold text-slate-950">Iniciar sesion</button>
        <p id="authMsg" class="mt-3 text-sm text-emerald-300"></p>

        <hr class="my-4 border-slate-700" />
        <div class="space-y-2 text-sm">
          <p class="text-slate-300">Estado: <span id="stateBadge" class="rounded-full bg-slate-700 px-2 py-1 text-xs">sin sesion</span></p>
          <p class="text-slate-300">Registros: <span id="countBadge" class="font-bold text-amber-300">0</span></p>
        </div>
        <div class="mt-3 rounded-xl border border-slate-700 bg-slate-900 p-2">
          <p class="text-xs uppercase tracking-wide text-amber-300">Token beta</p>
          <pre id="tokenBox" class="mt-1 max-h-28 overflow-auto text-[11px] leading-4 text-slate-300">(sin token)</pre>
        </div>
      </aside>

      <main class="space-y-4">
        <section id="actions" class="grid gap-4 xl:grid-cols-2"></section>

        <section class="glass rounded-3xl border border-slate-700/80 p-5">
          <div class="mb-4 flex items-center justify-between">
            <h2 class="text-xl font-bold text-cyan-300">Datos</h2>
            <button onclick="loadList()" class="rounded-xl bg-sky-400 px-4 py-2 text-sm font-bold text-slate-950">Refrescar</button>
          </div>
          <div class="overflow-auto rounded-2xl border border-slate-700">
            <table id="table" class="min-w-full text-sm"></table>
          </div>
        </section>

        <section class="glass rounded-3xl border border-slate-700/80 p-5">
          <h2 class="mb-2 text-xl font-bold text-cyan-300">Respuesta API</h2>
          <pre id="output" class="max-h-72 overflow-auto rounded-xl bg-slate-900 p-3 text-xs text-slate-200"></pre>
        </section>
      </main>
    </div>
  </div>

<script>
let token = "";
const service = "__SERVICE__";

const cfg = {
  clientes: {
    list: ["GET", "/clientes"],
    blocks: [
      { title: "Nuevo cliente", tone: "cyan", method: "POST", path: "/clientes", fields: ["nombre", "correo", "direccion", "telefono", "activo:boolean"] },
      { title: "Editar cliente", tone: "amber", method: "PATCH", path: "/clientes/{id}", fields: ["id:number", "nombre?", "correo?", "direccion?", "telefono?", "activo:boolean"] },
      { title: "Baja cliente", tone: "rose", method: "DELETE", path: "/clientes/{id}", fields: ["id:number"] }
    ]
  },
  productos: {
    list: ["GET", "/productos"],
    blocks: [
      { title: "Nuevo producto", tone: "cyan", method: "POST", path: "/productos", fields: ["descripcion", "precio:number", "activo:boolean"] },
      { title: "Editar producto", tone: "amber", method: "PATCH", path: "/productos/{id}", fields: ["id:number", "descripcion?", "precio?:number", "activo:boolean"] },
      { title: "Eliminar producto", tone: "rose", method: "DELETE", path: "/productos/{id}", fields: ["id:number"] }
    ]
  },
  pedidos: {
    list: ["GET", "/pedidos"],
    blocks: [
      { title: "Crear pedido", tone: "cyan", method: "POST", path: "/pedidos", fields: ["id_cliente:number", "id_producto:number", "cantidad:number"] }
    ]
  },
  inventario: {
    list: ["GET", "/inventario"],
    blocks: [
      { title: "Registrar inventario", tone: "cyan", method: "POST", path: "/inventario", fields: ["id_producto:number", "cantidad:number"] },
      { title: "Agregar stock", tone: "emerald", method: "POST", path: "/inventario/agregar", fields: ["id_producto:number", "cantidad:number"] },
      { title: "Descontar stock", tone: "rose", method: "POST", path: "/inventario/descontar", fields: ["id_producto:number", "cantidad:number"] }
    ]
  }
};

const toneMap = {
  cyan: "border-cyan-700/60 text-cyan-300",
  amber: "border-amber-700/60 text-amber-300",
  rose: "border-rose-700/60 text-rose-300",
  emerald: "border-emerald-700/60 text-emerald-300"
};

function fieldInput(name, prefix) {
  const safe = name.replace(/[^a-zA-Z0-9_?]/g, "");
  return `<label class=\"block\"><span class=\"mb-1 block text-xs uppercase tracking-wide text-slate-400\">${name}</span><input id=\"${prefix}_${safe}\" class=\"w-full rounded-xl border border-slate-600 bg-slate-800 px-3 py-2 text-sm\" /></label>`;
}

function renderForms() {
  const blocks = cfg[service].blocks;
  const root = document.getElementById("actions");
  root.innerHTML = blocks.map((b, idx) => {
    const pid = `b${idx}`;
    return `
      <article class=\"glass rounded-3xl border ${toneMap[b.tone] || toneMap.cyan} p-5\">
        <div class=\"mb-3 flex items-center justify-between\">
          <h3 class=\"text-lg font-bold\">${b.title}</h3>
          <span class=\"rounded-full bg-slate-800 px-2 py-1 text-xs\">${b.method}</span>
        </div>
        <div class=\"grid gap-3 md:grid-cols-2\">${b.fields.map((f) => fieldInput(f, pid)).join("")}</div>
        <button onclick=\"runBlock(${idx})\" class=\"mt-4 rounded-xl bg-cyan-400 px-4 py-2 text-sm font-bold text-slate-950\">Ejecutar</button>
      </article>
    `;
  }).join("");
}

function cast(spec, value) {
  if (spec.includes(":number")) return Number(value);
  if (spec.includes(":boolean")) return String(value).toLowerCase() === "true";
  return value;
}

function pretty(value) {
  if (value == null) return "";
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value);
      return JSON.stringify(parsed, null, 2);
    } catch {
      return value;
    }
  }
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}

function readField(blockIndex, spec) {
  const safe = spec.replace(/[^a-zA-Z0-9_?]/g, "");
  const id = `b${blockIndex}_${safe}`;
  return document.getElementById(id)?.value ?? "";
}

async function api(path, method, body) {
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  if (!(body instanceof URLSearchParams)) headers["Content-Type"] = "application/json";
  const response = await fetch(path, {
    method,
    headers,
    body: body ? (body instanceof URLSearchParams ? body : JSON.stringify(body)) : undefined
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || data.mensaje || `Error HTTP ${response.status}`);
  return data;
}

function renderTable(rows) {
  const table = document.getElementById("table");
  if (!Array.isArray(rows) || rows.length === 0) {
    table.innerHTML = `<tbody><tr><td class=\"px-4 py-6 text-slate-300\">Sin registros</td></tr></tbody>`;
    document.getElementById("countBadge").textContent = "0";
    return;
  }

  const columns = Object.keys(rows[0]);
  const thead = `<thead class=\"bg-slate-900\"><tr>${columns.map((c) => `<th class=\"px-3 py-2 text-left text-xs font-bold uppercase tracking-wide text-sky-300\">${c}</th>`).join("")}</tr></thead>`;
  const tbody = `<tbody>${rows.map((row) => `<tr class=\"border-t border-slate-700\">${columns.map((c) => `<td class=\"px-3 py-2 text-slate-200 whitespace-pre-wrap\">${pretty(row[c])}</td>`).join("")}</tr>`).join("")}</tbody>`;
  table.innerHTML = thead + tbody;
  document.getElementById("countBadge").textContent = String(rows.length);
}

async function login() {
  const u = document.getElementById("username").value;
  const p = document.getElementById("password").value;
  try {
    const form = new URLSearchParams();
    form.append("username", u);
    form.append("password", p);
    const data = await api("/token", "POST", form);
    token = data.access_token;
    document.getElementById("authMsg").textContent = "Sesion iniciada";
    document.getElementById("tokenBox").textContent = token || "(sin token)";
    document.getElementById("stateBadge").textContent = "autenticado";
    document.getElementById("stateBadge").className = "rounded-full bg-emerald-700/50 px-2 py-1 text-xs";
    loadList();
  } catch (e) {
    document.getElementById("authMsg").textContent = e.message;
  }
}

async function runBlock(index) {
  const b = cfg[service].blocks[index];
  try {
    let path = b.path;
    const body = {};

    for (const spec of b.fields) {
      const raw = readField(index, spec);
      const optional = spec.includes("?");
      const key = spec.replace("?", "").split(":")[0];

      if (key === "id") {
        path = path.replace("{id}", raw);
        continue;
      }
      if (!raw && optional) continue;
      body[key] = cast(spec, raw);
    }

    const data = await api(path, b.method, b.method === "DELETE" ? null : body);
    document.getElementById("output").textContent = pretty(data);
    loadList();
  } catch (e) {
    document.getElementById("output").textContent = e.message;
  }
}

async function loadList() {
  if (!token) return;
  try {
    const [method, path] = cfg[service].list;
    const data = await api(path, method);
    renderTable(data);
    document.getElementById("output").textContent = pretty(data);
  } catch (e) {
    document.getElementById("output").textContent = e.message;
  }
}

renderForms();
</script>
</body>
</html>
"""
    html = html.replace("__SERVICE__", service).replace("__TITLE__", title)
    return HTMLResponse(content=html)
