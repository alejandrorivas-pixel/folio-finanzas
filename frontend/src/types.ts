export type Movement = {
  id?: string;
  date: string;
  account: string;
  kind: string;
  category: string;
  description: string;
  amount_minor: number;
  currency: string;
  reference?: string | null;
  property?: string | null;
  treatment: string;
  source_file?: string | null;
  source_sheet?: string | null;
  source_row?: number | null;
  duplicate?: boolean;
};
export type Account = {
  id: string;
  name: string;
  kind: string;
  opening_minor: number | null;
  balance_minor?: number | null;
  count?: number;
};
export type Totals = {
  income_minor: number;
  expense_minor: number;
  operating_net_minor: number;
  inflow_minor: number;
  outflow_minor: number;
  count: number;
  excluded_count: number;
};
export type Summary = Totals & {
  accounts: Account[];
  net_position_minor: number | null;
  categories: { name: string; amount_minor: number }[];
  daily: { date: string; income_minor: number; expense_minor: number }[];
  recent: Movement[];
  month: string | null;
  review_count: number;
  unreconciled_count: number;
};
export type Proposal = {
  id: string;
  kind: string;
  status: string;
  created_at: string;
  payload: {
    movements: Movement[];
    stats?: {
      total: number;
      new: number;
      duplicates: number;
      errors: number;
      review: number;
      accounts: Record<string, number>;
    };
    errors: ImportError[];
    categories?: string[];
    corrections?: { sheet: string; row: number; reason: string }[];
    notes: string[];
    filename?: string;
    document?: { mime: string; pages: number; account: string; model: string };
    openings: { account: string; amount_minor: number; source: string }[];
  };
};
export type Meta = {
  accounts: Account[];
  categories: string[];
  months: string[];
  count: number;
  pending: number;
  local_workbook_available: boolean;
  demo_mode: boolean;
  company_name: string;
};
export type ImportError = {
  sheet: string;
  row: number;
  message: string;
  draft?: {
    date: string;
    account: string;
    kind: string;
    category: string;
    description: string;
    amount_minor: number | null;
    reference: string | null;
    property: string | null;
  };
};
export type Evidence = {
  filters: {
    month: string | null;
    account: string | null;
    category: string | null;
    search: string | null;
    operating_only: boolean;
  };
  totals: Totals;
  movement_ids: string[];
};
export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  evidence?: Evidence[];
  proposal?: Proposal | null;
  mode?: string;
};
