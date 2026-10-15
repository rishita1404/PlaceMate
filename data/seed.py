"""
data/seed.py
─────────────
One-time script to load sample_jobs.json into the database.

Run with:
  .venv/bin/python -m data.seed

This is safe to run multiple times — it skips jobs that already exist
(matched by company name + title combination).
"""

import asyncio
import json
import sys
from pathlib import Path

# Make sure the project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal, init_db
from app.models import Company, Job, JobSource, ListingStatus


async def seed():
    await init_db()

    seed_file = Path(__file__).parent / "sample_jobs.json"
    jobs_data = json.loads(seed_file.read_text())

    async with AsyncSessionLocal() as db:
        for item in jobs_data:
            from sqlalchemy import select

            # Get or create company
            result = await db.execute(
                select(Company).where(Company.name == item["company_name"])
            )
            company = result.scalar_one_or_none()
            if company is None:
                company = Company(name=item["company_name"])
                db.add(company)
                await db.flush()
                await db.refresh(company)

            # Get or create seed source
            source_result = await db.execute(
                select(JobSource).where(
                    JobSource.company_id == company.id,
                    JobSource.source_type == "seed",
                )
            )
            source = source_result.scalar_one_or_none()
            if source is None:
                source = JobSource(
                    company_id=company.id,
                    source_url=f"seed://local/{company.name}",
                    source_type="seed",
                    import_status="ok",
                )
                db.add(source)
                await db.flush()
                await db.refresh(source)

            # Skip if a job with this title already exists for this company
            existing = await db.execute(
                select(Job).where(
                    Job.company_id == company.id,
                    Job.title == item["title"],
                )
            )
            if existing.scalar_one_or_none() is not None:
                print(f"  Skipping (already exists): {item['title']} @ {item['company_name']}")
                continue

            job = Job(
                company_id=company.id,
                source_id=source.id,
                title=item["title"],
                description=item.get("description"),
                location=item.get("location"),
                job_type=item.get("job_type"),
                official_url=item.get("official_url"),
                listing_status=ListingStatus.active,
            )
            job.required_skills = item.get("required_skills", [])
            job.preferred_skills = item.get("preferred_skills", [])
            job.eligibility_requirements = item.get("eligibility_requirements", {})

            db.add(job)
            print(f"  Added: {item['title']} @ {item['company_name']}")

        await db.commit()

    print("\n✅  Seed data loaded successfully.")


if __name__ == "__main__":
    asyncio.run(seed())
