import pytest
from unittest.mock import MagicMock, patch
from src.infrastructure.persistence.chroma_repo import ChromaRepository
from src.core.entities import FichaEstructurada

@pytest.fixture
def mock_chroma_client():
    """Mocks the ChromaDB PersistentClient."""
    with patch("src.infrastructure.persistence.chroma_repo.chromadb.PersistentClient") as mock_client:
        # Setup the chain: Client -> Collection
        mock_instance = mock_client.return_value
        mock_collection = MagicMock()
        mock_instance.get_or_create_collection.return_value = mock_collection
        yield mock_instance, mock_collection

@pytest.fixture
def mock_sentence_transformer():
    """Mocks the SentenceTransformer model to avoid loading weights."""
    with patch("src.infrastructure.persistence.chroma_repo.SentenceTransformer") as mock_model:
        mock_instance = mock_model.return_value
        # Mock encode to return an object that has a .tolist() method (like a numpy array)
        mock_embedding = MagicMock()
        mock_embedding.tolist.return_value = [0.1, 0.2, 0.3]
        mock_instance.encode.return_value = mock_embedding
        yield mock_instance

@pytest.fixture
def chroma_repo(mock_chroma_client, mock_sentence_transformer):
    """Provides a ChromaRepository instance with mocked external dependencies."""
    return ChromaRepository()

def test_indexar_creates_collection(mock_chroma_client):
    """
    Requirement: 4.2 Implement test_indexar_creates_collection if not exists.
    Verify that the repository creates/gets the collection upon initialization.
    """
    client, collection = mock_chroma_client
    # We need to instantiate the repo to trigger the call
    repo = ChromaRepository()
    client.get_or_create_collection.assert_called_once_with("expedientes")

def test_indexar_upserts_with_embedding(chroma_repo, mock_chroma_client, mock_sentence_transformer):
    """
    Requirement: 4.3 Implement test_indexar_upserts_with_embedded_vector representation.
    Verify that the text is encoded and upserted to ChromaDB.
    """
    _, collection = mock_chroma_client
    doc_id = "test-doc-123"
    archivo = "test.pdf"
    ficha = FichaEstructurada(resumen_ejecutivo="Resumen prueba", fragmentos_clave=["Frag 1"])

    chroma_repo.indexar(doc_id, archivo, ficha)

    # Verify model was used for encoding
    mock_sentence_transformer.encode.assert_called_once()

    # Verify upsert was called with correct data
    collection.upsert.assert_called_once()
    args, kwargs = collection.upsert.call_args

    # The implementation uses: embeddings=[embedding]
    # where embedding is [0.1, 0.2, 0.3]
    # So kwargs['embeddings'] should be [[0.1, 0.2, 0.3]]
    assert kwargs['ids'] == [doc_id]
    assert kwargs['embeddings'] == [[0.1, 0.2, 0.3]]
    assert "Resumen prueba" in kwargs['documents'][0]

def test_indexar_includes_metadata(chroma_repo, mock_chroma_client):
    """
    Requirement: 4.4 Implement test_indexar_includes_metadata from FichaEstructurada fields.
    Verify that document metadata is correctly mapped to ChromaDB metadatas.
    """
    _, collection = mock_chroma_client
    doc_id = "test-meta-123"
    archivo = "meta.pdf"
    ficha = FichaEstructurada(
        resumen_ejecutivo="Resumen",
        fecha_documento="2023-01-01",
        organismo_emisor="Org A",
        confiabilidad_extraccion="alta"
    )

    chroma_repo.indexar(doc_id, archivo, ficha)

    args, kwargs = collection.upsert.call_args
    metadatas = kwargs['metadatas'][0]

    assert metadatas['archivo_origen'] == archivo
    assert metadatas['fecha_documento'] == "2023-01-01"
    assert metadatas['organismo_emisor'] == "Org A"
    assert metadatas['confiabilidad_extraccion'] == "alta"

def test_indexar_skips_when_no_indexable_text(chroma_repo, mock_chroma_client):
    """
    Requirement: 4.5 Implement test_indexar_skips_when_no_indexable_text present.
    Verify that the system skips indexing if there is no text content.
    """
    _, collection = mock_chroma_client
    doc_id = "test-empty-123"
    ficha = FichaEstructurada(resumen_ejecutivo="  ", fragmentos_clave=[])

    chroma_repo.indexar(doc_id, "empty.pdf", ficha)

    # Upsert should NOT be called
    collection.upsert.assert_not_called()
