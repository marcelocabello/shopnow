const { useEffect, useMemo, useState } = React;

const SERVICES = {
  clientes: {
    label: "Clientes",
    listPath: "/clientes",
    createPath: "/clientes",
    updatePath: (id) => `/clientes/${id}`,
    deletePath: (id) => `/clientes/${id}`,
  },
  productos: {
    label: "Productos",
    listPath: "/productos",
    createPath: "/productos",
    updatePath: (id) => `/productos/${id}`,
    deletePath: (id) => `/productos/${id}`,
  },
  pedidos: {
    label: "Pedidos",
    listPath: "/pedidos",
    createPath: "/pedidos",
  },
  inventario: {
    label: "Inventario",
    listPath: "/inventario",
    createPath: "/inventario",
    addPath: "/inventario/agregar",
  },
};

const MAIN_TABS = ["general", "clientes", "productos", "pedidos", "inventario"];
const SERVICE_TABS = ["clientes", "productos", "pedidos", "inventario"];
const AUTO_REFRESH_MS = 4000;

async function apiFetch(path, { method = "GET", token, body, form = false } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (!form) headers["Content-Type"] = "application/json";

  const response = await fetch(path, {
    method,
    headers,
    body: form ? body : body ? JSON.stringify(body) : undefined,
  });

  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    const msg = data?.detail || data?.mensaje || `Error HTTP ${response.status}`;
    throw new Error(msg);
  }

  return data;
}

function Card({ title, children }) {
  return (
    <div className="rounded-2xl border border-slate-700/60 bg-slate-900/70 p-4 shadow-glow backdrop-blur-sm">
      <h3 className="mb-3 text-lg font-bold text-sky-300">{title}</h3>
      {children}
    </div>
  );
}

function Input({ label, ...props }) {
  return (
    <label className="block text-sm text-slate-300">
      <span className="mb-1 block">{label}</span>
      <input
        className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-slate-100 outline-none focus:border-aqua"
        {...props}
      />
    </label>
  );
}

function Switch({ label, checked, onChange }) {
  return (
    <label className="flex items-center gap-2 text-sm text-slate-200">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      {label}
    </label>
  );
}

function LoginPanel({ service, token, onLogin, onLogout }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin123");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const login = async () => {
    setLoading(true);
    setError("");
    try {
      const form = new URLSearchParams();
      form.append("username", username);
      form.append("password", password);
      const data = await apiFetch(`/${service}/token`, {
        method: "POST",
        body: form,
        form: true,
      });
      onLogin(service, data.access_token);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card title={`Login ${SERVICES[service].label}`}>
      {token ? (
        <div className="space-y-2">
          <p className="text-sm text-emerald-300">Sesion activa.</p>
          <div className="rounded-lg border border-slate-700 bg-slate-950/70 p-2">
            <p className="text-xs font-semibold text-amber-300">Token (beta):</p>
            <p className="break-all text-xs text-slate-300">{token}</p>
          </div>
          <button className="rounded-lg bg-coral px-4 py-2 text-sm font-semibold text-white" onClick={() => onLogout(service)}>
            Cerrar sesion
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          <Input label="Usuario" value={username} onChange={(e) => setUsername(e.target.value)} />
          <Input label="Contrasena" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          <button
            className="rounded-lg bg-aqua px-4 py-2 text-sm font-semibold text-slate-950"
            onClick={login}
            disabled={loading}
          >
            {loading ? "Entrando..." : "Entrar"}
          </button>
          {error && <p className="text-sm text-red-300">{error}</p>}
        </div>
      )}
    </Card>
  );
}

function DataTable({ rows }) {
  if (!rows.length) return <p className="text-sm text-slate-300">Sin registros.</p>;
  const columns = Object.keys(rows[0]);
  return (
    <div className="overflow-auto">
      <table className="w-full text-left text-sm text-slate-200">
        <thead>
          <tr className="border-b border-slate-600">
            {columns.map((c) => (
              <th className="px-2 py-2 font-semibold text-sky-300" key={c}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr className="border-b border-slate-800" key={i}>
              {columns.map((c) => (
                <td className="px-2 py-2" key={c}>{String(row[c])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ClientesPanel({ token }) {
  const [rows, setRows] = useState([]);
  const [msg, setMsg] = useState("");
  const [form, setForm] = useState({ nombre: "", correo: "", direccion: "", telefono: "", activo: true });
  const [patch, setPatch] = useState({ id: "", nombre: "", correo: "", direccion: "", telefono: "", activo: true });
  const [deleteId, setDeleteId] = useState("");

  const load = async () => {
    try {
      setRows(await apiFetch(`/clientes${SERVICES.clientes.listPath}`, { token }));
    } catch (e) {
      setMsg(e.message);
    }
  };

  useEffect(() => { if (token) load(); }, [token]);
  useEffect(() => {
    if (!token) return undefined;
    const id = setInterval(load, AUTO_REFRESH_MS);
    return () => clearInterval(id);
  }, [token]);

  const create = async () => {
    setMsg("");
    try {
      const r = await apiFetch(`/clientes${SERVICES.clientes.createPath}`, { method: "POST", token, body: form });
      setMsg(r.mensaje || "Solicitud enviada");
      load();
    } catch (e) { setMsg(e.message); }
  };

  const update = async () => {
    setMsg("");
    try {
      const body = { activo: patch.activo };
      ["nombre", "correo", "direccion", "telefono"].forEach((k) => {
        if (patch[k]) body[k] = patch[k];
      });
      const r = await apiFetch(`/clientes${SERVICES.clientes.updatePath(patch.id)}`, { method: "PATCH", token, body });
      setMsg(r.mensaje || "Actualizado");
      load();
    } catch (e) { setMsg(e.message); }
  };

  const remove = async () => {
    setMsg("");
    try {
      const r = await apiFetch(`/clientes${SERVICES.clientes.deletePath(deleteId)}`, { method: "DELETE", token });
      setMsg(r.mensaje || "Eliminado");
      load();
    } catch (e) { setMsg(e.message); }
  };

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <button className="rounded-lg bg-sky px-4 py-2 text-sm font-bold text-slate-950" onClick={load}>Refrescar</button>
      </div>
      {msg && <p className="text-sm text-amber-300">{msg}</p>}
      <Card title="Crear Cliente">
        <div className="grid gap-2 md:grid-cols-2">
          <Input label="Nombre" value={form.nombre} onChange={(e) => setForm({ ...form, nombre: e.target.value })} />
          <Input label="Correo" value={form.correo} onChange={(e) => setForm({ ...form, correo: e.target.value })} />
          <Input label="Direccion" value={form.direccion} onChange={(e) => setForm({ ...form, direccion: e.target.value })} />
          <Input label="Telefono" value={form.telefono} onChange={(e) => setForm({ ...form, telefono: e.target.value })} />
          <Switch label="Activo" checked={form.activo} onChange={(v) => setForm({ ...form, activo: v })} />
        </div>
        <button className="mt-3 rounded-lg bg-aqua px-4 py-2 text-sm font-semibold text-slate-950" onClick={create}>Guardar</button>
      </Card>

      <Card title="Actualizar Cliente (PATCH)">
        <div className="grid gap-2 md:grid-cols-2">
          <Input label="ID cliente" value={patch.id} onChange={(e) => setPatch({ ...patch, id: e.target.value })} />
          <Input label="Nombre" value={patch.nombre} onChange={(e) => setPatch({ ...patch, nombre: e.target.value })} />
          <Input label="Correo" value={patch.correo} onChange={(e) => setPatch({ ...patch, correo: e.target.value })} />
          <Input label="Direccion" value={patch.direccion} onChange={(e) => setPatch({ ...patch, direccion: e.target.value })} />
          <Input label="Telefono" value={patch.telefono} onChange={(e) => setPatch({ ...patch, telefono: e.target.value })} />
          <Switch label="Activo" checked={patch.activo} onChange={(v) => setPatch({ ...patch, activo: v })} />
        </div>
        <button className="mt-3 rounded-lg bg-coral px-4 py-2 text-sm font-semibold text-white" onClick={update}>Actualizar</button>
      </Card>

      <Card title="Eliminar Cliente">
        <div className="flex flex-col gap-2 md:flex-row">
          <Input label="ID cliente" value={deleteId} onChange={(e) => setDeleteId(e.target.value)} />
          <button className="mt-6 rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white" onClick={remove}>Eliminar</button>
        </div>
      </Card>

      <Card title="Listado de Clientes"><DataTable rows={rows} /></Card>
    </div>
  );
}

function ProductosPanel({ token }) {
  const [rows, setRows] = useState([]);
  const [msg, setMsg] = useState("");
  const [form, setForm] = useState({ descripcion: "", precio: "", activo: true, stock_inicial: 0 });
  const [patch, setPatch] = useState({ id: "", descripcion: "", precio: "", activo: true });
  const [deleteId, setDeleteId] = useState("");

  const load = async () => {
    try { setRows(await apiFetch(`/productos${SERVICES.productos.listPath}`, { token })); }
    catch (e) { setMsg(e.message); }
  };
  useEffect(() => { if (token) load(); }, [token]);
  useEffect(() => {
    if (!token) return undefined;
    const id = setInterval(load, AUTO_REFRESH_MS);
    return () => clearInterval(id);
  }, [token]);

  const create = async () => {
    try {
      const r = await apiFetch(`/productos${SERVICES.productos.createPath}`, {
        method: "POST",
        token,
        body: { ...form, precio: Number(form.precio), stock_inicial: Number(form.stock_inicial || 0) },
      });
      setMsg(r.mensaje || "Solicitud enviada");
      load();
    } catch (e) { setMsg(e.message); }
  };

  const update = async () => {
    try {
      const body = { activo: patch.activo };
      if (patch.descripcion) body.descripcion = patch.descripcion;
      if (patch.precio) body.precio = Number(patch.precio);
      const r = await apiFetch(`/productos${SERVICES.productos.updatePath(patch.id)}`, { method: "PATCH", token, body });
      setMsg(r.mensaje || "Actualizado");
      load();
    } catch (e) { setMsg(e.message); }
  };

  const remove = async () => {
    try {
      const r = await apiFetch(`/productos${SERVICES.productos.deletePath(deleteId)}`, { method: "DELETE", token });
      setMsg(r.mensaje || "Eliminado");
      load();
    } catch (e) { setMsg(e.message); }
  };

  return (
    <div className="space-y-4">
      <button className="rounded-lg bg-sky px-4 py-2 text-sm font-bold text-slate-950" onClick={load}>Refrescar</button>
      {msg && <p className="text-sm text-amber-300">{msg}</p>}
      <Card title="Crear Producto">
        <div className="grid gap-2 md:grid-cols-2">
          <Input label="Descripcion" value={form.descripcion} onChange={(e) => setForm({ ...form, descripcion: e.target.value })} />
          <Input label="Precio" type="number" value={form.precio} onChange={(e) => setForm({ ...form, precio: e.target.value })} />
          <Input label="Stock inicial" type="number" value={form.stock_inicial} onChange={(e) => setForm({ ...form, stock_inicial: e.target.value })} />
          <Switch label="Activo" checked={form.activo} onChange={(v) => setForm({ ...form, activo: v })} />
        </div>
        <button className="mt-3 rounded-lg bg-aqua px-4 py-2 text-sm font-semibold text-slate-950" onClick={create}>Guardar</button>
      </Card>
      <Card title="Actualizar Producto (PATCH)">
        <div className="grid gap-2 md:grid-cols-2">
          <Input label="ID producto" value={patch.id} onChange={(e) => setPatch({ ...patch, id: e.target.value })} />
          <Input label="Descripcion" value={patch.descripcion} onChange={(e) => setPatch({ ...patch, descripcion: e.target.value })} />
          <Input label="Precio" type="number" value={patch.precio} onChange={(e) => setPatch({ ...patch, precio: e.target.value })} />
          <Switch label="Activo" checked={patch.activo} onChange={(v) => setPatch({ ...patch, activo: v })} />
        </div>
        <button className="mt-3 rounded-lg bg-coral px-4 py-2 text-sm font-semibold text-white" onClick={update}>Actualizar</button>
      </Card>
      <Card title="Eliminar Producto">
        <div className="flex flex-col gap-2 md:flex-row">
          <Input label="ID producto" value={deleteId} onChange={(e) => setDeleteId(e.target.value)} />
          <button className="mt-6 rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white" onClick={remove}>Eliminar</button>
        </div>
      </Card>
      <Card title="Catalogo de Productos"><DataTable rows={rows} /></Card>
    </div>
  );
}

function PedidosPanel({ token }) {
  const [rows, setRows] = useState([]);
  const [msg, setMsg] = useState("");
  const [form, setForm] = useState({ id_cliente: "", id_producto: "", cantidad: "", descuento_pct: "0" });

  const load = async () => {
    try { setRows(await apiFetch(`/pedidos${SERVICES.pedidos.listPath}`, { token })); }
    catch (e) { setMsg(e.message); }
  };
  useEffect(() => { if (token) load(); }, [token]);
  useEffect(() => {
    if (!token) return undefined;
    const id = setInterval(load, AUTO_REFRESH_MS);
    return () => clearInterval(id);
  }, [token]);

  const create = async () => {
    try {
      const r = await apiFetch(`/pedidos${SERVICES.pedidos.createPath}`, {
        method: "POST",
        token,
        body: {
          id_cliente: Number(form.id_cliente),
          id_producto: Number(form.id_producto),
          cantidad: Number(form.cantidad),
          descuento_pct: Number(form.descuento_pct || 0),
        },
      });
      setMsg(r.mensaje || "Pedido enviado");
      load();
    } catch (e) { setMsg(e.message); }
  };

  return (
    <div className="space-y-4">
      <button className="rounded-lg bg-sky px-4 py-2 text-sm font-bold text-slate-950" onClick={load}>Refrescar</button>
      {msg && <p className="text-sm text-amber-300">{msg}</p>}
      <Card title="Crear Pedido">
        <div className="grid gap-2 md:grid-cols-4">
          <Input label="ID cliente" type="number" value={form.id_cliente} onChange={(e) => setForm({ ...form, id_cliente: e.target.value })} />
          <Input label="ID producto" type="number" value={form.id_producto} onChange={(e) => setForm({ ...form, id_producto: e.target.value })} />
          <Input label="Cantidad" type="number" value={form.cantidad} onChange={(e) => setForm({ ...form, cantidad: e.target.value })} />
          <Input label="Descuento %" type="number" value={form.descuento_pct} onChange={(e) => setForm({ ...form, descuento_pct: e.target.value })} />
        </div>
        <button className="mt-3 rounded-lg bg-aqua px-4 py-2 text-sm font-semibold text-slate-950" onClick={create}>Enviar pedido</button>
      </Card>
      <Card title="Listado de Pedidos"><DataTable rows={rows} /></Card>
    </div>
  );
}

function InventarioPanel({ token }) {
  const [rows, setRows] = useState([]);
  const [msg, setMsg] = useState("");
  const [plus, setPlus] = useState({ id_producto: "", cantidad: "" });

  const load = async () => {
    try { setRows(await apiFetch(`/inventario${SERVICES.inventario.listPath}`, { token })); }
    catch (e) { setMsg(e.message); }
  };
  useEffect(() => { if (token) load(); }, [token]);
  useEffect(() => {
    if (!token) return undefined;
    const id = setInterval(load, AUTO_REFRESH_MS);
    return () => clearInterval(id);
  }, [token]);

  const call = async (path, payload) => {
    try {
      const r = await apiFetch(`/inventario${path}`, { method: "POST", token, body: payload });
      setMsg(r.mensaje || "Operacion enviada");
      load();
    } catch (e) { setMsg(e.message); }
  };

  return (
    <div className="space-y-4">
      <button className="rounded-lg bg-sky px-4 py-2 text-sm font-bold text-slate-950" onClick={load}>Refrescar</button>
      <p className="text-sm text-slate-300">Inventario no da de alta productos y no descuenta manualmente. Aqui solo se agrega cantidad; el descuento lo hace Pedidos.</p>
      {msg && <p className="text-sm text-amber-300">{msg}</p>}
      <Card title="Agregar Stock">
        <div className="grid gap-2 md:grid-cols-2">
          <Input label="ID producto" type="number" value={plus.id_producto} onChange={(e) => setPlus({ ...plus, id_producto: e.target.value })} />
          <Input label="Cantidad a agregar" type="number" value={plus.cantidad} onChange={(e) => setPlus({ ...plus, cantidad: e.target.value })} />
        </div>
        <button className="mt-3 rounded-lg bg-sky px-4 py-2 text-sm font-semibold text-slate-950" onClick={() => call(SERVICES.inventario.addPath, { id_producto: Number(plus.id_producto), cantidad: Number(plus.cantidad) })}>Agregar</button>
      </Card>
      <Card title="Inventario Actual"><DataTable rows={rows} /></Card>
    </div>
  );
}

function GeneralPanel({ tokens }) {
  const [data, setData] = useState({
    clientes: [],
    productos: [],
    pedidos: [],
    inventario: [],
  });
  const [msg, setMsg] = useState("");

  const loadAll = async () => {
    const next = {
      clientes: [],
      productos: [],
      pedidos: [],
      inventario: [],
    };
    const jobs = [];
    if (tokens.clientes) {
      jobs.push(
        apiFetch(`/clientes${SERVICES.clientes.listPath}`, { token: tokens.clientes }).then((rows) => {
          next.clientes = rows;
        })
      );
    }
    if (tokens.productos) {
      jobs.push(
        apiFetch(`/productos${SERVICES.productos.listPath}`, { token: tokens.productos }).then((rows) => {
          next.productos = rows;
        })
      );
    }
    if (tokens.pedidos) {
      jobs.push(
        apiFetch(`/pedidos${SERVICES.pedidos.listPath}`, { token: tokens.pedidos }).then((rows) => {
          next.pedidos = rows;
        })
      );
    }
    if (tokens.inventario) {
      jobs.push(
        apiFetch(`/inventario${SERVICES.inventario.listPath}`, { token: tokens.inventario }).then((rows) => {
          next.inventario = rows;
        })
      );
    }
    const results = await Promise.allSettled(jobs);
    const failed = results.find((r) => r.status === "rejected");
    setData(next);
    setMsg(failed ? failed.reason?.message || "Error parcial al cargar servicios" : "");
  };

  useEffect(() => {
    loadAll();
  }, [tokens.clientes, tokens.productos, tokens.pedidos, tokens.inventario]);

  useEffect(() => {
    const hasToken = tokens.clientes || tokens.productos || tokens.pedidos || tokens.inventario;
    if (!hasToken) return undefined;
    const id = setInterval(loadAll, AUTO_REFRESH_MS);
    return () => clearInterval(id);
  }, [tokens.clientes, tokens.productos, tokens.pedidos, tokens.inventario]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <button className="rounded-lg bg-sky px-4 py-2 text-sm font-bold text-slate-950" onClick={loadAll}>Refrescar todo</button>
        <p className="text-xs text-slate-300">Auto-refresco cada {AUTO_REFRESH_MS / 1000}s</p>
      </div>
      {msg && <p className="text-sm text-amber-300">{msg}</p>}
      <Card title="Clientes"><DataTable rows={data.clientes} /></Card>
      <Card title="Productos"><DataTable rows={data.productos} /></Card>
      <Card title="Pedidos"><DataTable rows={data.pedidos} /></Card>
      <Card title="Inventario"><DataTable rows={data.inventario} /></Card>
    </div>
  );
}

function App() {
  const [tab, setTab] = useState("clientes");
  const [tokens, setTokens] = useState(() => {
    try { return JSON.parse(localStorage.getItem("shopnow_tokens") || "{}"); }
    catch { return {}; }
  });

  useEffect(() => {
    localStorage.setItem("shopnow_tokens", JSON.stringify(tokens));
  }, [tokens]);

  const setToken = (service, token) => setTokens((t) => ({ ...t, [service]: token }));
  const clearToken = (service) => setTokens((t) => ({ ...t, [service]: "" }));

  const content = useMemo(() => {
    if (tab === "general") return <GeneralPanel tokens={tokens} />;
    if (!tokens[tab]) return <p className="rounded-xl bg-slate-800 p-4 text-slate-300">Inicia sesion en {SERVICES[tab].label} para usar su panel.</p>;
    if (tab === "clientes") return <ClientesPanel token={tokens.clientes} />;
    if (tab === "productos") return <ProductosPanel token={tokens.productos} />;
    if (tab === "pedidos") return <PedidosPanel token={tokens.pedidos} />;
    return <InventarioPanel token={tokens.inventario} />;
  }, [tab, tokens]);

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_20%_20%,#0f766e_0%,transparent_40%),radial-gradient(circle_at_90%_0%,#fb923c_0%,transparent_35%),linear-gradient(170deg,#020617,#0f172a)] p-4 text-slate-100 md:p-8">
      <div className="mx-auto max-w-7xl">
        <header className="mb-6 rounded-3xl border border-slate-700/60 bg-slate-900/70 p-6 backdrop-blur">
          <h1 className="text-3xl font-black tracking-tight text-white md:text-4xl">ShopNow Control Center</h1>
          <p className="mt-2 text-slate-300">Interfaz grafica de microservicios con login independiente por servicio y operaciones CRUD.</p>
        </header>

        <section className="mb-6 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {SERVICE_TABS.map((service) => (
            <LoginPanel
              key={service}
              service={service}
              token={tokens[service]}
              onLogin={setToken}
              onLogout={clearToken}
            />
          ))}
        </section>

        <section className="mb-4 flex flex-wrap gap-2">
          {MAIN_TABS.map((service) => (
            <button
              key={service}
              onClick={() => setTab(service)}
              className={`rounded-xl px-4 py-2 text-sm font-bold transition ${tab === service ? "bg-aqua text-slate-950" : "bg-slate-800 text-slate-200 hover:bg-slate-700"}`}
            >
              {service === "general" ? "Vista general" : SERVICES[service].label}
            </button>
          ))}
        </section>

        <section>{content}</section>
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
