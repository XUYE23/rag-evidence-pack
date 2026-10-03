# RAG Evidence Pack

面向中英文 RAG 的可追溯证据压缩工具，核心零第三方依赖。

安装：python -m pip install .
演示：rag-evidence-pack demo --output outputs/demo.json
测试：python -m unittest discover -s tests -v

功能：BM25 词法排序、重复片段消除、预算内多样性选择、原文位置与哈希校验、
Dify 外部知识接口。默认预算单位为 UTF-8 字节；模型 token 预算可接入对应分词器。
计费范围包含引用标记与分隔符。

示例为手工构造的运维文档，报告可验证节省字节数和原文一致性。
同义词、跨语言语义召回与回答准确率需要单独评估。
来源校验用于确认片段出处；原文真实性、回答蕴含关系仍需上层业务验证。

详见英文 README 和 docs/dify.md。
