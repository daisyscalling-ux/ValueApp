import copy,datetime as dt,hashlib,unittest
from fed_capital_requirements import collect,requirement_for,URL
class FedRequirementTests(unittest.TestCase):
 def setUp(self):
  self.now=dt.datetime(2026,10,30,tzinfo=dt.timezone.utc);self.payload=b'%PDF-test'
  self.r={'schema':1,'method':'fed-cet1-requirement-v1','sourceUrl':URL,'sourceSha256':hashlib.sha256(self.payload).hexdigest(),'sourcePage':3,'publicationDate':'2026-06-24','applicableFrom':'2026-06-24','reviewExpires':'2026-12-31','entries':[{'rssdId':'1','holdingName':'Example','minimumBps':450,'stressBufferBps':250,'gsibBps':0,'totalBps':700}]}
  self.cap={'rssdId':'1','holdingName':'Example','period':'2026-06-30'}
 def collect(self,previous=None,now=None):return collect(self.r,previous or {},now or self.now,lambda:self.payload)
 def test_verified_and_source_changed(self):
  a=self.collect();self.assertEqual(requirement_for(self.cap,a,self.now)['value'],.07)
  self.payload=b'changed';self.assertEqual(self.collect(a)['reason'],'source_changed_review_required')
 def test_failed_fetch_preserves_original_verification_only_seven_days(self):
  a=self.collect()
  def fail():raise TimeoutError()
  for days,state in [(1,'available'),(7,'available'),(8,'missing')]:
   b=collect(self.r,a,self.now+dt.timedelta(days=days),fail);self.assertEqual(b['state'],state)
   if state=='available':self.assertEqual(b['sourceVerifiedAt'],a['sourceVerifiedAt'])
 def test_changed_registry_cannot_use_cached_evidence(self):
  a=self.collect();self.r['entries'][0]['holdingName']='Other'
  def fail():raise TimeoutError()
  self.assertEqual(collect(self.r,a,self.now,fail)['state'],'missing')
 def test_invalid_components_expiry_and_duplicates(self):
  original=copy.deepcopy(self.r)
  for key,value in [('totalBps',710),('gsibBps',True),('minimumBps',-450)]:
   self.r['entries'][0][key]=value;self.assertEqual(self.collect()['state'],'missing');self.r=copy.deepcopy(original)
  self.r['entries']*=2;self.assertEqual(self.collect()['state'],'missing')
  self.r=original;self.assertEqual(self.collect(now=dt.datetime(2027,1,1,tzinfo=dt.timezone.utc))['state'],'missing')
 def test_entity_period_and_dates_not_borrowed(self):
  a=self.collect()
  for patch in [{'rssdId':'2'},{'holdingName':'Subsidiary'},{'period':'2026-03-31'}]:self.assertIsNone(requirement_for({**self.cap,**patch},a,self.now))
  self.assertIsNone(requirement_for(self.cap,a,self.now+dt.timedelta(days=8)))
if __name__=='__main__':unittest.main()
