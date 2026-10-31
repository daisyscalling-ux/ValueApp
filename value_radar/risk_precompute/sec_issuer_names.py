"""Formatting-only issuer comparison, always subordinate to exact SEC listing/CIK."""
import re,unicodedata
POLICY='sec-issuer-format-v2'
def name_key(value):
 s=unicodedata.normalize('NFKD',str(value or '')).casefold()
 s=''.join(c for c in s if not unicodedata.combining(c))
 # SEC incorporation suffixes, not arbitrary slash-separated business names.
 s=re.sub(r'\s*/(?:de|md|ny|nj|ca|nv|pa|va|ma|fl|oh|tx|wa|wi|mn|co|ct|or|new)/\s*$','',s)
 s=re.sub(r'\s*\(the\)\s*$','',s)
 s=re.sub(r'^the\s+','',s)
 # Security description is removed only as a terminal explicit phrase.
 s=re.sub(r'\s+common\s+stock\s*$','',s)
 s=re.sub(r'\s*\((?:reit|holding company)\)\s*$','',s)
 s=s.replace('&',' and ').replace("'",'').replace('’','')
 words=re.findall(r'[a-z0-9]+',s)
 suffixes=[['incorporated'],['corporation'],['limited'],['company'],['corp'],['inc'],['ltd'],['plc'],['co']]
 changed=True
 while changed:
  changed=False
  for suffix in suffixes:
   if len(words)>len(suffix) and words[-len(suffix):]==suffix:words=words[:-len(suffix)];changed=True;break
 return ' '.join(words)
def same_issuer(a,b):
 ka,kb=name_key(a),name_key(b)
 return bool(ka and kb and ka==kb)
