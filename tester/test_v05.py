import unittest
from datetime import datetime,timezone,timedelta
from backtest import Bar
from evalbot_v05 import features,triple_barrier,dataset,purged_split

class V05Tests(unittest.TestCase):
    def bars(self,n=350):
        t=datetime(2026,1,1,tzinfo=timezone.utc)
        return [Bar(t+timedelta(minutes=i),100+i*.01,100.3+i*.01,99.7+i*.01,100+i*.01,100+i%7) for i in range(n)]
    def test_feature_causality(self):
        a=self.bars(); f1,_=features(a)
        a[200].h=10000
        f2,_=features(a)
        self.assertTrue((f1[150]==f2[150]).all())
    def test_ambiguous_bar_conservative(self):
        a=self.bars(); a[101].h=105; a[101].l=95
        self.assertEqual(triple_barrier(a,100,1,1,2,5)[0],0)
        self.assertEqual(triple_barrier(a,100,-1,1,2,5)[0],0)
    def test_split_no_label_overlap(self):
        meta=[(i,i+3,1,1) for i in range(10,100)]
        tr,va,te=purged_split(meta,100,3)
        self.assertTrue(all(meta[k][1]<60 for k in tr))
        self.assertTrue(all(meta[k][0]>=60 and meta[k][1]<80 for k in va))
        self.assertTrue(all(meta[k][0]>=80 for k in te))
    def test_dataset_dimensions(self):
        X,y,meta=dataset(self.bars(),horizon=5)
        self.assertEqual(X.shape[1],13)
        self.assertEqual(len(y),len(meta))

if __name__=='__main__':unittest.main()
