"""Collect local taxonomy definitions for review; never infer accounting equivalence."""
import hashlib,posixpath,xml.etree.ElementTree as ET
from urllib.parse import urlsplit,unquote
XSD='{http://www.w3.org/2001/XMLSchema}'
LINK='{http://www.xbrl.org/2003/linkbase}'
XL='{http://www.w3.org/1999/xlink}'

def local_reference(href,filename,definition):
 try:ref=urlsplit(href)
 except ValueError:return False
 if ref.scheme or ref.netloc or ref.query or ref.fragment!=definition['id']:return False
 path=unquote(ref.path)
 if not path or path.startswith('/') or '\\' in path:return False
 resolved=posixpath.normpath(posixpath.join(posixpath.dirname(filename),path))
 return resolved==definition['schemaFile']

def collect(archive,annual):
 candidates=[x for x in annual.get('diagnostics',{}).get('monetaryCandidates',[]) if '/taxonomy/' not in x.get('tag','') and x.get('periodKind')=='duration' and ('Purchase' in x.get('tag','') or 'Acquis' in x.get('tag',''))]
 out={'method':'local-extension-label-review-v1','state':'review_required','candidates':[],'scoreContribution':0,'automaticallyMapped':False}
 if not candidates:return out
 trees=[];total=0
 for entry in archive.infolist():
  if '/PublicDoc/' not in '/'+entry.filename or not entry.filename.endswith(('.xsd','.xml')):continue
  if entry.file_size>2_000_000 or entry.file_size>max(1,entry.compress_size)*300:continue
  total+=entry.file_size
  if total>8_000_000 or len(trees)>=40:out['truncated']=True;break
  raw=archive.read(entry)
  probe=raw.replace(b'\x00',b'').upper()
  if b'<!DOCTYPE' in probe or b'<!ENTITY' in probe:continue
  try:root=ET.fromstring(raw)
  except ET.ParseError:continue
  trees.append((entry.filename,root,hashlib.sha256(raw).hexdigest()))
 definitions={}
 for filename,root,digest in trees:
  if root.tag!=XSD+'schema':continue
  namespace=root.get('targetNamespace','')
  for element in root.findall(XSD+'element'):
   if not element.get('id') or not element.get('name'):continue
   definitions['{'+namespace+'}'+element.get('name')]={'id':element.get('id'),'schemaFile':filename,'schemaSha256':digest,'type':element.get('type'),'periodType':element.get('{http://www.xbrl.org/2003/instance}periodType')}
 for c in candidates[:40]:
  definition=definitions.get(c['tag']);labels=[]
  if definition:
   for filename,root,digest in trees:
    for link in root.iter(LINK+'labelLink'):
     locs={x.get(XL+'label') for x in link.findall(LINK+'loc') if local_reference(x.get(XL+'href',''),filename,definition)}
     targets={x.get(XL+'to') for x in link.findall(LINK+'labelArc') if x.get(XL+'from') in locs}
     for label in link.findall(LINK+'label'):
      if label.get(XL+'label') in targets:
       labels.append({'text':''.join(label.itertext())[:1000],'language':label.get('{http://www.w3.org/XML/1998/namespace}lang'),'role':label.get(XL+'role'),'file':filename,'sha256':digest})
  out['candidates'].append({**c,'definition':definition,'labels':labels[:12]})
 return out
