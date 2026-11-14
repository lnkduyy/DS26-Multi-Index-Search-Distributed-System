from enrich_recipes import process
from upload_recipes import index_jsonl
from qdrant_client import QdrantClient

INPUT_FILES = [] # recipes from user's input 
OUTPUT_PATH = "recipes_rag_enriched.jsonl"

qdrant_api_key = ""

qdrant_client = QdrantClient(
    url="https://cf19a9b2-fef9-49a9-96b2-003c18348045.eu-central-1-0.aws.cloud.qdrant.io:6333",
    api_key=qdrant_api_key,
)

# Process raw json 
process(
    INPUT_FILES,  
    OUTPUT_PATH, 
    qdrant_client=qdrant_client,
    nutrition_collection="nutrition",
)

# Upload to Qdrant cloud
index_jsonl(OUTPUT_PATH)