/** Explicit cash-equity closures. Never infer a closure from a missing quote. */
const DAY=86400000;
export const JPX_CALENDAR_SOURCE='https://www.jpx.co.jp/english/corporate/about-jpx/calendar/index.html';
const holidays=new Set([
 '2025-12-31',
 '2026-01-01','2026-01-02','2026-01-03','2026-01-12','2026-02-11','2026-02-23','2026-03-20','2026-04-29',
 '2026-05-03','2026-05-04','2026-05-05','2026-05-06','2026-07-20','2026-08-11','2026-09-21','2026-09-22',
 '2026-09-23','2026-10-12','2026-11-03','2026-11-23','2026-12-31',
 '2027-01-01','2027-01-02','2027-01-03','2027-01-11','2027-02-11','2027-02-23','2027-03-21','2027-03-22',
 '2027-04-29','2027-05-03','2027-05-04','2027-05-05','2027-07-19','2027-08-11','2027-09-20','2027-09-23',
 '2027-10-11','2027-11-03','2027-11-23','2027-12-31'
]);
export function verifiedClosureGap(previous:string,wanted:number,symbols:string[]){
 const start=Date.parse(previous),days=(wanted-start)/DAY;
 if(!symbols.length||!symbols.every(s=>/^(TSE|TYO|JPX):/.test(s))||days<=0||days>10)return false;
 for(let t=start+DAY;t<=wanted;t+=DAY){
  const d=new Date(t),key=d.toISOString().slice(0,10);
  if(key<'2025-12-31'||key>'2027-12-31')return false;
  if(![0,6].includes(d.getUTCDay())&&!holidays.has(key))return false;
 }
 return true;
}
export function weeklyCalendar(dates:string[],end:string,symbols:string[]=[]){
 const weekly:string[]=[],adjustments:{anchor:string;observation:string}[]=[];
 const finish=Date.parse(end);
 for(let i=52;i>=0;i--){
  const wanted=finish-i*7*DAY,day=new Date(wanted).toISOString().slice(0,10);
  const d=[...dates].reverse().find(x=>Date.parse(x)<=wanted);
  if(!d||wanted-Date.parse(d)>4*DAY){
   if(!d||!verifiedClosureGap(d,wanted,symbols))return {dates:weekly,adjustments,error:'unverified_weekly_gap',anchor:day,previous:d||null};
   adjustments.push({anchor:day,observation:d});
  }
  if(weekly.includes(d))return {dates:weekly,adjustments,error:'duplicate_weekly_observation',anchor:day,previous:d};
  weekly.push(d);
 }
 return {dates:weekly,adjustments,error:null,anchor:null,previous:null};
}
