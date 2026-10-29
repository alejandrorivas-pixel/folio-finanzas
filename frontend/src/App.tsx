import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import ImportCorrection from "./ImportCorrection";
import type { ImportError } from "./types";
import {
  ArrowDownLeft,
  ArrowUpRight,
  ArrowRight,
  ArrowUp,
  ArrowUpDown,
  Banknote,
  Building2,
  CalendarDays,
  ChartNoAxesCombined,
  Check,
  CheckCheck,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  CirclePlus,
  CreditCard,
  Download,
  FileSpreadsheet,
  FolderCheck,
  LayoutDashboard,
  ListFilter,
  LoaderCircle,
  MoreHorizontal,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
  Upload,
  Wallet,
  X,
} from "lucide-react";
import {
  api,
  money,
  monthName,
  dateName,
  accountName,
  treatmentName,
} from "./api";
import type {
  Movement,
  Summary,
  Meta,
  Proposal,
  Evidence,
  ChatMessage,
} from "./types";

type View = "dashboard" | "movements" | "pending" | "agents";
type Health = {
  status: string;
  ai_configured: boolean;
  model: string;
  demo_mode?: boolean;
};
const CURRENT_MONTH = new Intl.DateTimeFormat("en-CA", {
  year: "numeric",
  month: "2-digit",
  timeZone: "America/Mexico_City",
})
  .format(new Date())
  .replace("/", "-");
const today = () =>
  new Date().toLocaleDateString("en-CA", { timeZone: "America/Mexico_City" });

function Modal({
  title,
  subtitle,
  children,
  onClose,
  wide = false,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
    return () => ref.current?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className={`modal ${wide ? "wide" : ""}`}
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal-heading">
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        <button className="icon-button" onClick={onClose} aria-label="Cerrar">
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}

function MovementTable({
  rows,
  onSelect,
  compact = false,
}: {
  rows: Movement[];
  onSelect: (r: Movement) => void;
  compact?: boolean;
}) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Concepto</th>
            <th>Cuenta</th>
            {!compact && <th>Categoría</th>}
            <th>Fecha</th>
            <th className="right">Importe</th>
            <th className="sr-only">Ver detalle</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.id || `${r.source_sheet}-${r.source_row}-${i}`}>
              <td>
                <button className="concept-button" onClick={() => onSelect(r)}>
                  <span
                    className={`movement-icon ${r.amount_minor > 0 ? "in" : "out"}`}
                  >
                    {r.amount_minor > 0 ? (
                      <ArrowDownLeft size={17} />
                    ) : (
                      <ArrowUpRight size={17} />
                    )}
                  </span>
                  <span>
                    <strong>{r.description}</strong>
                    <small>
                      {r.property || treatmentName[r.treatment]}
                      {r.duplicate ? " · Ya importado" : ""}
                    </small>
                  </span>
                </button>
              </td>
              <td>
                <span className={`account-chip ${r.account}`}>
                  {accountName[r.account]}
                </span>
              </td>
              {!compact && <td className="category-cell">{r.category}</td>}
              <td className="date-cell">{dateName(r.date)}</td>
              <td
                className={`right amount ${r.amount_minor > 0 ? "positive" : ""}`}
              >
                {r.amount_minor > 0 ? "+" : "−"}
                {money(Math.abs(r.amount_minor))}
              </td>
              <td>
                <button
                  className="icon-button"
                  onClick={() => onSelect(r)}
                  aria-label={`Ver detalle de ${r.description}`}
                >
                  <ChevronRight size={16} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ActivityChart({ summary }: { summary: Summary | null }) {
  const days = summary?.daily || [];
  const groups = Array.from({ length: 8 }, (_, i) => ({
    label: `${i * 4 + 1}`,
    income: 0,
    expense: 0,
  }));
  for (const d of days) {
    const i = Math.min(7, Math.floor((Number(d.date.slice(8)) - 1) / 4));
    groups[i].income += d.income_minor;
    groups[i].expense += d.expense_minor;
  }
  const max = Math.max(...groups.flatMap((g) => [g.income, g.expense]), 100);
  return (
    <div className="activity-chart">
      <div className="chart-scale">
        <span>{money(max)}</span>
        <span>{money(Math.round(max / 2))}</span>
        <span>$0</span>
      </div>
      <div className="chart-plot">
        <div className="chart-grid" />
        {groups.map((g, i) => (
          <div
            className="bar-group"
            key={i}
            title={`Días ${g.label}–${Math.min(31, i * 4 + 4)} · Ingresos ${money(g.income)} · Gastos ${money(g.expense)}`}
          >
            <div className="bar-pair">
              <div
                className="bar income"
                style={{ height: `${(Math.max(0, g.income) / max) * 100}%` }}
              />
              <div
                className="bar expense"
                style={{ height: `${(Math.max(0, g.expense) / max) * 100}%` }}
              />
            </div>
            <span>{g.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ProposalModal({
  proposal,
  onClose,
  onDone,
  onDetail,
}: {
  proposal: Proposal;
  onClose: () => void;
  onDone: (message: string) => void;
  onDetail: (r: Movement) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [limit, setLimit] = useState(8);
  const [current, setCurrent] = useState(proposal);
  const [correction, setCorrection] = useState<ImportError | null>(null);
  const p = current.payload,
    stats = p.stats;
  const confirm = async () => {
    setBusy(true);
    setError("");
    try {
      const r = await api<{ inserted: number; duplicates: number }>(
        `/api/proposals/${proposal.id}/confirm`,
        { method: "POST", body: JSON.stringify({ confirm: true }) },
      );
      onDone(
        `${r.inserted} movimientos confirmados${r.duplicates ? ` · ${r.duplicates} duplicados omitidos` : ""}.`,
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const reject = async () => {
    setBusy(true);
    try {
      await api(`/api/proposals/${proposal.id}/reject`, {
        method: "POST",
        body: JSON.stringify({ confirm: true }),
      });
      onDone("Propuesta descartada.");
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };
  return (
    <Modal
      title={
        proposal.kind === "import"
          ? "Revisa tu importación"
          : "Revisa el movimiento"
      }
      subtitle={p.filename || "Este movimiento todavía no afecta tus cifras."}
      wide
      onClose={onClose}
    >
      <div className="preview-summary">
        <div>
          <span>Registros</span>
          <strong>{stats?.total ?? p.movements.length}</strong>
        </div>
        <div>
          <span>Nuevos</span>
          <strong>{stats?.new ?? p.movements.length}</strong>
        </div>
        <div>
          <span>Ya importados</span>
          <strong>{stats?.duplicates ?? 0}</strong>
        </div>
        <div>
          <span>Errores</span>
          <strong className={p.errors.length ? "negative" : ""}>
            {p.errors.length}
          </strong>
        </div>
      </div>
      <div className="notice">
        <ShieldCheck size={18} />
        <span>
          Confirmar incorpora los registros a tu libro. La conciliación con el
          banco se realiza por separado. Los movimientos no operativos se
          distinguen del gasto y del ingreso.
        </span>
      </div>
      {p.openings.length > 0 && (
        <div className="opening-list">
          {p.openings.map((a) => (
            <span key={a.account}>
              Saldo inicial · {accountName[a.account]}{" "}
              <b>{money(a.amount_minor)}</b>
            </span>
          ))}
        </div>
      )}
      {p.errors.length > 0 && (
        <div className="error-box">
          <strong>Revisa estas filas antes de confirmar.</strong>
          {p.errors.slice(0, 12).map((e, i) => (
            <p key={i}>
              {e.sheet}, fila {e.row}: {e.message}
              {e.draft && (
                <button
                  className="button secondary small-button"
                  style={{ marginLeft: 10 }}
                  onClick={() => setCorrection(e)}
                >
                  Revisar fila
                </button>
              )}
            </p>
          ))}
        </div>
      )}
      {correction && (
        <ImportCorrection
          key={`${correction.sheet}-${correction.row}`}
          error={correction}
          proposal={current}
          onCancel={() => setCorrection(null)}
          onSaved={(p) => {
            setCurrent(p);
            setCorrection(null);
          }}
        />
      )}
      {!!p.corrections?.length && (
        <div className="notice">
          <ShieldCheck size={18} />
          <span>
            {p.corrections.length} correcciones revisadas. Se guardará el motivo
            y el origen de cada una.
          </span>
        </div>
      )}
      {p.notes.map((n, i) => (
        <p className="muted" key={i}>
          {n}
        </p>
      ))}
      {!!stats?.review && (
        <p className="warning-text">
          {stats.review} movimientos sin categoría quedarán “Por revisar”, fuera
          del resultado operativo hasta clasificarlos.
        </p>
      )}
      <MovementTable rows={p.movements.slice(0, limit)} onSelect={onDetail} />
      {p.movements.length > limit && (
        <button
          className="text-button show-more"
          onClick={() => setLimit((l) => l + 40)}
        >
          Mostrar más movimientos ({p.movements.length - limit} restantes)
          <ChevronDown size={15} />
        </button>
      )}
      {error && (
        <div className="error-box" role="alert">
          {error}
        </div>
      )}
      <div className="modal-footer">
        <button className="button secondary" onClick={reject} disabled={busy}>
          Descartar propuesta
        </button>
        <button
          className="button primary"
          onClick={confirm}
          disabled={busy || p.errors.length > 0 || !p.movements.length}
        >
          {busy ? (
            <LoaderCircle size={17} className="spin" />
          ) : (
            <CheckCheck size={17} />
          )}
          Confirmar {stats?.new ?? p.movements.length} movimientos
        </button>
      </div>
    </Modal>
  );
}

function ManualModal({
  meta,
  onClose,
  onCreated,
}: {
  meta: Meta | null;
  onClose: () => void;
  onCreated: (p: Proposal) => void;
}) {
  const [form, setForm] = useState({
    date: today(),
    account: "efectivo",
    kind: "egreso",
    category: "Nómina y sueldos",
    description: "",
    amount: "",
    reference: "",
    property: "",
  });
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const update = (key: string, value: string) =>
    setForm((f) => ({
      ...f,
      [key]: value,
      ...(key === "account"
        ? { kind: value === "tarjeta_bbva" ? "cargo" : "egreso" }
        : {}),
    }));
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (!/^\d+(\.\d{1,2})?$/.test(form.amount))
        throw new Error("Usa un importe positivo con hasta dos decimales.");
      const [whole, fraction = ""] = form.amount.split(".");
      const cents = Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
      const p = await api<Proposal>("/api/proposals/manual", {
        method: "POST",
        body: JSON.stringify({ ...form, amount_minor: cents }),
      });
      onCreated(p);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal
      title="Nuevo movimiento"
      subtitle="Prepara el registro. Lo confirmarás en el siguiente paso."
      onClose={onClose}
    >
      <form onSubmit={submit} className="manual-form">
        <div className="form-grid">
          <label>
            Fecha
            <input
              type="date"
              value={form.date}
              onChange={(e) => update("date", e.target.value)}
              required
            />
          </label>
          <label>
            Cuenta
            <select
              value={form.account}
              onChange={(e) => update("account", e.target.value)}
            >
              {Object.entries(accountName).map(([v, n]) => (
                <option key={v} value={v}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <label>
            Tipo
            <select
              value={form.kind}
              onChange={(e) => update("kind", e.target.value)}
            >
              {(form.account === "tarjeta_bbva"
                ? [
                    "cargo",
                    "pago",
                    "interes",
                    "comision",
                    "abono",
                    "devolucion",
                  ]
                : ["egreso", "ingreso"]
              ).map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
          </label>
          <label>
            Importe en MXN
            <input
              inputMode="decimal"
              placeholder="0.00"
              value={form.amount}
              onChange={(e) => update("amount", e.target.value)}
              required
            />
          </label>
        </div>
        <label>
          Concepto
          <input
            placeholder="Ej. Pago de nómina de octubre"
            maxLength={1000}
            value={form.description}
            onChange={(e) => update("description", e.target.value)}
            required
          />
        </label>
        <label>
          Categoría
          <select
            value={form.category}
            onChange={(e) => update("category", e.target.value)}
          >
            {meta?.categories.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <div className="form-grid">
          <label>
            Referencia / proveedor <span>(opcional)</span>
            <input
              value={form.reference}
              onChange={(e) => update("reference", e.target.value)}
              maxLength={300}
            />
          </label>
          <label>
            Folio de propiedad <span>(opcional)</span>
            <input
              placeholder="DEMO-001"
              maxLength={100}
              value={form.property}
              onChange={(e) => update("property", e.target.value)}
            />
          </label>
        </div>
        {error && (
          <p className="error-box" role="alert">
            {error}
          </p>
        )}
        <div className="modal-footer">
          <button type="button" className="button secondary" onClick={onClose}>
            Cancelar
          </button>
          <button className="button primary" disabled={busy}>
            {busy ? (
              <LoaderCircle size={17} className="spin" />
            ) : (
              <ArrowRight size={17} />
            )}
            Revisar propuesta
          </button>
        </div>
      </form>
    </Modal>
  );
}

function AgentPanel({
  health,
  month,
  account,
  onProposal,
  onEvidence,
  onPending,
  onHelp,
}: {
  health: Health | null;
  month: string;
  account: string;
  onProposal: (p: Proposal) => void;
  onEvidence: (e: Evidence) => void;
  onPending: () => void;
  onHelp: () => void;
}) {
  const [mode, setMode] = useState<"analyst" | "capture">("analyst");
  const [messages, setMessages] = useState<ChatMessage[]>([]),
    [input, setInput] = useState(""),
    [busy, setBusy] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (messages.length || busy) {
      const scroll = bottom.current?.parentElement;
      scroll?.scrollTo({ top: scroll.scrollHeight, behavior: "smooth" });
    }
  }, [messages, busy]);
  const send = async (text = input) => {
    if (!text.trim() || busy) return;
    const history = messages
      .filter((m) => m.mode === mode)
      .slice(-8)
      .map((m) => ({ role: m.role, content: m.content }));
    setMessages((m) => [...m, { role: "user", content: text, mode }]);
    setInput("");
    setBusy(true);
    try {
      const result = await api<{
        message: string;
        evidence?: Evidence[];
        proposal?: Proposal;
      }>("/api/chat", {
        method: "POST",
        body: JSON.stringify({
          message: text,
          mode,
          month: month || null,
          account: account || null,
          history,
        }),
      });
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: result.message,
          evidence: result.evidence,
          proposal: result.proposal,
          mode,
        },
      ]);
      if (result.proposal) onPending();
    } catch (e) {
      setMessages((m) => [
        ...m,
        { role: "assistant", content: (e as Error).message, mode },
      ]);
    } finally {
      setBusy(false);
    }
  };
  return (
    <aside className="agent-panel">
      <div className="agent-panel-heading">
        <span className="sparkle-square">
          <Sparkles size={20} />
        </span>
        <div>
          <h3>Tu equipo de IA</h3>
          <p>Una segunda mirada a tus números</p>
        </div>
        <button
          className="icon-button"
          onClick={onHelp}
          aria-label="Ayuda de agentes"
        >
          <MoreHorizontal size={20} />
        </button>
      </div>
      <div className="agent-tabs">
        <button
          className={mode === "analyst" ? "active" : ""}
          onClick={() => setMode("analyst")}
        >
          <ChartNoAxesCombined size={14} />
          Analista
        </button>
        <button
          className={mode === "capture" ? "active" : ""}
          onClick={() => setMode("capture")}
        >
          <CirclePlus size={14} />
          Captura
        </button>
      </div>
      <div className="agent-status">
        <span
          className={`status-dot ${health?.ai_configured ? "" : "offline"}`}
        />
        {health?.ai_configured
          ? "OpenAI conectado"
          : "Conexión de OpenAI pendiente"}
        <ShieldCheck size={13} />
      </div>
      <div className="chat-scroll">
        {messages.filter((m) => m.mode === mode).length === 0 && (
          <div className="agent-welcome">
            <div className="agent-avatar">
              <Sparkles size={25} />
            </div>
            <h4>
              {mode === "analyst"
                ? "Pregúntale a tus números."
                : "Cuéntame qué movimiento hubo."}
            </h4>
            <p>
              {mode === "analyst"
                ? "Consulta tus movimientos y abre el respaldo de cada respuesta."
                : "Preparo el registro y tú decides si se incorpora al libro."}
            </p>
            <div className="suggestions">
              {(mode === "analyst"
                ? [
                    "¿Cuánto gastamos en nómina este mes?",
                    "Muéstrame los gastos de publicidad",
                    "¿Qué pagos de tarjeta registramos?",
                  ]
                : [
                    "Hoy pagué 1,500 pesos de nómina en efectivo",
                    "Recibí 3,000 pesos en banco por una investigación",
                  ]
              ).map((s) => (
                <button
                  key={s}
                  onClick={() => {
                    if (health?.ai_configured) void send(s);
                    else setInput(s);
                  }}
                >
                  {s}
                  <ArrowUpRight size={14} />
                </button>
              ))}
            </div>
          </div>
        )}
        {messages
          .filter((m) => m.mode === mode)
          .map((m, i) => (
            <div key={i} className={`chat-message ${m.role}`}>
              {m.role === "assistant" && (
                <span className="chat-label">
                  <Sparkles size={12} />
                  {mode === "analyst" ? "Agente analista" : "Agente de captura"}
                </span>
              )}
              <p>{m.content}</p>
              {m.evidence?.map((e, j) => (
                <button
                  className="evidence-button"
                  key={j}
                  onClick={() => onEvidence(e)}
                >
                  <FolderCheck size={15} />
                  Ver respaldo · {e.totals.count} movimientos
                  <ArrowUpRight size={14} />
                </button>
              ))}
              {m.proposal && (
                <button
                  className="evidence-button"
                  onClick={() => onProposal(m.proposal!)}
                >
                  <FileSpreadsheet size={15} />
                  Revisar propuesta
                  <ArrowRight size={14} />
                </button>
              )}
            </div>
          ))}
        {busy && (
          <div className="agent-thinking">
            <LoaderCircle size={14} className="spin" />
            {mode === "analyst"
              ? "Consultando el libro…"
              : "Preparando la propuesta…"}
          </div>
        )}
        <div ref={bottom} />
      </div>
      <form
        className="chat-composer"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        <textarea
          aria-label="Mensaje al agente"
          value={input}
          maxLength={3000}
          onChange={(e) => setInput(e.target.value)}
          placeholder={
            mode === "analyst"
              ? "Pregunta sobre tu negocio…"
              : "Describe el movimiento…"
          }
          rows={2}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void send();
            }
          }}
        />
        <div>
          <span>
            <ShieldCheck size={12} />
            Tú confirmas los cambios
          </span>
          <button
            type="submit"
            aria-label="Enviar mensaje"
            disabled={busy || !input.trim()}
          >
            <ArrowUp size={17} />
          </button>
        </div>
      </form>
      <p className="agent-footnote">
        Las cifras se calculan desde el libro confirmado.
      </p>
    </aside>
  );
}

export default function App() {
  const [view, setView] = useState<View>("dashboard");
  const [meta, setMeta] = useState<Meta | null>(null),
    [summary, setSummary] = useState<Summary | null>(null),
    [health, setHealth] = useState<Health | null>(null);
  const [month, setMonth] = useState(CURRENT_MONTH),
    [account, setAccount] = useState(""),
    [search, setSearch] = useState(""),
    [category, setCategory] = useState("");
  const [rows, setRows] = useState<Movement[]>([]),
    [total, setTotal] = useState(0),
    [page, setPage] = useState(1),
    [pending, setPending] = useState<Proposal[]>([]);
  const [version, setVersion] = useState(0),
    [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [toast, setToast] = useState("");
  const [proposal, setProposal] = useState<Proposal | null>(null),
    [detail, setDetail] = useState<Movement | null>(null),
    [manual, setManual] = useState(false),
    [help, setHelp] = useState(false),
    [importOpen, setImportOpen] = useState(false);
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const refresh = useCallback(() => setVersion((v) => v + 1), []);
  useEffect(() => {
    let active = true;
    Promise.all([
      api<Meta>("/api/meta"),
      api<Health>("/health"),
      api<Proposal[]>("/api/proposals"),
    ])
      .then(([m, h, p]) => {
        if (active) {
          setMeta(m);
          setHealth(h);
          setPending(p);
        }
      })
      .catch((e) => active && setError(e.message));
    return () => {
      active = false;
    };
  }, [version]);
  useEffect(() => {
    setPage(1);
  }, [month, account, search, category, evidence]);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    const q = new URLSearchParams();
    if (month) q.set("month", month);
    if (account) q.set("account", account);
    const tableQ = new URLSearchParams(q);
    if (search) tableQ.set("search", search);
    if (category) tableQ.set("category", category);
    if (evidence) {
      tableQ.delete("month");
      tableQ.delete("account");
      tableQ.delete("search");
      tableQ.delete("category");
      tableQ.set("ids", evidence.movement_ids.join(","));
    }
    tableQ.set("page", String(page));
    const timer = setTimeout(
      () =>
        Promise.all([
          api<Summary>(`/api/summary?${q}`, { signal: controller.signal }),
          api<{ items: Movement[]; total: number }>(
            `/api/movements?${tableQ}`,
            { signal: controller.signal },
          ),
        ])
          .then(([s, r]) => {
            setSummary(s);
            setRows(r.items);
            setTotal(r.total);
          })
          .catch((e) => {
            if (e.name !== "AbortError") setError(e.message);
          })
          .finally(() => {
            if (!controller.signal.aborted) setLoading(false);
          }),
      120,
    );
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [month, account, search, category, page, version, evidence]);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(""), 5000);
    return () => clearTimeout(t);
  }, [toast]);
  const upload = async (file?: File) => {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const data = new FormData();
      data.append("file", file);
      const p = await api<Proposal>("/api/imports/preview", {
        method: "POST",
        body: data,
      });
      setImportOpen(false);
      setProposal(p);
      refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };
  const localImport = async () => {
    setBusy(true);
    setError("");
    try {
      const p = await api<Proposal>("/api/imports/local-preview", {
        method: "POST",
        body: "{}",
      });
      setImportOpen(false);
      setProposal(p);
      refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const done = (message: string) => {
    setProposal(null);
    setToast(message);
    refresh();
  };
  const nav = (next: View) => {
    setView(next);
    if (next !== "movements") setEvidence(null);
  };
  const showEvidence = (e: Evidence) => {
    setEvidence(e);
    setView("movements");
    setSearch("");
    setCategory("");
    setPage(1);
  };
  const exportQ = new URLSearchParams();
  if (month) exportQ.set("month", month);
  if (account) exportQ.set("account", account);
  const count = meta?.count || 0;
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          href="#"
          className="brand"
          onClick={(e) => {
            e.preventDefault();
            nav("dashboard");
          }}
        >
          <span className="brand-mark">
            <ChartNoAxesCombined size={25} strokeWidth={2.8} />
          </span>
          folio<span className="brand-dot">.</span>
        </a>
        <div className="workspace-card">
          <span className="workspace-logo">D</span>
          <div>
            <strong>Empresa Demo</strong>
            <span>Espacio de trabajo</span>
          </div>
          <ChevronDown size={14} />
        </div>
        <span className="nav-label">TU OPERACIÓN</span>
        <nav>
          {(
            [
              { id: "dashboard", label: "Resumen", icon: LayoutDashboard },
              { id: "movements", label: "Movimientos", icon: ArrowUpDown },
              { id: "pending", label: "Por confirmar", icon: FolderCheck },
              { id: "agents", label: "Agentes IA", icon: Sparkles },
            ] as const
          ).map((n) => (
            <button
              key={n.id}
              className={`nav-item ${view === n.id ? "active" : ""}`}
              onClick={() => nav(n.id)}
            >
              <n.icon size={18} />
              {n.label}
              {n.id === "pending" && pending.length > 0 && (
                <span className="nav-count">{pending.length}</span>
              )}
              {n.id === "agents" && <span className="new-tag">2</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="local-card">
            <ShieldCheck size={20} />
            <strong>Tu libro, bajo tu control.</strong>
            <p>
              Los agentes proponen.
              <br />
              Tú confirmas cada cambio.
            </p>
            <span>
              <span className="status-dot" />
              Datos guardados localmente
            </span>
          </div>
          <button className="help-link" onClick={() => setHelp(true)}>
            <CircleHelp size={17} />
            Ayuda y conexión
            <ArrowUpRight size={14} />
          </button>
          <div className="profile">
            <span>ED</span>
            <div>
              <strong>Mi negocio</strong>
              <small>Administrador · MXN</small>
            </div>
            <span className="status-dot" />
          </div>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumb">
            Espacio de trabajo <ChevronRight size={13} />
            <strong>
              {
                {
                  dashboard: "Resumen financiero",
                  movements: "Movimientos",
                  pending: "Por confirmar",
                  agents: "Agentes IA",
                }[view]
              }
            </strong>
          </div>
          <div className="topbar-right">
            <span className="local-pill">
              <span className="status-dot" />
              Modo local
            </span>
            <button
              className="icon-button"
              onClick={() => setHelp(true)}
              aria-label="Ayuda"
            >
              <CircleHelp size={18} />
            </button>
            <span className="avatar-small">ED</span>
          </div>
        </header>
        <main>
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                <span className="tiny-line" />
                EL PULSO DE TU NEGOCIO
              </div>
              <h1>
                {view === "dashboard"
                  ? "Todo claro. Todo en orden."
                  : view === "movements"
                    ? "Cada movimiento cuenta."
                    : view === "pending"
                      ? "La última palabra es tuya."
                      : "Tu equipo, con otra mirada."}
              </h1>
              <p>
                {view === "dashboard"
                  ? "Tus finanzas en un solo lugar, con el respaldo de cada movimiento."
                  : view === "movements"
                    ? "Consulta el detalle y conoce de dónde viene cada cifra."
                    : view === "pending"
                      ? "Revisa lo que prepararon tus agentes antes de incorporarlo al libro."
                      : "Dos especialistas conectados a tus datos. Tú mantienes el control."}
              </p>
            </div>
            <div className="heading-actions">
              <button
                className="button secondary"
                onClick={() => setManual(true)}
              >
                <Plus size={17} />
                Nuevo movimiento
              </button>
              <button
                className="button primary"
                onClick={() => setImportOpen(true)}
                disabled={busy}
              >
                {busy ? (
                  <LoaderCircle size={17} className="spin" />
                ) : (
                  <Upload size={17} />
                )}
                Importar Excel
              </button>
            </div>
          </div>
          {import.meta.env.VITE_DEMO === "true" && (
            <div className="notice">
              <Sparkles size={18} />
              <span>
                <strong>Modo diseño · datos ficticios.</strong> Las respuestas
                del chat son simuladas y las importaciones son ejemplos. No se
                está usando una clave API.
              </span>
            </div>
          )}
          {health?.demo_mode && import.meta.env.VITE_DEMO !== "true" && (
            <div className="notice">
              <ShieldCheck size={18} />
              <span>
                <strong>Demostración · todos los datos son ficticios.</strong>{" "}
                Empresa, movimientos, proveedores, folios y saldos son ejemplos
                inventados.
              </span>
            </div>
          )}
          {error && (
            <div className="error-box dismissible" role="alert">
              <span>{error}</span>
              <button
                className="icon-button"
                onClick={() => setError("")}
                aria-label="Descartar error"
              >
                <X size={16} />
              </button>
            </div>
          )}
          <div className="filterbar">
            <div className="filters">
              <label className="select-wrap">
                <CalendarDays size={16} />
                <select
                  aria-label="Periodo"
                  value={month}
                  onChange={(e) => {
                    setMonth(e.target.value);
                    setEvidence(null);
                  }}
                >
                  <option value="">Todo el historial</option>
                  {[...new Set([CURRENT_MONTH, ...(meta?.months || [])])]
                    .sort()
                    .reverse()
                    .map((m) => (
                      <option key={m} value={m}>
                        {monthName(m)}
                      </option>
                    ))}
                </select>
                <ChevronDown size={14} />
              </label>
              <label className="select-wrap">
                <Wallet size={16} />
                <select
                  aria-label="Cuenta"
                  value={account}
                  onChange={(e) => {
                    setAccount(e.target.value);
                    setEvidence(null);
                  }}
                >
                  <option value="">Todas las cuentas</option>
                  {Object.entries(accountName).map(([v, n]) => (
                    <option key={v} value={v}>
                      {n}
                    </option>
                  ))}
                </select>
                <ChevronDown size={14} />
              </label>
            </div>
            <span className="confirmed-label">
              <CheckCheck size={14} />
              {count.toLocaleString("es-MX")} movimientos confirmados
            </span>
          </div>
          <div className="main-grid">
            <div className="main-content">
              {view === "dashboard" && (
                <>
                  <div className="stats-grid">
                    {[
                      {
                        label: "Ingresos operativos",
                        value: summary?.income_minor ?? 0,
                        icon: ArrowDownLeft,
                        cls: "green",
                        foot: "Entradas propias del negocio",
                      },
                      {
                        label: "Gastos operativos",
                        value: summary?.expense_minor ?? 0,
                        icon: ArrowUpRight,
                        cls: "orange",
                        foot: "Netos de devoluciones",
                      },
                      {
                        label: "Flujo operativo",
                        value: summary?.operating_net_minor ?? 0,
                        icon: ChartNoAxesCombined,
                        cls: "blue",
                        foot: "Ingresos menos gastos",
                      },
                      {
                        label: "Posición neta",
                        value: summary?.net_position_minor,
                        icon: Wallet,
                        cls: "purple",
                        foot: "Saldos al cierre · incluye deuda",
                      },
                    ].map((k) => (
                      <article className="stat-card" key={k.label}>
                        <div>
                          <span>{k.label}</span>
                          <span className={`stat-icon ${k.cls}`}>
                            <k.icon size={17} />
                          </span>
                        </div>
                        <strong
                          className={k.value == null ? "undetermined" : ""}
                        >
                          {loading && !summary ? "—" : money(k.value)}
                        </strong>
                        <small>{k.foot}</small>
                      </article>
                    ))}
                  </div>
                  <div className="insight-banner">
                    <span className="insight-icon">
                      <ShieldCheck size={20} />
                    </span>
                    <div>
                      <strong>
                        {count
                          ? "Cifras con respaldo, decisiones con claridad."
                          : "Tu siguiente paso: conecta tu libro de movimientos."}
                      </strong>
                      <p>
                        {count
                          ? `${summary?.count || 0} registros en este periodo · ${summary?.excluded_count || 0} fuera del resultado operativo. Pendientes de conciliación bancaria.`
                          : "Importa tu Excel, revisa los registros y confirma para ver el pulso de tu negocio."}
                      </p>
                    </div>
                    <button
                      className="text-button"
                      onClick={() =>
                        count ? nav("movements") : setImportOpen(true)
                      }
                    >
                      {count ? "Ver registros" : "Comenzar"}
                      <ArrowRight size={15} />
                    </button>
                  </div>
                  <div className="charts-row">
                    <section className="panel cashflow-panel">
                      <div className="panel-heading">
                        <div>
                          <h3>Entradas y salidas operativas</h3>
                          <p>Cómo se mueve tu negocio en el periodo</p>
                        </div>
                        <span className="chart-label">MXN</span>
                      </div>
                      <div className="chart-legend">
                        <span>
                          <i className="legend-income" />
                          Ingresos
                        </span>
                        <span>
                          <i className="legend-expense" />
                          Gastos
                        </span>
                      </div>
                      <ActivityChart summary={summary} />
                      <div className="chart-caption">
                        {month
                          ? `Días de ${monthName(month)}`
                          : "Agrupado por día del mes · todo el historial"}
                      </div>
                    </section>
                    <section className="panel categories-panel">
                      <div className="panel-heading">
                        <div>
                          <h3>¿En qué se va?</h3>
                          <p>Gastos por categoría</p>
                        </div>
                        <ArrowUpRight size={18} className="muted" />
                      </div>
                      {!summary?.categories.length ? (
                        <div className="category-empty">
                          <span className="empty-ring">
                            <ChartNoAxesCombined size={27} />
                          </span>
                          <p>Aquí verás tus principales gastos.</p>
                          <span>Empieza importando tus movimientos.</span>
                        </div>
                      ) : (
                        <div className="category-bars">
                          {summary.categories.slice(0, 5).map((c, i) => (
                            <button
                              key={c.name}
                              onClick={() => {
                                nav("movements");
                                setCategory(c.name);
                              }}
                            >
                              <div>
                                <span>{c.name}</span>
                                <strong>{money(c.amount_minor)}</strong>
                              </div>
                              <div className="category-track">
                                <i
                                  style={{
                                    width: `${(Math.max(0, c.amount_minor) / Math.max(1, ...summary.categories.map((c) => c.amount_minor))) * 100}%`,
                                    background: [
                                      "#227c68",
                                      "#4b9a85",
                                      "#83b6a5",
                                      "#b0cfc1",
                                      "#d4e5dc",
                                    ][i],
                                  }}
                                />
                              </div>
                            </button>
                          ))}
                        </div>
                      )}
                      <button
                        className="text-button category-link"
                        onClick={() => nav("movements")}
                      >
                        Explorar movimientos
                        <ArrowRight size={14} />
                      </button>
                    </section>
                  </div>
                  <section className="panel accounts-panel">
                    <div className="panel-heading">
                      <div>
                        <h3>Tus cuentas</h3>
                        <p>Saldos calculados a partir del libro</p>
                      </div>
                      <span className="muted small">MXN</span>
                    </div>
                    <div className="account-cards">
                      {(summary?.accounts || meta?.accounts || []).map((a) => (
                        <button
                          className="account-card"
                          key={a.id}
                          onClick={() => {
                            setAccount(a.id);
                            nav("movements");
                          }}
                        >
                          <span className={`account-icon ${a.id}`}>
                            {a.kind === "credit" ? (
                              <CreditCard size={20} />
                            ) : a.kind === "cash" ? (
                              <Banknote size={20} />
                            ) : (
                              <Building2 size={20} />
                            )}
                          </span>
                          <div>
                            <span>{a.name}</span>
                            <strong>
                              {money(
                                a.kind === "credit" && a.balance_minor != null
                                  ? -a.balance_minor
                                  : a.balance_minor,
                              )}
                            </strong>
                            <small>
                              {a.kind === "credit"
                                ? "Deuda registrada"
                                : "Disponible registrado"}
                            </small>
                          </div>
                          <ArrowUpRight size={15} />
                        </button>
                      ))}
                    </div>
                  </section>
                  <section className="panel recent-panel">
                    <div className="panel-heading">
                      <div>
                        <h3>Últimos movimientos</h3>
                        <p>El detalle detrás de tus números</p>
                      </div>
                      <button
                        className="text-button"
                        onClick={() => nav("movements")}
                      >
                        Ver todos
                        <ArrowRight size={15} />
                      </button>
                    </div>
                    {summary?.recent.length ? (
                      <MovementTable
                        rows={summary.recent.slice(0, 5)}
                        onSelect={setDetail}
                        compact
                      />
                    ) : (
                      <div className="empty-state">
                        <span>
                          <FileSpreadsheet size={27} />
                        </span>
                        <h3>
                          Un libro claro empieza con el primer movimiento.
                        </h3>
                        <p>
                          Sube tu Excel para revisar la importación. Nada se
                          registra sin tu confirmación.
                        </p>
                        <button
                          className="button secondary"
                          onClick={() => setImportOpen(true)}
                        >
                          Importar mi Excel
                          <ArrowRight size={16} />
                        </button>
                      </div>
                    )}
                  </section>
                </>
              )}
              {view === "movements" && (
                <section className="panel movements-panel">
                  <div className="panel-heading">
                    <div>
                      <h3>
                        {evidence
                          ? "Respaldo de la consulta"
                          : "Libro de movimientos"}
                      </h3>
                      <p>
                        {evidence
                          ? `${evidence.filters.category || "Todas las categorías"} · ${evidence.filters.month ? monthName(evidence.filters.month) : "Todo el historial"} · ${evidence.totals.count} registros`
                          : `${total} movimientos encontrados`}
                      </p>
                    </div>
                    {evidence ? (
                      <button
                        className="text-button"
                        onClick={() => setEvidence(null)}
                      >
                        <X size={15} />
                        Quitar respaldo
                      </button>
                    ) : (
                      <a
                        className="button secondary small-button"
                        href={`/api/export?${exportQ}`}
                      >
                        <Download size={15} />
                        Exportar
                      </a>
                    )}
                  </div>
                  {!evidence && (
                    <div className="table-filters">
                      <div className="search-input">
                        <Search size={16} />
                        <input
                          placeholder="Buscar concepto, proveedor o folio…"
                          aria-label="Buscar movimientos"
                          value={search}
                          onChange={(e) => setSearch(e.target.value)}
                        />
                      </div>
                      <label className="select-wrap">
                        <ListFilter size={15} />
                        <select
                          value={category}
                          aria-label="Categoría"
                          onChange={(e) => setCategory(e.target.value)}
                        >
                          <option value="">Todas las categorías</option>
                          {meta?.categories.map((c) => (
                            <option key={c}>{c}</option>
                          ))}
                        </select>
                      </label>
                    </div>
                  )}
                  {loading ? (
                    <div className="loading-state">
                      <LoaderCircle size={22} className="spin" />
                      Consultando movimientos…
                    </div>
                  ) : rows.length ? (
                    <MovementTable rows={rows} onSelect={setDetail} />
                  ) : (
                    <div className="empty-state">
                      <Search size={30} />
                      <h3>No hay movimientos con esos filtros.</h3>
                      <p>Prueba otro periodo o importa tu libro de trabajo.</p>
                      <button
                        className="button secondary"
                        onClick={() => {
                          setMonth("");
                          setAccount("");
                          setCategory("");
                          setSearch("");
                          setEvidence(null);
                        }}
                      >
                        Ver todo el historial
                      </button>
                    </div>
                  )}
                  <div className="pagination">
                    <span>
                      {total
                        ? `${(page - 1) * 25 + 1}–${Math.min(page * 25, total)} de ${total}`
                        : "0 movimientos"}
                    </span>
                    <div>
                      <button
                        className="icon-button"
                        disabled={page === 1}
                        onClick={() => setPage((p) => p - 1)}
                        aria-label="Página anterior"
                      >
                        <ChevronLeft size={17} />
                      </button>
                      <span>{page}</span>
                      <button
                        className="icon-button"
                        disabled={page * 25 >= total}
                        onClick={() => setPage((p) => p + 1)}
                        aria-label="Página siguiente"
                      >
                        <ChevronRight size={17} />
                      </button>
                    </div>
                  </div>
                </section>
              )}
              {view === "pending" && (
                <section className="panel">
                  <div className="panel-heading">
                    <div>
                      <h3>Propuestas pendientes</h3>
                      <p>
                        Ninguna propuesta modifica tus cifras hasta confirmarla.
                      </p>
                    </div>
                    <span className="count-badge">{pending.length}</span>
                  </div>
                  {!pending.length ? (
                    <div className="empty-state">
                      <span>
                        <CheckCheck size={28} />
                      </span>
                      <h3>Todo al día.</h3>
                      <p>
                        Las importaciones y los registros preparados por el
                        agente aparecerán aquí.
                      </p>
                    </div>
                  ) : (
                    <div className="pending-list">
                      {pending.map((p) => (
                        <button
                          className="pending-item"
                          key={p.id}
                          onClick={() => setProposal(p)}
                        >
                          <span className="pending-icon">
                            {p.kind === "import" ? (
                              <FileSpreadsheet size={22} />
                            ) : (
                              <Sparkles size={22} />
                            )}
                          </span>
                          <div>
                            <strong>
                              {p.payload.filename ||
                                p.payload.movements[0]?.description ||
                                "Nuevo movimiento"}
                            </strong>
                            <small>
                              {p.payload.movements.length} registros ·{" "}
                              {new Date(p.created_at).toLocaleString("es-MX")} ·
                              Pendiente
                            </small>
                          </div>
                          <span className="text-button">
                            Revisar
                            <ArrowRight size={16} />
                          </span>
                        </button>
                      ))}
                    </div>
                  )}
                </section>
              )}
              {view === "agents" && (
                <>
                  <section className="agents-hero">
                    <span className="hero-sparkle">
                      <Sparkles size={31} />
                    </span>
                    <span className="eyebrow">INTELIGENCIA CON RESPALDO</span>
                    <h2>
                      Más claridad.
                      <br />
                      Menos captura manual.
                    </h2>
                    <p>
                      Agentes especializados que trabajan sobre tu libro.
                      <br />
                      Cada cambio pasa por ti y cada cifra tiene un origen.
                    </p>
                    <div className="hero-tags">
                      <span>
                        <ShieldCheck size={14} />
                        Confirmación humana
                      </span>
                      <span>
                        <FolderCheck size={14} />
                        Datos verificables
                      </span>
                    </div>
                  </section>
                  <div className="agent-description-grid">
                    <section className="panel specialist">
                      <span className="stat-icon green">
                        <ChartNoAxesCombined size={22} />
                      </span>
                      <h3>Agente analista</h3>
                      <p>
                        Entiende tu pregunta, consulta los movimientos
                        confirmados y solicita al sistema el cálculo de totales.
                      </p>
                      <span className="specialist-rule">
                        <Check size={14} />
                        Consulta sin modificar registros
                      </span>
                    </section>
                    <section className="panel specialist">
                      <span className="stat-icon blue">
                        <CirclePlus size={22} />
                      </span>
                      <h3>Agente de captura</h3>
                      <p>
                        Convierte lo que escribes en una propuesta estructurada.
                        Si faltan datos, te pregunta antes de continuar.
                      </p>
                      <span className="specialist-rule">
                        <Check size={14} />
                        Siempre requiere tu confirmación
                      </span>
                    </section>
                  </div>
                  <div className="notice">
                    <ShieldCheck size={18} />
                    <span>
                      Los agentes reciben tus instrucciones y los datos
                      necesarios para responder a través de OpenAI. Tu libro y
                      los archivos originales permanecen en este equipo.
                    </span>
                  </div>
                </>
              )}
              <footer className="page-footer">
                <span>Folio · Finanzas con respaldo</span>
                <span>
                  <ShieldCheck size={12} />
                  MXN · Un negocio, una fuente de verdad
                </span>
              </footer>
            </div>
            <AgentPanel
              health={health}
              month={month}
              account={account}
              onProposal={async (p) => {
                try {
                  setProposal(await api<Proposal>(`/api/proposals/${p.id}`));
                } catch (e) {
                  setError((e as Error).message);
                }
              }}
              onEvidence={showEvidence}
              onPending={refresh}
              onHelp={() => setHelp(true)}
            />
          </div>
        </main>
      </div>
      {toast && (
        <div className="toast" role="status">
          <CheckCheck size={18} />
          {toast}
          <button
            className="icon-button"
            onClick={() => setToast("")}
            aria-label="Cerrar aviso"
          >
            <X size={15} />
          </button>
        </div>
      )}
      <input
        ref={fileInput}
        type="file"
        accept=".xlsx"
        className="sr-only"
        onChange={(e) => void upload(e.target.files?.[0])}
      />
      {importOpen && (
        <Modal
          title="Conecta tu libro de trabajo"
          subtitle="Importa tu Excel y revisa los movimientos antes de guardarlos."
          onClose={() => !busy && setImportOpen(false)}
        >
          <button
            className="upload-drop"
            disabled={busy}
            onClick={() =>
              health?.demo_mode
                ? void localImport()
                : fileInput.current?.click()
            }
          >
            <span className="upload-icon">
              {busy ? (
                <LoaderCircle size={30} className="spin" />
              ) : (
                <FileSpreadsheet size={30} />
              )}
            </span>
            <strong>
              {busy
                ? "Preparando la vista previa…"
                : health?.demo_mode
                  ? "Cargar movimientos ficticios"
                  : "Selecciona tu archivo Excel"}
            </strong>
            <span>
              {health?.demo_mode
                ? "24 movimientos de ejemplo · Sin datos reales"
                : "Formato .xlsx · Hasta 15 MB"}
            </span>
            <small>Efectivo · Banco · Tarjeta BBVA</small>
          </button>
          {meta?.local_workbook_available && !health?.demo_mode && (
            <button
              className="local-file-button"
              onClick={() => void localImport()}
              disabled={busy}
            >
              <FileSpreadsheet size={22} />
              <span>
                <strong>Cargar ejemplo ficticio</strong>
                <small>movimientos-demo.json · Datos ficticios</small>
              </span>
              <ArrowRight size={18} />
            </button>
          )}
          <div className="notice">
            <ShieldCheck size={18} />
            <span>
              Se conserva el archivo original. La importación muestra errores y
              duplicados antes de pedirte confirmación.
            </span>
          </div>
        </Modal>
      )}
      {proposal && (
        <ProposalModal
          key={proposal.id}
          proposal={proposal}
          onClose={() => setProposal(null)}
          onDone={done}
          onDetail={setDetail}
        />
      )}
      {manual && (
        <ManualModal
          meta={meta}
          onClose={() => setManual(false)}
          onCreated={(p) => {
            setManual(false);
            setProposal(p);
            refresh();
          }}
        />
      )}
      {detail && (
        <Modal
          title="Detalle del movimiento"
          subtitle="El respaldo de tu libro financiero."
          onClose={() => setDetail(null)}
        >
          <div
            className={`detail-amount ${detail.amount_minor > 0 ? "positive" : ""}`}
          >
            {detail.amount_minor > 0 ? "+" : "−"}
            {money(Math.abs(detail.amount_minor))}
            <small>MXN · {detail.kind}</small>
          </div>
          <dl className="detail-list">
            {Object.entries({
              Concepto: detail.description,
              Fecha: detail.date,
              Cuenta: accountName[detail.account],
              Categoría: detail.category,
              Tratamiento: treatmentName[detail.treatment],
              Referencia: detail.reference || "Sin referencia",
              Propiedad: detail.property || "Sin propiedad asociada",
              "Archivo de origen":
                detail.source_file || "Registro preparado por el agente",
              Ubicación: detail.source_sheet
                ? `${detail.source_sheet} · fila ${detail.source_row}`
                : "Captura manual",
              Estado: detail.id
                ? "Confirmado · sin conciliación bancaria"
                : "Propuesta pendiente",
            }).map(([k, v]) => (
              <div key={k}>
                <dt>{k}</dt>
                <dd>{v}</dd>
              </div>
            ))}
          </dl>
        </Modal>
      )}
      {help && (
        <Modal
          title="Tu conexión, bajo control"
          subtitle="Folio corre localmente en tu equipo."
          onClose={() => setHelp(false)}
        >
          <div className="connection-box">
            <span
              className={`status-dot ${health?.ai_configured ? "" : "offline"}`}
            />
            <strong>
              {health?.ai_configured
                ? "OpenAI configurado en el backend"
                : "OpenAI pendiente en este proceso"}
            </strong>
          </div>
          <p className="help-copy">
            {health?.ai_configured
              ? "Los agentes están conectados al servicio de OpenAI. Los importes se calculan en el backend y cualquier registro requiere confirmación."
              : "Tu clave está disponible únicamente en la terminal donde la ingresaste. Para conectar los agentes, inicia la app desde esa misma terminal:"}
          </p>
          {!health?.ai_configured && (
            <pre className="command-box">
              cd /ruta/a/folio-finanzas{`\n`}./start.sh
            </pre>
          )}
          <p className="help-copy">
            El importador lee las hojas de efectivo, banco y tarjeta del
            Balance. Los estados de cuenta PDF, Telegram y facturación quedan
            para la siguiente etapa.
          </p>
          <div className="notice">
            <ShieldCheck size={18} />
            <span>
              Importar y confirmar no equivale a conciliar con el banco. Un
              periodo sin movimientos no demuestra que no hubo gastos.
            </span>
          </div>
          <button
            className="button primary full-width"
            onClick={() => {
              refresh();
              setHelp(false);
            }}
          >
            Comprobar conexión
            <ArrowRight size={16} />
          </button>
        </Modal>
      )}
    </div>
  );
}
