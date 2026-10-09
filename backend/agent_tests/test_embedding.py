"""测试 Embedding + 向量检索流程"""
import sys
sys.path.insert(0, 'D:/pythonproject/knowledgeforge/backend')

from agent.common.embedding import get_embedding_service
from agent.common.vector_store import get_vector_store

# 1. 测试 Embedding
print('1. 加载 Embedding 模型...')
service = get_embedding_service()
print(f'   维度: {service.dimension}')

# 2. 批量 Embedding
print('2. 批量 Embedding...')
texts = ['Java线程池', 'Activity生命周期', 'TCP三次握手', '今天天气不错']
vectors = service.embed_texts(texts)
print(f'   生成 {len(vectors)} 个向量')

# 3. 向量存储
print('3. 写入向量存储...')
store = get_vector_store(dimension=service.dimension)
for i, (text, vec) in enumerate(zip(texts, vectors)):
    store.upsert(f'k_{i}', vec, {'name': text})
print(f'   存储 {store.count()} 条记录')

# 4. 相似度检索
print('4. 相似度检索...')
query = service.embed_text('Java线程池核心参数')
results = store.search(query, top_k=3)
for r in results:
    name = r.metadata.get('name', '?')
    print(f'   {name}: {r.score:.4f}')

print('全部通过!')
