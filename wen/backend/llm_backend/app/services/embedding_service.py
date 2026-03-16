from typing import Dict, List
import aiohttp
import asyncio
import numpy as np
import faiss
import json
from pathlib import Path
import hashlib
import time
import PyPDF2
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

class EmbeddingService:
    def __init__(self):
        # 使用 Ollama 的 Qwen3 Embedding 模型
        self.base_url = settings.OLLAMA_BASE_URL or "http://localhost:11434"
        self.model = settings.OLLAMA_EMBEDDING_MODEL or "qwen3-embedding:4b"
        self.dimension = 2560  # Qwen3-embedding 的向量维度

        self.index_dir = Path("indexes")
        self.index_dir.mkdir(exist_ok=True)

        # 初始化空索引和文档存储
        self.current_index = None
        self.current_documents = {}

        logger.info(f"EmbeddingService initialized with model: {self.model}")

    async def get_embedding(self, text: str) -> List[float]:
        """通过 Ollama API 获取单个文本的 embedding"""
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    "model": self.model,
                    "input": text
                }

                async with session.post(f"{self.base_url}/api/embed", json=data) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        embedding = result.get('embedding', [])
                        logger.debug(f"Got embedding with dimension: {len(embedding)}")
                        return embedding
                    else:
                        error_text = await resp.text()
                        logger.error(f"Failed to get embedding: {error_text}")
                        return []
        except Exception as e:
            logger.error(f"Error getting embedding: {e}")
            return []

    async def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """批量获取 embeddings"""
        embeddings = []
        for text in texts:
            emb = await self.get_embedding(text)
            if emb:
                embeddings.append(emb)
            else:
                # 如果失败，返回零向量
                embeddings.append([0.0] * self.dimension)
            # 避免请求过快
            await asyncio.sleep(0.1)
        return embeddings

    def _generate_safe_id(self, metadata: dict) -> str:
        """生成安全的文件ID"""
        timestamp = str(int(time.time()))
        file_info = f"{metadata.get('filename', '')}_{timestamp}"
        return hashlib.md5(file_info.encode()).hexdigest()

    def _create_index(self) -> faiss.IndexFlatL2:
        """创建新的 FAISS 索引"""
        return faiss.IndexFlatL2(self.dimension)

    async def create_embeddings(self, file_path: str, index_dir: str) -> Dict:
        """从文件创建向量索引"""
        try:
            logger.info(f"Creating embeddings for file: {file_path}")

            # 读取 PDF 文件内容
            text_chunks = []
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                for i, page in enumerate(pdf_reader.pages):
                    text = page.extract_text()
                    if text.strip():  # 只添加非空页
                        text_chunks.append(text)
                    logger.debug(f"Extracted page {i + 1}: {len(text)} chars")

            logger.info(f"Extracted {len(text_chunks)} text chunks from PDF")

            # 创建索引
            index = self._create_index()

            # 使用 Ollama 生成向量
            logger.info(f"Generating embeddings for {len(text_chunks)} chunks...")
            vectors = await self.get_embeddings_batch(text_chunks)

            # 转换为 numpy 数组并确保类型正确
            vectors_array = np.array(vectors, dtype='float32')
            logger.info(f"Generated embeddings shape: {vectors_array.shape}")

            # 添加向量到索引
            index.add(vectors_array)

            # 生成文件 ID
            file_hash = hashlib.md5(file_path.encode()).hexdigest()
            index_id = f"index_{file_hash}"

            # 创建文档数据
            documents = {}
            for i, text in enumerate(text_chunks):
                documents[str(i)] = {
                    "text": text,
                    "metadata": {
                        "page": i + 1,
                        "source": file_path,
                        "chunk_size": len(text)
                    }
                }

            # 保存索引和文档数据
            await self._save_index(file_hash, index, documents)

            logger.info(f"Successfully created index with {len(text_chunks)} vectors")

            return {
                "status": "success",
                "index_id": index_id,
                "chunks": len(text_chunks),
                "dimension": self.dimension
            }

        except Exception as e:
            logger.error(f"Failed to create embeddings: {e}")
            raise Exception(f"创建向量失败: {str(e)}")

    async def _save_index(self, file_id: str, index: faiss.Index, documents: dict):
        """保存索引和文档数据"""
        try:
            index_path = self.index_dir / f"index_{file_id}.bin"
            docs_path = self.index_dir / f"docs_{file_id}.json"

            # 保存 FAISS 索引
            faiss.write_index(index, str(index_path))
            logger.info(f"Saved index to {index_path}")

            # 保存文档数据
            with open(docs_path, 'w', encoding='utf-8') as f:
                json.dump(documents, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved documents to {docs_path}")

        except Exception as e:
            logger.error(f"Failed to save index: {e}")
            raise Exception(f"保存索引失败: {str(e)}")

    async def load_index(self, index_id: str):
        """加载索引和文档数据"""
        try:
            # 从 index_id 提取文件 hash
            file_hash = index_id.replace('index_', '')
            index_path = self.index_dir / f"index_{file_hash}.bin"
            docs_path = self.index_dir / f"docs_{file_hash}.json"

            if not index_path.exists():
                raise FileNotFoundError(f"Index file not found: {index_path}")
            if not docs_path.exists():
                raise FileNotFoundError(f"Documents file not found: {docs_path}")

            # 加载索引
            self.current_index = faiss.read_index(str(index_path))
            logger.info(f"Loaded index with {self.current_index.ntotal} vectors")

            # 验证索引维度
            if self.current_index.d != self.dimension:
                logger.warning(f"Dimension mismatch: expected {self.dimension}, got {self.current_index.d}")

            # 加载文档数据
            with open(docs_path, 'r', encoding='utf-8') as f:
                self.current_documents = json.load(f)

            logger.info(
                f"Successfully loaded index {index_id}: {self.current_index.ntotal} vectors, {len(self.current_documents)} documents")

        except Exception as e:
            self.current_index = None
            self.current_documents = {}
            logger.error(f"Failed to load index: {e}")
            raise Exception(f"加载索引失败: {str(e)}")

    async def search(self, query: str, top_k: int = 3) -> List[dict]:
        """搜索最相关的文档片段"""
        try:
            if not self.current_index:
                raise Exception("未加载索引，请先调用 load_index")

            # 生成查询向量
            logger.info(f"Searching for: {query}")
            query_vector = await self.get_embedding(query)
            if not query_vector:
                raise Exception("Failed to generate query embedding")

            query_array = np.array([query_vector], dtype='float32')

            # 搜索最相似的向量
            distances, indices = self.current_index.search(query_array, min(top_k, self.current_index.ntotal))

            # 返回结果
            results = []
            for i in range(len(indices[0])):
                idx = indices[0][i]
                if idx >= 0 and str(idx) in self.current_documents:
                    doc = self.current_documents[str(idx)]
                    results.append({
                        "score": float(1.0 / (1.0 + distances[0][i])),  # 转换为相似度分数
                        "distance": float(distances[0][i]),
                        "content": doc["text"],
                        "metadata": doc["metadata"]
                    })

            logger.info(f"Found {len(results)} results for query")
            return results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise Exception(f"搜索失败: {str(e)}")

    async def close(self):
        """清理资源"""
        self.current_index = None
        self.current_documents = {}
        logger.info("EmbeddingService closed")