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

"""Seed Firestore 'tickets' collection with initial sample IT support tickets."""

import datetime
from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-03-2f074985a624"

SAMPLE_TICKETS = [
    {
        "ticket_id": "TICKET-1001",
        "employee_name": "Sarah Jenkins",
        "department": "Engineering",
        "role": "Senior DevOps Engineer",
        "issue_description": "Production Kubernetes cluster latency spike and container crash-looping in us-central1",
        "priority": "P1",
        "status": "open",
        "assigned_team": "Site Reliability Engineering (SRE)",
        "created_at": "2026-09-21T18:30:00Z",
        "sla_deadline": "2026-09-21T19:30:00Z",
    },
    {
        "ticket_id": "TICKET-1002",
        "employee_name": "Marcus Vance",
        "department": "Finance",
        "role": "Financial Controller",
        "issue_description": "Global corporate VPN connection dropping every 10 minutes on macOS Sequoia",
        "priority": "P3",
        "status": "in-progress",
        "assigned_team": "Network Operations",
        "created_at": "2026-09-21T14:15:00Z",
        "sla_deadline": "2026-09-22T14:15:00Z",
    },
    {
        "ticket_id": "TICKET-1003",
        "employee_name": "Elena Rostova",
        "department": "Human Resources",
        "role": "VP of People Operations",
        "issue_description": "New hire onboarding access provisioning delayed for 5 executive sales reps",
        "priority": "P2",
        "status": "escalated",
        "assigned_team": "Identity & Access Management (IAM)",
        "created_at": "2026-09-21T10:00:00Z",
        "sla_deadline": "2026-09-21T14:00:00Z",
    },
    {
        "ticket_id": "TICKET-1004",
        "employee_name": "David Chen",
        "department": "Product Management",
        "role": "Lead Product Manager",
        "issue_description": "Figma enterprise license assignment request for Q4 design sprint",
        "priority": "P4",
        "status": "resolved",
        "assigned_team": "IT Software Procurement",
        "created_at": "2026-09-20T09:00:00Z",
        "sla_deadline": "2026-09-23T09:00:00Z",
    },
]


def seed_database():
    db = firestore.Client(project=PROJECT_ID)
    print(f"Connecting to Firestore for project '{PROJECT_ID}'...")

    collection_ref = db.collection("tickets")
    for ticket in SAMPLE_TICKETS:
        doc_ref = collection_ref.document(ticket["ticket_id"])
        doc_ref.set(ticket)
        print(f"  ✓ Seeded ticket: {ticket['ticket_id']} ({ticket['priority']} - {ticket['status']})")

    print("\n✅ Successfully seeded 4 example IT support tickets in Firestore!")


if __name__ == "__main__":
    seed_database()
