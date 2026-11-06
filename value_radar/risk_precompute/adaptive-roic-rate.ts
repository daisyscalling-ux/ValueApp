/** Serial requester only: another API consumer still shares the provider limit. */
export class AdaptiveRoicRate {
 readonly minimumSpacing:number;
 spacing:number;
 blockedUntil=0;
 private lastStart=-Infinity;
 private recoveryAt=-Infinity;
 private successful=0;
 recoveries=0;
 constructor(rpm:number){
  if(!Number.isFinite(rpm)||rpm<20||rpm>240)throw Error('Ungültiges Aufruflimit.');
  this.minimumSpacing=60000/rpm;this.spacing=this.minimumSpacing;
 }
 delay(now:number){return Math.max(0,this.blockedUntil-now,this.lastStart+this.spacing-now)}
 start(now:number){this.lastStart=now}
 response(status:number,retryAfter:string|null,now:number){
  if(status===429){
   const seconds=retryAfter===null?NaN:Number(retryAfter),date=retryAfter?Date.parse(retryAfter):NaN;
   const delay=Math.max(30000,Number.isFinite(seconds)?seconds*1000:Number.isFinite(date)?date-now:60000);
   this.blockedUntil=Math.max(this.blockedUntil,now+delay);
   this.spacing=Math.min(3000,this.spacing*1.5);
   this.recoveryAt=this.blockedUntil;this.successful=0;return;
  }
  if(status<200||status>=300){this.successful=0;this.recoveryAt=now;return}
  this.successful++;
  // At least 20 successes AND a clean minute per recovery step, never a burst.
  if(this.spacing>this.minimumSpacing&&this.successful>=20&&now-this.recoveryAt>=60000){
   this.spacing=Math.max(this.minimumSpacing,this.spacing*.8);
   this.recoveries++;this.successful=0;this.recoveryAt=now;
  }
 }
 stats(){return {spacingMs:Math.round(this.spacing),configuredRequestsPerMinute:60000/this.minimumSpacing,recoverySteps:this.recoveries}}
}
