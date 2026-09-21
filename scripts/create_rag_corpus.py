# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Create a serverless Vertex AI RAG Engine corpus and import knowledge base file from GCS."""

import vertexai
from vertexai.preview import rag
from vertexai.preview.rag.utils import resources as rr

PROJECT_ID = "qwiklabs-gcp-03-2f074985a624"
LOCATION = "us-central1"
GCS_PATH = "gs://nova-it-assets-qwiklabs-gcp-03-2f074985a624/rag/pg49513.txt"

PARSING_PROMPT = (
    "Extract all key facts, instructions, policies, remedies, procedures, and troubleshooting guidelines in this text. "
    "Ignore boilerplate header/footer licensing text. "
    "Output clean, self-contained informative prose."
)


def create_and_import_corpus():
    print(f"Initializing Vertex AI for project '{PROJECT_ID}' in location '{LOCATION}'...")
    vertexai.init(project=PROJECT_ID, location=LOCATION)

    # 1. Ensure serverless mode configuration
    cfg = f"projects/{PROJECT_ID}/locations/{LOCATION}/ragEngineConfig"
    try:
        rag.update_rag_engine_config(
            rag_engine_config=rag.RagEngineConfig(
                name=cfg,
                rag_managed_db_config=rag.RagManagedDbConfig(mode=rr.Serverless()),
            )
        )
        print("  ✓ Serverless mode enabled for region's RAG Engine config.")
    except Exception as e:
        print(f"  Note on ragEngineConfig: {e}")

    # 2. Create the serverless RAG corpus
    print("Creating serverless RAG corpus 'nova-it-knowledge-base'...")
    corpus = rag.create_corpus(
        display_name="nova-it-knowledge-base",
        embedding_model_config=rag.EmbeddingModelConfig(
            publisher_model="publishers/google/models/text-embedding-005"
        ),
    )
    corpus_name = corpus.name
    print(f"  ✓ Corpus created successfully: {corpus_name}")

    # 3. Import, parse, chunk, and embed the document
    print(f"Importing and indexing document from '{GCS_PATH}' into corpus...")
    import_resp = rag.import_files(
        corpus_name=corpus_name,
        paths=[GCS_PATH],
        transformation_config=rag.TransformationConfig(
            chunking_config=rag.ChunkingConfig(chunk_size=512, chunk_overlap=100)
        ),
        llm_parser=rag.LlmParserConfig(
            model_name="gemini-2.5-flash",
            custom_parsing_prompt=PARSING_PROMPT,
        ),
    )
    print(f"  ✓ Successfully imported files! Count: {getattr(import_resp, 'imported_rag_files_count', 1)}")

    # Write corpus resource name to a local config file for easy reference
    with open("data/corpus_config.txt", "w") as f:
        f.write(corpus_name.strip())
    print(f"\nSaved corpus resource name to data/corpus_config.txt: {corpus_name}")
    return corpus_name


if __name__ == "__main__":
    create_and_import_corpus()
