import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from langchain_community.embeddings import DashScopeEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pymilvus import connections, utility

logger = logging.getLogger(__name__)


# 使用 langchain-milvus 新包（类名是 Milvus，不是 MilvusVectorStore）
try:
    from langchain_milvus import Milvus as _MilvusVectorStore
    _MILVUS_BACKEND = "langchain_milvus"
except ImportError:
    from langchain_community.vectorstores import Milvus as _MilvusVectorStore
    _MILVUS_BACKEND = "langchain_community"


@dataclass(frozen=True)
class RAGConfig:
    milvus_host: str = "127.0.0.1"
    milvus_port: int = 19530
    collection_name: str = "mult_agent_knowledge"
    embedding_model: str = "text-embedding-v1"
    chunk_size: int = 500
    chunk_overlap: int = 50


class RAGSystem:
    #流程是：
    #1. 初始化 RAGSystem，连接 Milvus 数据库，设置嵌入模型和文本分割器。
    #2. 调用 search 方法进行相似性搜索，返回前 k 条最相关的文档记录。
    #3. 调用 add_documents 方法将新的文档添加到 Milvus 数据库中。
    #4. 调用 ingest_text 方法将文本内容分割成文档并添加到 Milvus 数据库中。
    #5. 调用 ingest_paths 方法将指定路径下的文本文件分割成文档并添加到 Milvus 数据
    def __init__(self, api_key: str, config: Optional[RAGConfig] = None):
        self.config = config or RAGConfig()
        self.api_key = api_key
        self.embeddings = DashScopeEmbeddings(
            model=self.config.embedding_model,
            dashscope_api_key=self.api_key,
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
        )
        self._connect_to_milvus()
        self.vectorstore = _MilvusVectorStore(
            embedding_function=self.embeddings,
            collection_name=self.config.collection_name,
            connection_args={"uri": f"http://{self.config.milvus_host}:{self.config.milvus_port}"},
            auto_id=True,
        )
        logger.info("RAG backend=%s | collection=%s", _MILVUS_BACKEND, self.config.collection_name)

    def _connect_to_milvus(self) -> None:
        try:
            connections.connect(
                alias="default",
                host=self.config.milvus_host,
                port=self.config.milvus_port,
            )
        except Exception as exc:
            logger.error("连接 Milvus 失败: %s", exc)

#这个函数主要是用于在本地知识库中对用户的查询进行相似性搜索
# 并返回前k条最相关的文档记录。具体步骤如下：
#1. 调用search_records函数执行相似性搜索，获取前k条最相关的文档记录。
#2. 如果没有找到相关记录，则返回提示信息“未找到相关信息。”。
#3. 如果找到了相关记录，则将每条记录的摘要和来源信息整理为字符串列表
# 并返回给调用者。
    def search(self, query: str, k: int = 3) -> str:
        try:
            records = self.search_records(query, k=k)
            if not records:
                return "未找到相关信息。"
            lines: list[str] = ["检索到的相关信息："]
            for idx, record in enumerate(records, 1):
                lines.append(f"{idx}. {record['snippet']}")
                lines.append(f"   (来源: {record['doc_id']})")
            return "\n".join(lines)
        except Exception as exc:
            logger.error("检索失败: %s", exc)
            return f"检索过程中发生错误: {str(exc)}"

#在文档里对query进行相似性搜索，返回前k条最相关的文档记录，并将其整理为字典列表，每条记录包含source_id、doc_id、title、snippet、source_type和metadata等信息。
    def search_records(self, query: str, k: int = 5) -> list[dict]:
        if not utility.has_collection(self.config.collection_name):
            return []
        docs = self.vectorstore.similarity_search(query, k=k)
        records: list[dict] = []
        for idx, doc in enumerate(docs, 1):
            metadata = doc.metadata or {}
            source = str(metadata.get("source") or "").strip()
            title = Path(source).name if source else f"本地知识片段-{idx}"
            records.append(
                {
                    "source_id": f"LOC-{idx}",
                    "doc_id": source,
                    "title": title,
                    "snippet": doc.page_content,
                    "source_type": "local",
                    "metadata": metadata,
                }
            )
        return records

    def add_documents(self, documents: list[Document]) -> int:
        self.vectorstore.add_documents(documents)
        return len(documents)

    def ingest_text(self, text: str, source: str) -> int:
        docs = self.text_splitter.create_documents([text], metadatas=[{"source": source}])
        return self.add_documents(docs)

    def ingest_paths(self, paths: Iterable[Path]) -> int:
        total = 0
        for path in paths:
            text = path.read_text(encoding="utf-8")
            total += self.ingest_text(text, source=str(path))
        return total
