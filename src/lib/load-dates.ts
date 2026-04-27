/**
 * Load show dates from the Google Sheet CSV at build time.
 * - Throws if DATES_CSV_URL is missing or fetch fails (build fails intentionally).
 * - Skips invalid rows with a console warning (other rows still rendered).
 */

export type DateEntry = {
  date: string;             // YYYY-MM-DD
  ville: string;
  lieu: string;
  heure: string;            // empty string if absent
  prix: string;             // empty string if absent
  lien_reservation: string; // empty string if absent
};

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
const URL_RE = /^https?:\/\//;

/** Minimal RFC 4180 CSV parser (handles quoted fields with commas/quotes/newlines). */
function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = '';
  let inQuotes = false;
  let i = 0;
  while (i < text.length) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"') {
        if (text[i + 1] === '"') { field += '"'; i += 2; continue; }
        inQuotes = false; i++; continue;
      }
      field += c; i++;
      continue;
    }
    if (c === '"') { inQuotes = true; i++; continue; }
    if (c === ',') { row.push(field); field = ''; i++; continue; }
    if (c === '\n' || c === '\r') {
      row.push(field); field = '';
      if (row.length > 1 || row[0] !== '') rows.push(row);
      row = [];
      if (c === '\r' && text[i + 1] === '\n') i += 2; else i++;
      continue;
    }
    field += c; i++;
  }
  if (field !== '' || row.length > 0) { row.push(field); rows.push(row); }
  return rows;
}

function validate(row: Record<string, string>): DateEntry | null {
  const date = (row.date ?? '').trim();
  if (!DATE_RE.test(date)) return null;
  if (Number.isNaN(new Date(date).getTime())) return null;
  const ville = (row.ville ?? '').trim();
  const lieu = (row.lieu ?? '').trim();
  if (!ville || !lieu) return null;
  const lien = (row.lien_reservation ?? '').trim();
  if (lien && !URL_RE.test(lien)) return null;
  return {
    date,
    ville,
    lieu,
    heure: (row.heure ?? '').trim(),
    prix: (row.prix ?? '').trim(),
    lien_reservation: lien,
  };
}

export async function loadDates(): Promise<{ upcoming: DateEntry[]; past: DateEntry[] }> {
  // Vite (astro dev) injects via import.meta.env from .env file.
  // CI build (npm run build) gets it from the shell env via process.env.
  const url = import.meta.env.DATES_CSV_URL ?? process.env.DATES_CSV_URL;
  if (!url) throw new Error('DATES_CSV_URL not set');

  const res = await fetch(url);
  if (!res.ok) throw new Error(`CSV fetch failed: ${res.status} ${res.statusText}`);

  const text = await res.text();
  const rows = parseCsv(text);
  if (rows.length === 0) throw new Error('CSV is empty');

  const [header, ...dataRows] = rows;
  const fields = header.map(h => h.trim());

  const valid: DateEntry[] = [];
  for (const cells of dataRows) {
    const obj = Object.fromEntries(fields.map((k, i) => [k, cells[i] ?? '']));
    const entry = validate(obj);
    if (entry) valid.push(entry);
    else console.warn('[dates] skipped invalid row:', obj);
  }

  // Date du jour J = upcoming jusqu'à minuit inclus (decision verrouillée)
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const upcoming = valid
    .filter(d => new Date(d.date) >= today)
    .sort((a, b) => a.date.localeCompare(b.date));

  const past = valid
    .filter(d => new Date(d.date) < today)
    .sort((a, b) => b.date.localeCompare(a.date));

  return { upcoming, past };
}

export function formatDate(iso: string): string {
  const [y, m, d] = iso.split('-');
  return `${d}.${m}.${y}`;
}
