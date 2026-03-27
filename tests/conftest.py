import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_llama_index_loader():
    """Fixture providing a mocked LlamaIndexDocumentLoader."""
    mock = MagicMock()
    mock.load_from_json.return_value = []
    mock.load_from_directory.return_value = []
    mock.create_nodes.return_value = []
    mock.build_index.return_value = None
    return mock


@pytest.fixture
def rag_service_with_mock_loader(mock_llama_index_loader):
    """Fixture providing a RAGService instance with mocked loader."""
    from src.services.rag_service import RAGService

    service = RAGService()
    # Replace the loader property with our mock
    service._loader = mock_llama_index_loader
    return service
