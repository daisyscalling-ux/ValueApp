"""Replay narrowly reviewed original facts without renewing data freshness."""
import json
import math
from pathlib import Path

METHOD='reviewed-edinet-broad-purchases-v1'

def apply(record,reviews=None):
    annual=record.get('annual',{})
    if annual.get('source')!='EDINET annual XBRL' or annual.get('currency')!='JPY':return False
    if annual.get('fields',{}).get('noncurrent_asset_purchases') is not None:return False
    reviews=reviews if reviews is not None else json.loads(Path(__file__).with_name('edinet_reviewed_purchases.json').read_text(encoding='utf-8'))['reviews']
    for review in reviews:
        if any(annual.get(k)!=review[k] for k in ('symbol','docID','start','end','fileSha256')):continue
        if record.get('filing',{}).get('docID')!=review['docID']:continue
        evidence=annual.get('extensionEvidence',{})
        if evidence.get('method')!='local-extension-label-review-v1' or evidence.get('truncated'):continue
        candidates=[c for c in evidence.get('candidates',[]) if c.get('tag')==review['tag']]
        if not candidates:continue
        values=[]
        for c in candidates:
            definition=c.get('definition') or {}
            valid_label=any(l.get('language')=='en' and l.get('role')=='http://www.xbrl.org/2003/role/label' and l.get('text')==review['label'] and l.get('sha256')==review['labelSha256'] for l in c.get('labels',[]))
            value=c.get('value')
            if definition.get('schemaSha256')!=review['schemaSha256'] or definition.get('periodType')!='duration' or not valid_label or c.get('periodKind')!='duration':break
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value>0:break
            values.append(value)
        if len(values)!=len(candidates) or len(set(values))!=1:continue
        annual.setdefault('fields',{})['noncurrent_asset_purchases']=-values[0]
        annual.setdefault('field_sources',{})['noncurrent_asset_purchases']={
            'source':annual['source'],'start':annual['start'],'end':annual['end'],
            'currency':'JPY','docID':annual['docID'],'tag':review['tag'],
            'derivation':METHOD,'fileSha256':review['fileSha256'],
            'schemaSha256':review['schemaSha256'],'labelSha256':review['labelSha256'],
            'scope':review['scope']}
        annual['reviewedPurchaseContext']={'method':METHOD,'scope':review['scope'],'scoreContribution':0,'fullCapex':False}
        return True
    return False
