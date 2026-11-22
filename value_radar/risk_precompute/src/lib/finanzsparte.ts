/**
 * finanzsparte.ts - Konzerne mit eigener Finanzierungssparte (seit 22.11.2026, Entscheidung des Nutzers).
 * Bei Fahrzeug- und Maschinenherstellern mit Kunden- und Händlerfinanzierung enthalten die Nettoschulden das
 * Finanzierungsgeschäft (VW 157 Mrd €), der freie Cashflow aber nicht dessen Ertrag; das Wachstum der
 * Finanzierungsforderungen drückt zudem den operativen Cashflow. Segmentdaten zum Herausrechnen fehlen. Der DCF bleibt
 * deshalb offen (valuation.ts, dcfSperre); die übrigen Methoden tragen den Fair Value.
 * Zuordnung kuratiert je Gesellschaft über die ISIN (alle Aktiengattungen derselben Gesellschaft; ein ähnlicher Name zählt
 * nicht), mit Prüfdatum und Ablauf. Abgelaufene Prüfung: Eintrag gilt nicht, der DCF rechnet wie zuvor.
 * Quelle: Segmentberichterstattung der Geschäftsberichte 2025 (eigener Finanzdienstleistungs-Bereich mit eigener
 * Refinanzierung); verlinkt ist die Investor-Relations-Seite der Gesellschaft.
 * Identische Kopie unter ValueApp/value_radar/risk_precompute/src/lib.
 */
export const FINANZSPARTE_METHOD='captive_finance_curated_v1';
export const FINANZSPARTE_REVIEWED_ON='2026-11-22',FINANZSPARTE_REVIEW_EXPIRES='2027-11-22';
export type FinanzsparteEintrag={name:string;isins:string[];sparte:string;source_url:string};
export const FINANZSPARTEN:FinanzsparteEintrag[]=[
 {name:'Volkswagen AG',isins:['DE0007664039','DE0007664005'],sparte:'Volkswagen Financial Services',source_url:'https://www.volkswagen-group.com/de/investor-relations'},
 {name:'Bayerische Motoren Werke AG',isins:['DE0005190003','DE0005190037'],sparte:'Segment Finanzdienstleistungen',source_url:'https://www.bmwgroup.com/de/investor-relations.html'},
 {name:'Mercedes-Benz Group AG',isins:['DE0007100000'],sparte:'Mercedes-Benz Mobility',source_url:'https://group.mercedes-benz.com/investoren/'},
 {name:'Daimler Truck Holding AG',isins:['DE000DTR0CK8'],sparte:'Financial Services',source_url:'https://www.daimlertruck.com/investoren'},
 {name:'Porsche AG',isins:['DE000PAG9113'],sparte:'Porsche Financial Services',source_url:'https://investorrelations.porsche.com/'},
 {name:'General Motors Company',isins:['US37045V1008'],sparte:'GM Financial',source_url:'https://investor.gm.com/'},
 {name:'Ford Motor Company',isins:['US3453708600'],sparte:'Ford Credit',source_url:'https://shareholder.ford.com/'},
 {name:'Stellantis N.V.',isins:['NL00150001Q9'],sparte:'Financial Services',source_url:'https://www.stellantis.com/en/investors'},
 {name:'Toyota Motor Corp.',isins:['JP3633400001'],sparte:'Financial Services',source_url:'https://global.toyota/en/ir/'},
 {name:'Honda Motor Co., Ltd.',isins:['JP3854600008'],sparte:'Financial Services',source_url:'https://global.honda/en/investors/'},
 {name:'Nissan Motor Co., Ltd.',isins:['JP3672400003'],sparte:'Sales Financing',source_url:'https://www.nissan-global.com/EN/IR/'},
 {name:'Renault SA',isins:['FR0000131906'],sparte:'Mobilize Financial Services',source_url:'https://www.renaultgroup.com/en/finance/'},
 {name:'Iveco Group NV',isins:['NL0015000LU4'],sparte:'Financial Services',source_url:'https://www.ivecogroup.com/investors'},
 {name:'Yamaha Motor Co., Ltd.',isins:['JP3942800008'],sparte:'Financial Services',source_url:'https://global.yamaha-motor.com/ir/'},
 {name:'Deere & Company',isins:['US2441991054'],sparte:'Financial Services (John Deere Financial)',source_url:'https://investor.deere.com/'},
 {name:'Caterpillar, Inc.',isins:['US1491231015'],sparte:'Financial Products (Cat Financial)',source_url:'https://investors.caterpillar.com/'},
 {name:'PACCAR Inc.',isins:['US6937181088'],sparte:'Financial Services (PACCAR Financial)',source_url:'https://investors.paccar.com/'},
 {name:'Volvo AB',isins:['SE0000115420','SE0000115446'],sparte:'Volvo Financial Services',source_url:'https://www.volvogroup.com/en/investors.html'},
];
export type Finanzsparte={method:string;name:string;sparte:string;isin:string;source_url:string;reviewed_on:string;review_expires:string};
/** Zuordnung über die exakte ISIN; nur bis zum Ablauf der Prüfung. */
export function finanzsparte(isin:unknown,now=Date.now()):Finanzsparte|null{
 if(typeof isin!=='string'||!/^[A-Z]{2}[A-Z0-9]{9}\d$/.test(isin))return null;
 const ab=Date.parse(FINANZSPARTE_REVIEW_EXPIRES+'T23:59:59Z'),seit=Date.parse(FINANZSPARTE_REVIEWED_ON);
 if(!(now<=ab&&now>=seit-86400000))return null;
 const e=FINANZSPARTEN.find(x=>x.isins.includes(isin));
 return e?{method:FINANZSPARTE_METHOD,name:e.name,sparte:e.sparte,isin,source_url:e.source_url,reviewed_on:FINANZSPARTE_REVIEWED_ON,review_expires:FINANZSPARTE_REVIEW_EXPIRES}:null;
}
