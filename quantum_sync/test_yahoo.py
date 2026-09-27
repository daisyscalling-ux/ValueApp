import unittest
from yahoo_supplement import normalize, yahoo_symbol

class YahooTests(unittest.TestCase):
    def test_target_identity_currency_and_range(self):
        stock=dict(symbol='XETR:SAP',exchange='XETR',currency='EUR',isin='DE-fixture',isPrimary=True,securityType='stock')
        info=dict(symbol='SAP.DE',exchange='GER',currency='EUR',quoteType='EQUITY',targetMeanPrice=200,targetMedianPrice=195,targetLowPrice=150,targetHighPrice=250)
        self.assertEqual(yahoo_symbol(stock),'SAP.DE')
        self.assertEqual(normalize(stock,info,'DE-fixture','SAP.DE')['mean'],200)
        for patch in [dict(currency='USD'),dict(exchange='NYQ'),dict(symbol='SAP'),dict(quoteType='ETF'),dict(targetHighPrice=180)]:
            with self.assertRaises(ValueError):normalize(stock,{**info,**patch},'DE-fixture','SAP.DE')
        with self.assertRaises(ValueError):normalize(stock,info,'wrong','SAP.DE')
        self.assertIsNone(normalize(stock,{**info,'targetMeanPrice':None},'DE-fixture','SAP.DE'))

if __name__=='__main__':unittest.main()
