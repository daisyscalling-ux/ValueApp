import datetime as dt,io,zipfile,unittest
from ecb_fx import normalize
NOW=dt.datetime(2026,10,26,22,tzinfo=dt.timezone.utc)
def archive(text,name='eurofxref-hist.csv'):
 out=io.BytesIO()
 with zipfile.ZipFile(out,'w') as z:z.writestr(name,text)
 return out.getvalue()
def data():
 return 'Date,USD,JPY,GBP,\n'+'\n'.join((NOW.date()-dt.timedelta(days=i)).isoformat()+',1.1,160,0.8,' for i in range(1,401))
class Tests(unittest.TestCase):
 def test_valid_units_order_and_today_excluded(self):
  p=normalize(archive(data()+'\n2026-10-26,2,200,1,'),NOW)
  self.assertEqual(p['lastObservation'],'2026-10-25');self.assertEqual(p['rates']['2026-10-25']['JPY'],160)
  self.assertEqual(p['quoteConvention'],'currency_units_per_EUR');self.assertNotIn('2026-10-26',p['rates'])
 def test_missing_currency_not_zero(self):
  p=normalize(archive(data().replace(',160,',',N/A,')),NOW)
  self.assertNotIn('JPY',p['rates']['2026-10-25'])
 def test_bad_rates_rejected(self):
  for rate in ['0','-1','NaN','inf','oops']:
   with self.assertRaises(ValueError):normalize(archive(data().replace(',160,',','+rate+',')),NOW)
 def test_duplicates_rejected(self):
  with self.assertRaises(ValueError):normalize(archive(data()+'\n2026-10-25,1.1,160,0.8,'),NOW)
 def test_wrong_archive_rejected(self):
  with self.assertRaises(ValueError):normalize(archive(data(),'../escape.csv'),NOW)
 def test_stale_and_short_history_rejected(self):
  with self.assertRaises(ValueError):normalize(archive(data()),NOW+dt.timedelta(days=9))
  with self.assertRaises(ValueError):normalize(archive('Date,USD\n2026-10-25,1.1'),NOW)
 def test_future_and_old_rows_never_retained(self):
  p=normalize(archive(data()+'\n2026-10-27,1.1,160,.8,\n2020-01-01,1,100,.5,'),NOW)
  self.assertEqual(len(p['rates']),400)
if __name__=='__main__':unittest.main()
