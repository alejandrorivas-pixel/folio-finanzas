import { useRef, useState } from "react";
import {
  FileImage,
  FileSpreadsheet,
  FileText,
  LoaderCircle,
  ShieldCheck,
} from "lucide-react";
import { accountName, api } from "./api";
import type { Proposal } from "./types";

type Format = "excel" | "pdf" | "image";
const formats = [
  { id: "excel" as const, label: "Excel", icon: FileSpreadsheet },
  { id: "pdf" as const, label: "PDF", icon: FileText },
  { id: "image" as const, label: "Captura / foto", icon: FileImage },
];

export default function ImportIntake({
  demoMode,
  aiConfigured,
  initialAccount,
  onCreated,
  onBusy,
}: {
  demoMode: boolean;
  aiConfigured: boolean;
  initialAccount: string;
  onCreated: (proposal: Proposal) => void;
  onBusy: (busy: boolean) => void;
}) {
  const [format, setFormat] = useState<Format>("excel");
  const [account, setAccount] = useState(initialAccount || "banco");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const isDocument = format !== "excel";
  const Icon = formats.find((option) => option.id === format)!.icon;

  const prepare = async (file?: File) => {
    setError("");
    if (!demoMode && !file) return;
    if (file) {
      const allowed =
        format === "excel"
          ? /\.xlsx$/i
          : format === "pdf"
            ? /\.pdf$/i
            : /\.(png|jpe?g|webp)$/i;
      if (!allowed.test(file.name)) {
        setError("El archivo no corresponde al formato seleccionado.");
        return;
      }
      if (file.size > (isDocument ? 10 : 15) * 1024 * 1024) {
        setError(`El archivo supera el límite de ${isDocument ? 10 : 15} MB.`);
        return;
      }
    }
    setBusy(true);
    onBusy(true);
    try {
      let proposal: Proposal;
      if (demoMode) {
        proposal = await api<Proposal>(
          isDocument
            ? "/api/imports/document-demo"
            : "/api/imports/local-preview",
          {
            method: "POST",
            body: JSON.stringify(isDocument ? { format, account } : {}),
          },
        );
      } else {
        const data = new FormData();
        data.append("file", file!);
        if (isDocument) data.append("account", account);
        proposal = await api<Proposal>(
          isDocument ? "/api/imports/document-preview" : "/api/imports/preview",
          {
            method: "POST",
            body: data,
          },
        );
      }
      onCreated(proposal);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      onBusy(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  return (
    <div className="import-intake">
      <div
        className="intake-formats"
        role="group"
        aria-label="Formato de importación"
      >
        {formats.map((option) => (
          <button
            key={option.id}
            type="button"
            className={format === option.id ? "active" : ""}
            aria-pressed={format === option.id}
            disabled={busy}
            onClick={() => {
              setFormat(option.id);
              setError("");
            }}
          >
            <option.icon size={18} />
            {option.label}
          </button>
        ))}
      </div>
      {isDocument && (
        <label className="intake-account">
          Cuenta de estos movimientos
          <select
            value={account}
            disabled={busy}
            onChange={(e) => setAccount(e.target.value)}
          >
            {Object.entries(accountName).map(([id, label]) => (
              <option key={id} value={id}>
                {label}
              </option>
            ))}
          </select>
          <small>Importa un documento de una sola cuenta a la vez.</small>
        </label>
      )}
      <div className="notice intake-disclosure">
        <ShieldCheck size={18} />
        <span>
          {demoMode
            ? "Modo demostración: solo cargamos ejemplos inventados. No se abre ningún archivo tuyo ni se envía información a OpenAI."
            : isDocument
              ? "Al seleccionar un archivo, se enviará a OpenAI para leer los movimientos. Revisa las fechas, importes y categorías de la propuesta antes de confirmar."
              : "El Excel se lee en este equipo. Revisa las filas y los duplicados antes de confirmar la importación."}
        </span>
      </div>
      {!demoMode && isDocument && !aiConfigured && (
        <p className="warning-text">
          Conecta OpenAI en el backend para leer PDF y capturas. La importación
          de Excel sigue disponible.
        </p>
      )}
      <input
        ref={fileInput}
        type="file"
        className="sr-only"
        aria-label="Archivo para importar"
        accept={
          format === "excel"
            ? ".xlsx"
            : format === "pdf"
              ? ".pdf,application/pdf"
              : ".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp"
        }
        disabled={busy || demoMode || (isDocument && !aiConfigured)}
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          void prepare(file);
        }}
      />
      <button
        type="button"
        className="upload-drop"
        disabled={busy || (!demoMode && isDocument && !aiConfigured)}
        onClick={() => (demoMode ? void prepare() : fileInput.current?.click())}
      >
        <span className="upload-icon">
          {busy ? (
            <LoaderCircle size={30} className="spin" />
          ) : (
            <Icon size={30} />
          )}
        </span>
        <strong>
          {busy
            ? "Preparando la propuesta…"
            : demoMode
              ? `Probar ${format === "excel" ? "Excel ficticio" : format === "pdf" ? "PDF ficticio" : "captura ficticia"}`
              : `Seleccionar ${format === "excel" ? "Excel" : format === "pdf" ? "PDF" : "captura o foto"}`}
        </strong>
        <span>
          {demoMode
            ? "Ejemplo de demostración · Datos inventados"
            : format === "excel"
              ? ".xlsx · Hasta 15 MB"
              : format === "pdf"
                ? ".pdf · Hasta 10 MB"
                : ".png, .jpg, .webp · Hasta 10 MB"}
        </span>
        <small>
          {isDocument
            ? "Cada movimiento conservará su referencia al documento."
            : "Efectivo · Banco · Tarjeta BBVA"}
        </small>
      </button>
      {error && (
        <p className="error-box" role="alert">
          {error}
        </p>
      )}
      <p className="intake-footnote">
        Primero verás una propuesta. Los saldos cambian únicamente cuando
        confirmas.
      </p>
    </div>
  );
}
