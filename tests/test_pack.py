import io
import json
import unittest
from rag_evidence_pack import Document, EvidencePacker
from rag_evidence_pack.cli import demo_documents
from rag_evidence_pack.server import create_app


class PackingTest(unittest.TestCase):
    def test_source_offsets_and_budget(self):
        docs = demo_documents()
        for budget in [0,20,80,150,220,1000]:
            p = EvidencePacker().pack("日志保留期限 log retention",docs,budget=budget)
            self.assertLessEqual(p.used,budget)
            self.assertEqual(p.used,len(p.context.encode("utf-8")))
            self.assertTrue(p.verify(docs))
        self.assertGreater(len(p.spans),0)

    def test_duplicates_removed_and_no_overlap(self):
        docs = [Document("x","日志保留30天。日志保留30天。")]
        p = EvidencePacker().pack("日志",docs)
        self.assertEqual(len(p.spans),1)

    def test_source_mutation_detected(self):
        p = EvidencePacker().pack("cat",[Document("x","cat sleeps.")])
        self.assertFalse(p.verify([Document("x","cat runs.")]))
        self.assertFalse(p.verify([]))

    def test_custom_counter_counts_headers(self):
        p = EvidencePacker(count=lambda x:len(x),unit="characters").pack(
            "cat",[Document("x","cat.")],budget=5)
        self.assertEqual(p.spans,[])

    def test_unrelated_query_empty(self):
        self.assertEqual(EvidencePacker().pack("quantum",[Document("x","cat.")]).spans,[])

    def test_malformed_input(self):
        with self.assertRaises(ValueError):
            EvidencePacker().pack("cat",[Document("x","a"),Document("x","b")])
        with self.assertRaises(ValueError):
            EvidencePacker().pack("",[])
        with self.assertRaises(ValueError):
            EvidencePacker().pack("x",[],budget=-1)

    def test_unicode_offsets_long_windows(self):
        d = Document("x","   日志保留30天。\n  log retention is 30 days. ")
        p = EvidencePacker(max_chars=10).pack("日志 retention",[d])
        self.assertTrue(p.verify([d]))
        self.assertTrue(all(s.end-s.start <= 10 for s in p.spans))


class DifyTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"docs":demo_documents()},"local-test")

    def request(self,payload,auth="Bearer local-test",path="/retrieval"):
        raw = json.dumps(payload).encode()
        env = {"PATH_INFO":path,"REQUEST_METHOD":"POST","HTTP_AUTHORIZATION":auth,
               "CONTENT_LENGTH":str(len(raw)),"wsgi.input":io.BytesIO(raw)}
        status = []
        body = b"".join(self.app(env,lambda s,h:status.append(s)))
        return status[0],json.loads(body)

    def payload(self,**extra):
        return {"knowledge_id":"docs","query":"日志保留期限",
                "retrieval_setting":{"top_k":3,"score_threshold":0},**extra}

    def test_auth_and_unknown_source(self):
        self.assertTrue(self.request(self.payload(),auth="wrong")[0].startswith("401"))
        self.assertTrue(self.request(self.payload(knowledge_id="other"))[0].startswith("404"))

    def test_contract_and_filters(self):
        status,data = self.request(self.payload(metadata_condition={"conditions":[
            {"name":"language","comparison_operator":"is","value":"zh"}]}))
        self.assertEqual(status,"200 OK")
        self.assertTrue(data["records"])
        for row in data["records"]:
            self.assertEqual(row["metadata"]["language"],"zh")
            self.assertIn("source_sha256",row["metadata"]["evidence_pack"])
            self.assertTrue(0 <= row["score"] <= 1)

    def test_unsupported_filter_fails(self):
        status,_ = self.request(self.payload(metadata_condition={"conditions":[
            {"name":"x","comparison_operator":"unsupported","value":1}]}))
        self.assertTrue(status.startswith("400"))

    def test_bad_request_shape(self):
        for value in [[],None,{"knowledge_id":[]},self.payload(retrieval_setting={"top_k":True,"score_threshold":0})]:
            status,_ = self.request(value)
            self.assertTrue(status.startswith(("400","404")))


if __name__ == "__main__":
    unittest.main()
