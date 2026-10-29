import { useState } from "react";
import { Check, LoaderCircle, X } from "lucide-react";
import { api } from "./api";
import type { ImportError, Proposal } from "./types";

export default function ImportCorrection({
  error,
  proposal,
  onSaved,
  onCancel,
}: {
  error: ImportError;
  proposal: Proposal;
  onSaved: (p: Proposal) => void;
  onCancel: () => void;
}) {
  const draft = error.draft!;
  const isDocument = !!proposal.payload.document;
  const [form, setForm] = useState({
    ...draft,
    amount:
      draft.amount_minor == null ? "" : (draft.amount_minor / 100).toFixed(2),
    reason: "",
  });
  const [busy, setBusy] = useState(false),
    [failure, setFailure] = useState("");
  const update = (key: string, value: string) =>
    setForm((f) => ({ ...f, [key]: value }));
  return (
    <form
      className="manual-form correction-form"
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        setFailure("");
        try {
          if (!/^\d+(\.\d{1,2})?$/.test(form.amount))
            throw new Error(
              "Escribe un importe positivo con hasta dos decimales.",
            );
          const [a, b = ""] = form.amount.split(".");
          const p = await api<Proposal>(
            `/api/proposals/${proposal.id}/corrections`,
            {
              method: "POST",
              body: JSON.stringify({
                sheet: error.sheet,
                row: error.row,
                reason: form.reason,
                movement: {
                  ...form,
                  amount_minor: Number(a) * 100 + Number(b.padEnd(2, "0")),
                },
              }),
            },
          );
          onSaved(p);
        } catch (e) {
          setFailure((e as Error).message);
        } finally {
          setBusy(false);
        }
      }}
    >
      <div className="panel-heading">
        <div>
          <h3>
            Revisar {isDocument ? "registro" : "fila"} {error.row}
          </h3>
          <p>
            {error.sheet} · {error.message}
          </p>
        </div>
        <button
          className="icon-button"
          type="button"
          onClick={onCancel}
          aria-label="Cancelar corrección"
        >
          <X size={18} />
        </button>
      </div>
      <div className="notice">
        La corrección se aplica solo a esta propuesta y conserva el origen y el
        motivo. El archivo original permanece intacto.
      </div>
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
          Tipo
          <select
            value={form.kind}
            onChange={(e) => update("kind", e.target.value)}
          >
            {(draft.account === "tarjeta_bbva"
              ? ["cargo", "pago", "interes", "comision", "abono", "devolucion"]
              : ["ingreso", "egreso"]
            ).map((k) => (
              <option key={k}>{k}</option>
            ))}
          </select>
        </label>
      </div>
      {isDocument && (
        <p className="warning-text">
          Confirma que el importe está expresado en MXN. Verifica la moneda y
          los datos contra el documento original antes de guardar la corrección.
        </p>
      )}
      {isDocument && (
        <div className="form-grid">
          <label>
            Referencia / proveedor
            <input
              value={form.reference || ""}
              onChange={(e) => update("reference", e.target.value)}
              maxLength={300}
            />
          </label>
          <label>
            Folio de propiedad
            <input
              value={form.property || ""}
              onChange={(e) => update("property", e.target.value)}
              maxLength={100}
            />
          </label>
        </div>
      )}
      <label>
        Descripción
        <input
          value={form.description}
          onChange={(e) => update("description", e.target.value)}
          required
        />
      </label>
      <div className="form-grid">
        <label>
          Importe MXN
          <input
            inputMode="decimal"
            value={form.amount}
            placeholder="Verifica el importe en tu documentación"
            onChange={(e) => update("amount", e.target.value)}
            required
          />
        </label>
        <label>
          Categoría
          <select
            value={form.category}
            onChange={(e) => update("category", e.target.value)}
          >
            {[
              ...new Set([
                ...(proposal.payload.categories || []),
                "Por revisar",
              ]),
            ].map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
      </div>
      <label>
        Motivo de la corrección
        <input
          value={form.reason}
          maxLength={1000}
          placeholder="Indica qué verificaste y por qué lo corriges"
          onChange={(e) => update("reason", e.target.value)}
          required
        />
      </label>
      {failure && (
        <div className="error-box" role="alert">
          {failure}
        </div>
      )}
      <div className="modal-footer">
        <button className="button secondary" type="button" onClick={onCancel}>
          Cancelar
        </button>
        <button className="button primary" disabled={busy}>
          {busy ? (
            <LoaderCircle className="spin" size={16} />
          ) : (
            <Check size={16} />
          )}
          Guardar en la propuesta
        </button>
      </div>
    </form>
  );
}
