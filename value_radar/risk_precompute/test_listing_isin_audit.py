import datetime as dt,unittest
import listing_isin_audit as a
NOW=dt.datetime(2026,11,10,12,tzinfo=dt.timezone.utc)
ROW={'listing_symbol':'OTC:IDCBF','ticker':'IDCBF','isin':'CNE000001P37','security_type':'stock','name_full':'Industrial and Commercial Bank of China Limited Class A'}
H={'symbol':'OTC:IDCBF','isin':'CNE1000003G1','type':'stock'}
class Audit(unittest.TestCase):
 def run_(self,rows,hits,state=None,now=NOW):
  calls=[];out=a.run({'kandidaten':rows},state or {},lambda q:(calls.append(q),hits)[1],now);return out,calls
 def test_conflict_reported_not_changed(self):
  out,_=self.run_([dict(ROW)],[H]);r=out['listings']['OTC:IDCBF']
  self.assertEqual((r['state'],r['providerIsin'],r['universeIsin'],r['sameCountryPrefix']),('conflict','CNE1000003G1','CNE000001P37',True))
  self.assertEqual(out['openConflicts'],['OTC:IDCBF'])
 def test_reference_confirmed_and_contradicted(self):
  fixed={**ROW,'isin':'CNE1000003G1','listing_reference_status':'applied'}
  out,_=self.run_([fixed],[H]);self.assertEqual(out['listings']['OTC:IDCBF']['state'],'reference_confirmed');self.assertEqual(out['openConflicts'],[])
  out,_=self.run_([fixed],[{**H,'isin':'CNE000001P37'}]);self.assertEqual(out['listings']['OTC:IDCBF']['state'],'reference_contradicted')
 def test_scope_cache_and_unclear_results(self):
  out,calls=self.run_([{**ROW,'security_type':'dr'},{**ROW,'listing_symbol':'NYSE:X','ticker':'X'}],[H]);self.assertEqual((out['listings'],calls),({},[]))
  out,_=self.run_([dict(ROW)],[{**H,'symbol':'OTC:OTHER'}]);self.assertEqual(out['listings']['OTC:IDCBF']['state'],'not_found')
  out,_=self.run_([dict(ROW)],[H,{**H,'isin':'CNE000001P37'}]);self.assertEqual(out['listings']['OTC:IDCBF']['state'],'ambiguous')
  first,_=self.run_([dict(ROW)],[H]);again,calls=self.run_([dict(ROW)],[H],first,NOW+dt.timedelta(days=3));self.assertEqual(calls,[])
  later,calls=self.run_([dict(ROW)],[H],first,NOW+dt.timedelta(days=15));self.assertEqual(calls,['IDCBF'])
  changed,calls=self.run_([{**ROW,'isin':'CNE1000003G1'}],[H],first,NOW+dt.timedelta(days=1));self.assertEqual(calls,['IDCBF'])
  gone,_=self.run_([],[H],first);self.assertEqual(gone['listings'],{})
if __name__=='__main__':unittest.main()
