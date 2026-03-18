# 自动文档识别与分块 - 实现计划

## TL;DR

> **目标**：实现 `data/guidelines` 文件夹下自动识别多种格式文档并读取分块
>
> **交付**：
> - `src/utils/auto_document_loader.py` - 自动文档加载器
> - 集成到现有 `LlamaIndexDocumentLoader`
>
> **预计工作量**：Medium（约 2-3 小时）

---

## 背景

### 当前状态
- `data/guidelines` 目录下已有：
  - `clinical_guidelines.json` - JSON 格式指南
  - `ICH_E6(R3)_DraftGuideline_2023_0519.pdf` - PDF 文档
- 当前代码仅支持 JSON 格式加载

### 需求
- 自动识别文件夹下所有支持的文件格式
- 根据文件类型选择合适的解析器
- 统一输出为 Document/Node 列表

---

## 支持的文件格式

| 格式 | 扩展名 | 状态 |
|------|--------|------|
| JSON | `.json` | 已有 |
| PDF | `.pdf` | 待实现 |
| Markdown | `.md`, `.markdown` | 待实现 |
| 纯文本 | `.txt` | 待实现 |
| Word | `.doc`, `.docx` | 待实现 |
| Excel | `.xlsx`, `.xls` | 待实现 |
| CSV | `.csv` | 待实现 |
| HTML | `.html`, `.htm` | 待实现 |

---

## 工作任务

### Task 1: 创建自动文档识别加载器

**目标**：创建 `src/utils/auto_document_loader.py`

**实现内容**：
- `AutoDocumentLoader` 类
- `detect_document_type()` - 根据扩展名识别类型
- `load_file()` - 加载单个文件
- `load_directory()` - 批量加载目录

**代码结构**：
```python
class AutoDocumentLoader:
    """自动文档识别与加载器"""
    
    def __init__(self, chunk_size=512, chunk_overlap=50):
        ...
    
    def detect_document_type(self, file_path) -> DocumentType:
        """自动识别文档类型"""
        ...
    
    def load_file(self, file_path) -> List[Document]:
        """加载单个文件"""
        ...
    
    def load_directory(self, directory) -> List[Document]:
        """加载整个目录"""
        ...

# 便捷函数
def load_guidelines_directory(directory="./data/guidelines") -> List[BaseNode]:
    """加载指南目录并分块"""
    ...

def get_directory_stats(directory) -> Dict:
    """获取目录统计信息"""
    ...
```

### Task 2: 实现各类文件加载器

**目标**：为每种文件格式实现 `_load_{type}()` 方法

**实现内容**：

| 方法 | 功能 | 依赖库 |
|------|------|--------|
| `_load_json()` | JSON 解析 | 内置 |
| `_load_pdf()` | PDF 文本提取 | `pypdf` |
| `_load_markdown()` | Markdown 解析 | 内置 |
| `_load_text()` | 纯文本读取 | 内置 |
| `_load_docx()` | Word 文档 | `python-docx` |
| `_load_xlsx()` | Excel 表格 | `pandas`, `openpyxl` |
| `_load_csv()` | CSV 文件 | `pandas` |
| `_load_html()` | HTML 解析 | `beautifulsoup4` |

### Task 3: 集成到现有代码

**目标**：在 `LlamaIndexDocumentLoader` 中添加自动加载能力

**修改 `src/utils/llama_index_loader.py`**：

```python
# 添加新方法
def load_from_directory_auto(
    self, 
    directory: str = "./data/guidelines",
    recursive: bool = True,
) -> List[Document]:
    """自动识别并加载目录下的所有支持的文件"""
    from src.utils.auto_document_loader import AutoDocumentLoader
    
    loader = AutoDocumentLoader()
    return loader.load_directory(directory, recursive=recursive)
```

### Task 4: 添加命令行工具

**目标**：创建便捷脚本用于测试

**新建 `scripts/load_guidelines.py`**：

```python
#!/usr/bin/env python
"""加载指南目录的便捷脚本"""

import sys
sys.path.insert(0, ".")

from src.utils.auto_document_loader import load_guidelines_directory, get_directory_stats

def main():
    # 1. 显示目录统计
    print("=" * 60)
    print("指南目录统计")
    print("=" * 60)
    stats = get_directory_stats("./data/guidelines")
    print(f"总文件数: {stats['total_files']}")
    print(f"支持的文件: {stats['supported_files']}")
    print(f"按类型统计: {stats['by_type']}")
    print()
    
    # 2. 加载并分块
    print("=" * 60)
    print("加载并分块")
    print("=" * 60)
    nodes = load_guidelines_directory("./data/guidelines")
    print(f"总节点数: {len(nodes)}")
    
    # 3. 显示示例
    print()
    print("=" * 60)
    print("节点示例（前3个）")
    print("=" * 60)
    for i, node in enumerate(nodes[:3]):
        print(f"\n--- 节点 {i+1} ---")
        print(f"ID: {node.id_}")
        print(f"文本: {node.text[:200]}...")

if __name__ == "__main__":
    main()
```

---

## 依赖安装

需要安装的额外依赖（添加到 `requirements.txt`）：

```txt
# 文档解析
pypdf>=3.0.0          # PDF 解析
python-docx>=0.8.0    # Word 文档
beautifulsoup4>=4.12.0 # HTML 解析
lxml>=4.9.0           # XML/HTML 解析器

# 数据处理
openpyxl>=3.1.0       # Excel xlsx 支持
```

---

## 验证方案

### 场景 1: 目录统计

```bash
python -c "
from src.utils.auto_document_loader import get_directory_stats
import json
print(json.dumps(get_directory_stats('./data/guidelines'), indent=2))
"
```

**预期输出**：
```json
{
  "directory": "data/guidelines",
  "total_files": 3,
  "supported_files": 2,
  "by_type": {
    "json": 1,
    "pdf": 1
  }
}
```

### 场景 2: 加载并分块

```bash
python scripts/load_guidelines.py
```

**预期输出**：
```
============================================================
指南目录统计
============================================================
总文件数: 3
支持的文件: 2
按类型统计: {'json': 1, 'pdf': 1}

============================================================
加载并分块
============================================================
[INFO] 加载目录: data/guidelines
[INFO] 找到 2 个支持的文件
[OK] 加载 clinical_guidelines.json: 1 个文档
[OK] 加载 ICH_E6(R3)_DraftGuideline_2023_0519.pdf: 5 个文档
[OK] 共加载 6 个文档
[INFO] 开始分块 - 类型: sentence, 大小: 512, 重叠: 50
[OK] 分块完成 - 共 28 个节点
总节点数: 28
```

### 场景 3: 集成到 LlamaIndex

```python
from src.utils.llama_index_loader import LlamaIndexDocumentLoader

loader = LlamaIndexDocumentLoader()

# 使用新的自动加载方法
documents = loader.load_from_directory_auto("./data/guidelines")
print(f"加载了 {len(documents)} 个文档")
```

---

## 文件变更清单

| 文件 | 操作 |
|------|------|
| `src/utils/auto_document_loader.py` | **新建** - 自动文档加载器 |
| `src/utils/llama_index_loader.py` | **修改** - 添加 `load_from_directory_auto()` |
| `scripts/load_guidelines.py` | **新建** - 命令行工具 |
| `requirements.txt` | **修改** - 添加新依赖 |

---

## 成功标准

- [ ] 支持至少 5 种文件格式（JSON, PDF, TXT, MD, CSV）
- [ ] `load_directory()` 能正确识别和加载 `data/guidelines` 下的所有文件
- [ ] 分块后的节点保留正确的元数据
- [ ] 集成到 `LlamaIndexDocumentLoader` 成功
- [ ] 命令行工具能正常运行并输出统计信息
