"""Auditable coverage ratios, not a percentage of project completion."""
from collections import Counter
from market_priority import market_tier

def measures(rows):
 total=len(rows)
 def available(r,d):return r.get('domains',{}).get(d,{}).get('state')=='available'
 def ratio(n):return {'available':n,'total':total,'percent':round(100*n/total,1) if total else None}
 result={d:ratio(sum(available(r,d) for r in rows)) for d in ['identity','quote','price','historical','market','sector']}
 result['balance_complete']=ratio(sum(available(r,'balance') for r in rows))
 result['balance_context_only']=ratio(sum(r.get('domains',{}).get('balance',{}).get('state')=='context_only' for r in rows))
 result['balance_basic_or_context']=ratio(sum(r.get('domains',{}).get('balance',{}).get('state') in ('available','context_only') for r in rows))
 result['any_peer_context']=ratio(sum(available(r,'sector') or any(r.get('domains',{}).get('sector',{}).get(k,{}).get('state')=='available' for k in ['industryContext','broaderContext']) for r in rows))
 # An intersection, not an average of unequal domain coverage percentages.
 result['core_data_together']=ratio(sum(all(available(r,d) for d in ['identity','quote','historical','market']) and r.get('domains',{}).get('balance',{}).get('state') in ('available','context_only') for r in rows))
 result['newsStates']=dict(Counter(r.get('domains',{}).get('news',{}).get('state','not_assessed') for r in rows))
 return result

def progress(rows,batches):
 scopes={'all':rows,'mainMarkets':[r for r in rows if market_tier(r['symbol'])<=1],'deferredMarkets':[r for r in rows if market_tier(r['symbol'])>1]}
 blocks=[]
 for kind in sorted({g['kind'] for g in batches}):
  groups=[g for g in batches if g['kind']==kind]
  main=sorted({s for g in groups if g['marketTier']<=1 for s in g['symbols']})
  deferred=sorted({s for g in groups if g['marketTier']>1 for s in g['symbols']})
  blocks.append({'kind':kind,'mainMarketListings':len(main),'deferredMarketListings':len(deferred),'mainMarketSymbols':main,'deferredMarketSymbols':deferred,'reasons':sorted({g['reason'] for g in groups})})
 # These phases cannot be certified from snapshot availability or article counts.
 return {'completionPercent':None,'completionStatus':'not_certified','scopes':{k:measures(v) for k,v in scopes.items()},
  'remainingBlocks':sorted(blocks,key=lambda b:(-b['mainMarketListings'],-b['deferredMarketListings'],b['kind'])),
  'unverifiedCompletionGates':['sector_specific_original_disclosures','news_event_verification','historical_validation_of_full_model','end_to_end_acceptance'],
  'interpretation':'Data availability only. Context-only bank/insurer figures do not close sector requirements. News presence is not a verified risk event. Strict peers and broader context are separate. Historical price validation is not full-model validation. No arbitrary total completion percentage.'}

def markdown(p):
 labels={'identity':'Identitaet','quote':'Aktueller Kurs','historical':'Nutzbare Kurshistorie','market':'Marktkontext','balance_complete':'Vollstaendige Basis-Bilanzkennzahlen','balance_context_only':'Nur Finanzbranchen-Kontext','balance_basic_or_context':'Basis-Bilanz oder Finanzbranchen-Kontext','sector':'Strenger Peer-Vergleich','any_peer_context':'Mindestens ein Vergleichskontext','core_data_together':'Basisdaten gemeinsam vorhanden'}
 lines=['\n## Messbarer Fortschritt des Risikoprojekts\n','Datenabdeckung, kein Fertigstellungsgrad des gesamten Scores. Finanzbranchen-Kontext ersetzt keine Branchenpruefung.\n','| Datenbereich | Hauptmaerkte | Gesamtes Universum |','|---|---:|---:|']
 def cell(v):return str(v['available'])+'/'+str(v['total'])+(' ('+str(v['percent'])+' %)' if v['percent'] is not None else ' (keine Basis)')
 for key,label in labels.items():lines.append('| '+label+' | '+cell(p['scopes']['mainMarkets'][key])+' | '+cell(p['scopes']['all'][key])+' |')
 lines.extend(['','Offen bleiben die Branchenpruefung anhand Originalangaben, bestaetigte Nachrichtenereignisse, historische Validierung des Gesamtmodells und die Endabnahme.','', '| Arbeitsblock | Hauptmarkt-Notierungen | Zurueckgestellt |','|---|---:|---:|'])
 for b in p['remainingBlocks']:lines.append('| '+b['kind']+' | '+str(b['mainMarketListings'])+' | '+str(b['deferredMarketListings'])+' |')
 lines.append('\nNotierungen koennen in mehreren Arbeitsbloecken vorkommen; innerhalb jedes Blocks werden sie nur einmal gezaehlt.\n')
 return '\n'.join(lines)
