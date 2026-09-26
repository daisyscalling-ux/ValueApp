import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
//#region lib/quantum/financial-periods.ts
var number = (v) => typeof v === "number" && Number.isFinite(v) ? v : null;
var rows$1 = (v) => {
	const data = v?.data;
	return Array.isArray(data) ? data : [];
};
var text = (v) => typeof v === "string" ? v : "";
/** No cross-period cash flows or summed balance sheets. Missing is never zero. */
function mapPeriods(income, balance, cash, profit, type) {
	const match = (data, i, balanceSheet = false) => {
		const candidates = rows$1(data).filter((r) => r.period_end_date === i.period_end_date && r.currency === i.currency && (!r.symbol || !i.symbol || r.symbol === i.symbol) && (r.period_type === type || balanceSheet && type === "ttm" && ["quarterly", "annual"].includes(text(r.period_type))));
		candidates.sort((a, b) => Number(b.period_type === type) - Number(a.period_type === type));
		const result = {};
		for (const row of candidates) for (const [key, value] of Object.entries(row)) if (result[key] == null && value != null) result[key] = value;
		return result;
	};
	return rows$1(income).filter((i) => i.period_type === type && /^\d{4}-\d{2}-\d{2}$/.test(text(i.period_end_date))).map((i) => {
		const b = match(balance, i, true), c = match(cash, i), r = match(profit, i), notes = [];
		const op = number(c.cf_cash_from_oper), reportedFcf = number(c.cf_free_cash_flow), reportedFcff = number(c.cf_free_cash_flow_firm);
		const fixed = number(c.cf_purchase_of_fixed_prod_assets), intangibles = number(c.cf_acquisition_of_intang_assets);
		const capex = number(c.cf_cap_expenditures) ?? number(c.cf_acquis_fxd_and_intang_detailed) ?? (fixed !== null && intangibles !== null && fixed <= 0 && intangibles <= 0 ? fixed + intangibles : null);
		const computed = op !== null && capex !== null && capex <= 0 ? op + capex : null;
		const mismatch = computed !== null && reportedFcf !== null && Math.abs(computed - reportedFcf) > Math.max(1, Math.abs(op) * .01);
		if (op === null) notes.push("Cashflow ungeprueft: operativer Cashflow (cf_cash_from_oper) fehlt fuer diese Periode.");
		if (capex === null) notes.push("Cashflow ungeprueft: vollstaendige Investitionsausgaben fehlen; keine Gesamtsumme und keine zwei vollstaendigen Bestandteile.");
		if (capex !== null && capex > 0) notes.push("Cashflow ungeprueft: Investitionsausgaben haben ein positives Vorzeichen.");
		if (mismatch) notes.push("ROIC-Free-Cashflow weicht von operativem Cashflow plus Investitionsausgaben ab. FCF wurde nachvollziehbar neu berechnet.");
		const interest = number(i.is_int_expense), tax = number(r.eff_tax_rate) ?? number(i.eff_tax_rate);
		const fcff = (computed !== null && interest !== null && interest >= 0 && tax !== null && tax >= 0 && tax <= 100 ? computed + interest * (1 - tax / 100) : null) ?? (computed !== null && reportedFcf !== null && !mismatch ? reportedFcff : null);
		if (fcff === null) notes.push("FCFF nicht verifiziert: keine vollständige Überleitung für das berichtete DCF.");
		const short = number(b.bs_st_borrow), long = number(b.bs_lt_borrow), total = number(b.bs_total_equity), parent = number(b.bs_eqty_bef_minority_int_detailed);
		return {
			interestExpense: interest,
			effectiveTaxRate: tax,
			year: Number(i.fiscal_year),
			date: text(i.period_end_date),
			currency: text(i.currency),
			periodType: type,
			periodLabel: text(i.period_label),
			revenue: number(i.is_sales_revenue_turnover),
			ebitda: number(i.ebitda),
			ebit: number(i.ebit),
			netIncome: number(i.is_net_income),
			eps: number(i.diluted_eps),
			shares: number(i.is_sh_for_diluted_eps),
			fcf: computed,
			fcff,
			reportedFcf,
			reportedFcff,
			cashflowNotes: notes,
			cashflowVerified: fcff !== null,
			operatingCashFlow: op,
			capex,
			cash: number(b.bs_cash_near_cash_item),
			debt: short !== null && long !== null ? short + long : null,
			minorityInterest: number(b.bs_minority_noncontrolling_interest) ?? (total !== null && parent !== null && total >= parent ? total - parent : null),
			preferredEquity: number(b.bs_pfd_eqty_and_hybrid_cptl),
			equity: parent,
			currentRatio: number(b.cur_ratio) ?? (number(b.bs_cur_asset_report) !== null && number(b.bs_cur_liab) > 0 ? Number(b.bs_cur_asset_report) / Number(b.bs_cur_liab) : null),
			roic: number(r.return_on_inv_capital),
			grossMargin: number(i.gross_margin) ?? number(r.gross_margin),
			operatingMargin: number(i.oper_margin) ?? number(r.oper_margin),
			netMargin: number(i.profit_margin) ?? number(r.profit_margin) ?? (number(i.is_net_income) !== null && number(i.is_sales_revenue_turnover) > 0 ? Number(i.is_net_income) / Number(i.is_sales_revenue_turnover) * 100 : null)
		};
	}).sort((a, b) => b.date.localeCompare(a.date));
}
function choosePeriods(annual, ttm) {
	const latest = ttm.find((f) => f.revenue !== null && f.eps !== null && f.shares !== null && f.shares > 0);
	return latest && (!annual[0] || latest.date >= annual[0].date) ? [latest, ...annual] : annual;
}
//#endregion
//#region lib/quantum/analysis.ts
var valid = (n) => typeof n === "number" && Number.isFinite(n);
//#endregion
//#region lib/quantum/request-budget.ts
/** One paced, rolling-minute budget per provider key in this server process. */
var RequestBudget = class {
	constructor(limit = 270, now = () => Date.now(), sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))) {
		this.limit = limit;
		this.now = now;
		this.sleep = sleep;
		this.chain = Promise.resolve();
		this.starts = [];
		this.next = 0;
		this.blockedUntil = 0;
		this.queued = 0;
	}
	trim() {
		const cutoff = this.now() - 6e4;
		this.starts = this.starts.filter((t) => t > cutoff);
	}
	pause(seconds) {
		this.blockedUntil = Math.max(this.blockedUntil, this.now() + seconds * 1e3);
	}
	status() {
		this.trim();
		return {
			limit: this.limit,
			accountLimit: 300,
			used: this.starts.length,
			queued: this.queued,
			waitSeconds: Math.max(0, Math.ceil((this.blockedUntil - this.now()) / 1e3))
		};
	}
	async reserve(deadline = Infinity) {
		this.queued++;
		const turn = this.chain.then(async () => {
			for (;;) {
				this.trim();
				if (this.now() >= deadline) throw new Error("Request deadline exceeded");
				const gate = Math.max(this.next, this.blockedUntil, this.starts.length >= this.limit ? this.starts[0] + 6e4 : 0);
				if (gate >= deadline) throw new Error("Request deadline exceeded");
				const delay = gate - this.now();
				if (delay <= 0) break;
				await this.sleep(delay);
			}
			const time = this.now();
			this.starts.push(time);
			this.next = time + Math.ceil(6e4 / this.limit);
			return time;
		});
		this.chain = turn.then(() => {}, () => {});
		try {
			return await turn;
		} finally {
			this.queued--;
		}
	}
};
var budgets = /* @__PURE__ */ new Map();
function budgetFor(keyHash) {
	let budget = budgets.get(keyHash);
	if (!budget) {
		budget = new RequestBudget();
		budgets.set(keyHash, budget);
	}
	return budget;
}
//#endregion
//#region lib/quantum/roic.ts
var DataError = class extends Error {
	constructor(message, status = 502, retryAfter = 0) {
		super(message);
		this.status = status;
		this.retryAfter = retryAfter;
	}
};
var object = (v) => v && typeof v === "object" && !Array.isArray(v) ? v : {};
var rows = (v) => {
	const a = Array.isArray(v) ? v : object(v).data;
	return Array.isArray(a) ? a.map(object) : [];
};
var n = (v) => valid(v) ? v : null;
var s = (v, otherwise = "") => typeof v === "string" ? v : otherwise;
var safeLink = (v) => {
	try {
		const u = new URL(String(v));
		return ["https:", "http:"].includes(u.protocol) ? u.href : "";
	} catch {
		return "";
	}
};
var cache = /* @__PURE__ */ new Map();
var cooldown = /* @__PURE__ */ new Map();
var flights = /* @__PURE__ */ new Map();
async function fingerprint(key) {
	return Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(key)))).map((n) => n.toString(16).padStart(2, "0")).join("");
}
var RoicClient = class {
	constructor(key, fetcher = (...args) => fetch(...args), expiresAt = Infinity) {
		this.fetcher = fetcher;
		this.expiresAt = expiresAt;
		this.deadline = Infinity;
		this.key = key.trim();
		this.hash = fingerprint(this.key);
	}
	async budget() {
		return budgetFor(await this.hash).status();
	}
	async get(path, ttl = 9e5, refresh = false) {
		if (Date.now() >= this.expiresAt) {
			this.key = "";
			throw new DataError("Die lokale ROIC-Sitzung ist abgelaufen. Bitte neu verbinden und den Scan fortsetzen.", 401);
		}
		const url = new URL(path, "https://api.roic.ai");
		if (url.origin !== "https://api.roic.ai" || !/^\/(v3\.0\.0|v2)\//.test(url.pathname) || url.username || url.password || url.searchParams.has("apikey")) throw new DataError("Ungültiger Datenpfad", 400);
		const hash = await this.hash, id = hash + url.href;
		const saved = cache.get(id);
		if (!refresh && saved && saved.expires > Date.now()) return saved.data;
		if (flights.has(id)) return flights.get(id);
		const until = cooldown.get(hash) ?? 0;
		if (until > Date.now()) throw new DataError("ROIC-Anfragelimit erreicht. Bitte nach der Wartezeit erneut laden.", 429, Math.ceil((until - Date.now()) / 1e3));
		const pending = (async () => {
			const budget = budgetFor(hash);
			try {
				await budget.reserve(this.deadline);
			} catch {
				throw new DataError("ROIC-Abruf wegen Wartezeit beendet. Bitte erneut laden.", 504);
			}
			if (Date.now() >= this.expiresAt) {
				this.key = "";
				throw new DataError("Die lokale ROIC-Sitzung ist abgelaufen. Bitte neu verbinden und den Scan fortsetzen.", 401);
			}
			let response;
			const requestUrl = new URL(url);
			const headers = { Accept: "application/json" };
			if (!/^[\x21-\x7e]{8,512}$/.test(this.key)) throw new DataError("Der gespeicherte ROIC-API-Schlüssel enthält ungültige Zeichen. Bitte das Cloudflare-Secret neu setzen.", 500);
			if (requestUrl.pathname.startsWith("/v2/")) requestUrl.searchParams.set("apikey", this.key);
			else headers.Authorization = `Bearer ${this.key}`;
			try {
				let current = requestUrl;
				for (let redirects = 0;; redirects++) {
					response = await this.fetcher(current.href, {
						headers,
						signal: AbortSignal.timeout(Math.max(1, Math.min(2e4, this.deadline - Date.now()))),
						redirect: "manual"
					});
					if (![
						301,
						302,
						303,
						307,
						308
					].includes(response.status)) break;
					const location = response.headers.get("Location");
					if (!location || redirects >= 2) throw new DataError("ROIC hat zu oft weitergeleitet.", 502);
					const next = new URL(location, current);
					if (next.origin !== "https://api.roic.ai") throw new DataError("ROIC hat auf einen nicht vertrauenswürdigen Server weitergeleitet.", 502);
					current = next;
				}
			} catch (error) {
				if (error instanceof DataError) throw error;
				const name = error instanceof Error ? error.name : "";
				if (name === "AbortError" || name === "TimeoutError") throw new DataError("ROIC hat innerhalb von 20 Sekunden nicht geantwortet.", 504);
				throw new DataError("Cloudflare konnte keine Verbindung zur ROIC-API herstellen.", 502);
			}
			if (!response.ok) {
				if (response.status === 429) {
					const raw = response.headers.get("Retry-After") ?? "60";
					const seconds = Math.max(1, Number(raw) || Math.ceil((Date.parse(raw) - Date.now()) / 1e3) || 60);
					cooldown.set(hash, Date.now() + seconds * 1e3);
					budget.pause(seconds);
					throw new DataError("ROIC-Anfragelimit erreicht. Die Daten wurden nicht ersetzt.", 429, seconds);
				}
				throw new DataError(response.status === 401 ? "ROIC hat den API-Schlüssel abgelehnt." : [402, 403].includes(response.status) ? "Dieser ROIC-Datenpunkt ist für deinen Tarif nicht freigeschaltet." : response.status === 404 ? "Für diesen Datenpunkt liegen keine ROIC-Daten vor." : `ROIC-Datenabruf fehlgeschlagen (HTTP ${response.status}).`, [
					400,
					401,
					402,
					403,
					404,
					422
				].includes(response.status) ? response.status : 502);
			}
			const data = await response.json().catch(() => {
				throw new DataError("Ungültige Antwort von ROIC.");
			});
			if (cache.size >= 300) cache.delete(cache.keys().next().value);
			cache.set(id, {
				data,
				expires: Date.now() + ttl
			});
			return data;
		})();
		flights.set(id, pending);
		try {
			return await pending;
		} finally {
			flights.delete(id);
		}
	}
	async search(query) {
		const attempts = await Promise.allSettled(["symbol", "name"].map((by) => this.get(`/v3.0.0/tickers/search?query=${encodeURIComponent(query)}&search_by=${by}&limit=12`, 36e5)));
		const denied = attempts.find((r) => r.status === "rejected" && r.reason instanceof DataError && [
			401,
			403,
			429
		].includes(r.reason.status));
		if (denied?.status === "rejected") throw denied.reason;
		const results = attempts.flatMap((r) => r.status === "fulfilled" ? [r.value] : []);
		if (!results.length) {
			const failure = attempts[0];
			if (failure.status === "rejected") throw failure.reason;
		}
		return [...new Map(results.flatMap(rows).filter((t) => ["stock", "dr"].includes(s(t.type))).map((t) => [t.id ?? t.symbol, t])).values()].sort((a, b) => Number(b.is_primary) - Number(a.is_primary)).slice(0, 16);
	}
	async catalog(page, exchange, limit = 20, refresh = false) {
		if (!Number.isInteger(limit) || limit < 1 || limit > 2e3 || exchange && !/^[A-Za-z0-9._-]{1,30}$/.test(exchange)) throw new DataError("Ungültige Katalogauswahl", 400);
		let path = `/v3.0.0/tickers?type=stock&is_primary=true&status=listed&limit=${limit}`;
		if (exchange) path += `&exchange=${encodeURIComponent(exchange)}`;
		if (page) {
			const next = new URL(page, "https://api.roic.ai");
			if (next.origin !== "https://api.roic.ai" || next.pathname !== "/v3.0.0/tickers" || next.searchParams.has("apikey")) throw new DataError("Ungültiger Katalog-Cursor", 400);
			next.searchParams.set("limit", String(limit));
			next.searchParams.set("type", "stock");
			next.searchParams.set("is_primary", "true");
			next.searchParams.set("status", "listed");
			if (exchange) next.searchParams.set("exchange", exchange);
			else next.searchParams.delete("exchange");
			path = next.pathname + next.search;
		}
		const res = object(await this.get(path, 36e5, refresh));
		return {
			data: rows(res),
			next: s(res.next_page_url) || null
		};
	}
	async stock(identifier, screenTicker, refresh = false) {
		this.deadline = Date.now() + 6e4;
		if (!/^[A-Za-z0-9:._-]{1,100}$/.test(identifier)) throw new DataError("Ungültige Aktienkennung", 400);
		const id = encodeURIComponent(identifier);
		const issues = [];
		if (screenTicker && screenTicker.id !== identifier && screenTicker.symbol !== identifier) throw new DataError("Aktienkennung und Katalog stimmen nicht überein.", 422);
		const profile = object(await this.get(`/v3.0.0/company/profile/${id}`, 864e5, refresh));
		if (!profile.name) throw new DataError("Das Unternehmensprofil enthält keinen Namen.");
		const optional = async (path, label, ttl = 36e5) => {
			try {
				return await this.get(path, ttl, refresh);
			} catch (e) {
				if (e instanceof DataError && ([401, 429].includes(e.status) || screenTicker && [
					402,
					403,
					502
				].includes(e.status))) throw e;
				issues.push(`${label}: ${e instanceof Error ? e.message : "Nicht verfügbar"}`);
				return null;
			}
		};
		const period = "?period_type=annual&order=desc&limit=5";
		const [ticker, latest, income] = await Promise.all([
			screenTicker ?? optional(`/v3.0.0/tickers/${id}`, "Aktiengattung"),
			optional(`/v3.0.0/stock-prices/latest/${id}`, "Tageskurs", 9e5),
			optional(`/v3.0.0/fundamental/income-statement/${id}${period}`, "GuV")
		]);
		const [balance, cash, profit] = await Promise.all([
			optional(`/v3.0.0/fundamental/balance-sheet/${id}${period}`, "Bilanz"),
			optional(`/v3.0.0/fundamental/cash-flow/${id}${period}`, "Cashflow"),
			optional(`/v3.0.0/fundamental/ratios/profitability/${id}${period}`, "Profitabilität")
		]);
		const inc = rows(income);
		const start = (/* @__PURE__ */ new Date(Date.now() - 370 * 864e5)).toISOString().slice(0, 10);
		const [history, splits] = await Promise.all([screenTicker ? null : optional(`/v3.0.0/stock-prices/${id}?adjustment=splits&order=desc&limit=400&date.gte=${start}`, "Kurshistorie", 36e5), optional(`/v3.0.0/stock-splits?identifier=${id}&date.gt=${s(inc[0]?.period_end_date, start)}&date.lte=${(/* @__PURE__ */ new Date()).toISOString().slice(0, 10)}&limit=100`, "Splitprüfung")]);
		const t = object(ticker), p = object(latest);
		const address = object(profile.address);
		const newsId = s(t.isin) || s(profile.isin) || s(t.cik) || s(profile.cik);
		const news = newsId && !screenTicker ? await optional(`/v2/company/news/${encodeURIComponent(newsId)}?limit=8`, "Nachrichten", 9e5) : null;
		if (!newsId && !screenTicker) issues.push("Nachrichten: Keine eindeutige ISIN/CIK für die v2-Zuordnung vorhanden.");
		if (screenTicker) issues.push("Universums-Vorauswahl: ohne Kursverlauf, Momentum und Nachrichten. Die Einzelanalyse lädt diese Daten bei bestehender Verbindung nach.");
		const annual = mapPeriods(income, balance, cash, profit, "annual");
		const fetchPeriod = async (type, limit) => {
			const query = `?period_type=${type}&order=desc&limit=${limit}`;
			const [i, b, c] = await Promise.all([
				optional(`/v3.0.0/fundamental/income-statement/${id}${query}`, type + " GuV"),
				optional(`/v3.0.0/fundamental/balance-sheet/${id}${query}`, type + " Bilanz"),
				optional(`/v3.0.0/fundamental/cash-flow/${id}${query}`, type + " Cashflow")
			]);
			return {
				i,
				b,
				c,
				ratios: await optional(`/v3.0.0/fundamental/ratios/profitability/${id}${query}`, type + " Profitabilität")
			};
		};
		const [q, ttm] = await Promise.all([fetchPeriod("quarterly", 8), fetchPeriod("ttm", 5)]);
		const quarterlyFinancials = mapPeriods(q.i, q.b, q.c, q.ratios, "quarterly");
		const ttmBalance = { data: [
			...rows(ttm.b),
			...rows(q.b),
			...rows(balance)
		] };
		const ttmFinancials = mapPeriods(ttm.i, ttmBalance, ttm.c, ttm.ratios, "ttm");
		const financials = choosePeriods(annual, ttmFinancials);
		if (financials[0]?.periodType !== "ttm") issues.push("Keine neuere vollständige TTM-GuV verfügbar: Jahresabschluss als gekennzeichnete Ersatzbasis. Quartale werden nicht blind vervierfacht.");
		for (const note of financials[0]?.cashflowNotes ?? []) issues.push(note);
		const primary = t.is_primary === true && s(t.type) === "stock" && (!Array.isArray(t.type_specifications) || !t.type_specifications.length || t.type_specifications.includes("common"));
		const valuationBlocked = splits === null || rows(splits).length > 0 || !primary;
		if (rows(splits).length) issues.push("Bewertung gesperrt: Kapitalmaßnahme seit dem Jahresabschluss. EPS und Aktienanzahl müssen zuerst auf eine einheitliche Basis gebracht werden.");
		if (!primary) issues.push("Bewertung gesperrt: Hauptnotierung und Stammaktiengattung nicht bestätigt; bitte die Hauptnotierung wählen.");
		if (financials[0] && s(p.currency) !== financials[0].currency) issues.push("Bewertung gesperrt: Handels- und Bilanzwährung unterscheiden sich. Eine verifizierte FX-/Aktienumrechnung fehlt.");
		if (p.date && Date.now() - Date.parse(s(p.date)) > 7 * 864e5) issues.push("Der jüngste Kurs ist älter als sieben Tage.");
		if (financials[0] && Date.now() - Date.parse(financials[0].date) > 550 * 864e5) issues.push("Der jüngste Jahresabschluss ist älter als 18 Monate.");
		if (!financials.length) issues.push("Keine jährlichen Finanzberichte verfügbar. Es wird keine Bewertung berechnet.");
		return {
			isin: s(t.isin) || s(profile.isin),
			id: s(t.id, identifier),
			symbol: s(t.symbol, identifier),
			name: s(profile.name),
			exchange: s(t.exchange, s(profile.exchange)),
			sector: s(profile.sector, "Nicht klassifiziert"),
			industry: s(profile.industry, "Nicht klassifiziert"),
			country: s(address.country),
			currency: s(p.currency, s(t.trading_currency, "USD")),
			description: s(profile.description),
			website: safeLink(profile.website),
			employees: n(profile.number_of_employees),
			ceo: s(profile.ceo, "—"),
			price: n(p.close),
			priceDate: s(p.date, "Nicht verfügbar"),
			history: rows(history).filter((r) => valid(r.close) && typeof r.date === "string").map((r) => ({
				date: s(r.date),
				close: r.close,
				volume: n(r.volume) ?? void 0
			})).sort((a, b) => a.date.localeCompare(b.date)),
			financials,
			quarterlyFinancials,
			ttmFinancials,
			dataVersion: 6,
			news: rows(news).filter((r) => safeLink(r.article_url)).map((r) => ({
				title: s(r.title),
				url: safeLink(r.article_url),
				source: s(r.site, "Quelle"),
				date: s(r.published_date)
			})),
			source: "roic",
			issues,
			retrievedAt: (/* @__PURE__ */ new Date()).toISOString(),
			isPrimary: primary,
			securityType: s(t.type),
			valuationBlocked
		};
	}
};
//#endregion
//#region scripts/github-screener.ts
var base = process.env.QUANTUM_URL || "https://quantum-equity-research.daisyscalling.workers.dev";
if (new URL(base).origin !== base || !base.startsWith("https://")) throw Error("HTTPS origin required");
var key = process.env.ROIC_API_KEY, token = process.env.QUANTUM_SYNC_TOKEN;
if (!key || !token) throw Error("ROIC_API_KEY and QUANTUM_SYNC_TOKEN required");
var endpoint = base + "/api/screener-sync", end = Date.now() + Math.min(35, Math.max(2, Number(process.env.QUANTUM_BUDGET_MIN) || 30)) * 6e4;
async function sync(body) {
	const r = await fetch(endpoint, {
		method: body === void 0 ? "GET" : "POST",
		redirect: "error",
		signal: AbortSignal.timeout(2e4),
		headers: {
			Authorization: "Bearer " + token,
			"Content-Type": "application/json",
			"User-Agent": "QuantumScreenerSync/1.0"
		},
		...body === void 0 ? {} : { body: JSON.stringify(body) }
	});
	if (!r.ok) throw Error("Quantum import HTTP " + r.status);
	return r.json();
}
var gate = Promise.resolve(), next = 0;
var paced = async (input, init) => {
	const turn = gate.then(async () => {
		await new Promise((r) => setTimeout(r, Math.max(0, next - Date.now())));
		next = Date.now() + 280;
	});
	gate = turn;
	await turn;
	if (Date.now() > end - 45e3) throw Error("Budget reserve reached");
	return fetch(input, {
		...init,
		redirect: "error",
		signal: AbortSignal.any([AbortSignal.timeout(2e4), ...init?.signal ? [init.signal] : []]),
		headers: {
			...init?.headers,
			"User-Agent": "QuantumScreenerSync/1.0"
		}
	});
};
var client = new RoicClient(key, paced);
var state = (await sync()).checkpoint || {
	cursor: null,
	remaining: [],
	complete: false
};
var catalog = /* @__PURE__ */ new Map();
var cursor;
var visited = /* @__PURE__ */ new Set();
do {
	if (Date.now() > end - 9e4) throw Error("Catalogue exceeded budget; prior analysis position retained");
	const page = await client.catalog(cursor, void 0, 2e3, true);
	for (const ticker of page.data) if (typeof ticker.id === "string") catalog.set(ticker.id, ticker);
	cursor = page.next || void 0;
	if (cursor) {
		if (visited.has(cursor)) throw Error("Repeated catalogue cursor");
		visited.add(cursor);
	}
} while (cursor);
var all = [...catalog.values()].filter((t) => t.is_primary === true && t.type === "stock" && (!t.type_specifications?.length || t.type_specifications.includes("common"))).sort((a, b) => String(a.id).localeCompare(String(b.id), "en"));
var start = state.lastId ? all.findIndex((t) => String(t.id).localeCompare(String(state.lastId), "en") > 0) : 0;
if (start < 0) start = 0;
var max = Math.min(1e3, Math.max(1, Number(process.env.QUANTUM_MAX_COMPANIES) || 250));
var processed = 0, saved = 0, failed = 0;
for (const ticker of all.slice(start)) {
	if (processed >= max || Date.now() > end - 9e4) break;
	let stock;
	try {
		if (ticker.is_primary === true && ticker.type === "stock" && (!ticker.type_specifications?.length || ticker.type_specifications.includes("common"))) {
			stock = await client.stock(ticker.id, ticker, true);
			if (!stock.financials.length) throw Error("No financial statements");
			const result = spawnSync(process.env.PYTHON || "python", [fileURLToPath(new URL("./engine/bridge.py", "" + import.meta.url))], {
				input: JSON.stringify(stock),
				encoding: "utf8",
				timeout: 2e4,
				maxBuffer: 1e6,
				env: {
					...process.env,
					PYTHONIOENCODING: "utf-8"
				}
			});
			if (result.status !== 0) throw Error("Python valuation failed");
			stock.scriptValuation = JSON.parse(result.stdout);
		}
	} catch (e) {
		stock = void 0;
		failed++;
		if (e instanceof DataError && [
			401,
			402,
			403,
			429
		].includes(e.status)) throw Error("ROIC denied / rate limited: " + e.status);
		console.log("Company failed; previous stored analysis retained");
	}
	const nextState = {
		...state,
		cursor: null,
		remaining: [],
		complete: false,
		lastId: ticker.id,
		catalogCount: all.length,
		updatedAt: Date.now(),
		processed: (state.processed || 0) + 1,
		failed: (state.failed || 0) + (stock ? 0 : 1)
	};
	await sync({
		checkpoint: nextState,
		...stock ? { stock } : {}
	});
	state = nextState;
	processed++;
	if (stock) saved++;
	if (processed % 10 === 0) console.log(`Screener: ${processed} processed, ${saved} saved, ${failed} failed`);
}
console.log(`Screener complete: ${processed} processed, ${saved} saved, ${failed} failed; checkpoint persisted`);
if (failed && !saved) throw Error("No analyses saved; review data access");
//#endregion

