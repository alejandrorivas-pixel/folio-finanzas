export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  if (import.meta.env.VITE_DEMO === "true") {
    const { demoRequest } = await import("./demo");
    return demoRequest(path, options) as Promise<T>;
  }
  const response = await fetch(path, {
    ...options,
    headers:
      options.body instanceof FormData
        ? options.headers
        : { "Content-Type": "application/json", ...options.headers },
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "No se pudo completar la operación. Revisa los datos e inténtalo de nuevo.",
    );
  return data;
}
export const money = (cents: number | null | undefined) =>
  cents == null
    ? "Sin determinar"
    : new Intl.NumberFormat("es-MX", {
        style: "currency",
        currency: "MXN",
        maximumFractionDigits: 2,
      }).format(cents / 100);
export const monthName = (value: string) =>
  value
    ? new Intl.DateTimeFormat("es-MX", {
        month: "long",
        year: "numeric",
        timeZone: "UTC",
      }).format(new Date(`${value}-01T12:00:00Z`))
    : "Todo el historial";
export const dateName = (value: string) =>
  new Intl.DateTimeFormat("es-MX", {
    day: "2-digit",
    month: "short",
    timeZone: "UTC",
  }).format(new Date(`${value}T12:00:00Z`));
export const accountName: Record<string, string> = {
  efectivo: "Efectivo",
  banco: "Banco",
  tarjeta_bbva: "Tarjeta BBVA",
};
export const treatmentName: Record<string, string> = {
  operational: "Operativo",
  transfer: "Transferencia",
  card_payment: "Pago de tarjeta",
  custody: "En custodia",
  financing: "Financiamiento",
  por_revisar: "Por revisar",
};
