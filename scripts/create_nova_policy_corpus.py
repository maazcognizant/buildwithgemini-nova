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

"""Create a serverless Vertex AI RAG corpus for Nova IT Policy and import nova_it_policy.txt."""

import os
import vertexai
from vertexai.preview import rag
from vertexai.preview.rag.utils import resources as rr

PROJECT_ID = "qwiklabs-gcp-03-2f074985a624"
LOCATION = "us-central1"
GCS_PATH = "gs://nova-it-assets-qwiklabs-gcp-03-2f074985a624/rag/nova_it_policy.txt"

PARSING_PROMPT = (
    "Extract all IT policies, SLA definitions, escalation criteria, VPN troubleshooting steps, "
    "macOS troubleshooting guidelines, docking station fixes, new hire provisioning rules, "
    "and hardware/software request procedures from this text. "
    "Output clean, informative, self-contained prose."
)


def create_nova_policy_corpus():
    print(f"Initializing Vertex AI for project '{PROJECT_ID}' in '{LOCATION}'...")
    vertexai.init(project=PROJECT_ID, location=LOCATION)

    # 1. Serverless config
    cfg = f"projects/{PROJECT_ID}/locations/{LOCATION}/ragEngineConfig"
    try:
        rag.update_rag_engine_config(
            rag_engine_config=rag.RagEngineConfig(
                name=cfg,
                rag_managed_db_config=rag.RagManagedDbConfig(mode=rr.Serverless()),
            )
        )
        print("  ✓ Serverless mode enabled.")
    except Exception as e:
        print(f"  Config update note: {e}")

    # 2. Create corpus
    print("Creating RAG corpus 'nova-it-policy-kb'...")
    corpus = rag.create_corpus(
        display_name="nova-it-policy-kb",
        embedding_model_config=rag.EmbeddingModelConfig(
            publisher_model="publishers/google/models/text-embedding-005"
        ),
    )
    corpus_name = corpus.name
    print(f"  ✓ Corpus created successfully: {corpus_name}")

    # 3. Import and index nova_it_policy.txt
    print(f"Importing and indexing '{GCS_PATH}'...")
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

    # Save corpus name to data/corpus_config.txt
    os.makedirs("data", exist_ok=True)
    with open("data/corpus_config.txt", "w") as f:
        f.write(corpus_name.strip())
    print(f"\nSaved corpus resource name to data/corpus_config.txt: {corpus_name}")
    return corpus_name


if __name__ == "__main__":
    create_nova_policy_corpus()
