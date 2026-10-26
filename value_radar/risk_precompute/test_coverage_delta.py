import unittest
import datetime as dt
from coverage_delta import compare
NOW=dt.datetime(2026,10,25,15,tzinfo=dt.timezone.utc)
def snapshot(date,rows):return {'generatedAt':date,'stocks':[{'symbol':symbol,'domains':{'balance':{'state':state}}} for symbol,state in rows]}
class Delta(unittest.TestCase):
 def setUp(self):
  self.old=snapshot('2026-10-24T15:00:00Z',[('NYSE:A','available'),('TSE:1234','partial'),('LSE:B','context_only')])
  self.new=snapshot('2026-10-25T14:00:00Z',[('NYSE:A','missing'),('TSE:1234','available'),('LSE:B','partial')])
 def test_transitions_are_not_scores(self):
  r=compare(self.old,self.new,NOW);self.assertEqual(r['summary']['transitions'],{'became_available':1,'lost_available':1,'state_changed':1});self.assertNotIn('score',r)
 def test_added_removed_not_recoveries(self):
  self.new['stocks'].pop(0);self.new['stocks'].append({'symbol':'NYSE:NEW','domains':{'balance':{'state':'available'}}})
  r=compare(self.old,self.new,NOW);self.assertEqual(r['addedListings'],['NYSE:NEW']);self.assertEqual(r['removedListings'],['NYSE:A']);self.assertEqual(r['summary']['transitions']['became_available'],1)
 def test_bad_dates(self):
  for date in (None,'bad','2026-01-01T00:00:00Z','2026-10-25T14:00:00Z','2027-01-01T00:00:00Z'):
   self.old['generatedAt']=date;self.assertEqual(compare(self.old,self.new,NOW)['state'],'not_comparable')
 def test_stale_current(self):
  self.new['generatedAt']='2026-10-20T00:00:00Z';self.assertEqual(compare(self.old,self.new,NOW)['reason'],'current_missing_stale_or_future')
 def test_duplicate_symbols(self):
  self.old['stocks'].append(self.old['stocks'][0]);self.assertEqual(compare(self.old,self.new,NOW)['reason'],'duplicate_or_invalid_listing')
 def test_missing_baseline(self):self.assertEqual(compare({},self.new,NOW)['state'],'not_comparable')
 def test_unchanged(self):
  self.new['stocks']=self.old['stocks'];self.assertEqual(compare(self.old,self.new,NOW)['changes'],[])
 def test_profile_change_is_not_counted_as_data_loss(self):
  self.old['stocks'][0]['domains']['balance']['profile']='corporate'
  self.new['stocks'][0]['domains']['balance'].update(profile='specialist_financial',state='context_only')
  r=compare(self.old,self.new,NOW);self.assertEqual(r['summary']['transitions']['framework_changed'],1)
  self.assertNotIn('lost_available',r['summary']['transitions'])
if __name__=='__main__':unittest.main()
