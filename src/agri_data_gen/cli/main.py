import typer
from pathlib import Path
from agri_data_gen.core.data_access.taxonomy_manager import TaxonomyManager
from agri_data_gen.core.generators.generator import GenerationEngine
from agri_data_gen.core.knowledge.bundle_builder import BundleBuilder
from agri_data_gen.gemini_batch_processing.create_job import TextBatchJob

app = typer.Typer()



@app.command()
def load_taxonomies(taxonomy_dir: str = "sample_data/taxonomies"):
    """
    Loads taxonomy schemas into MongoDB and prints a summary.
    """

    print("Loading taxonomies...")
    manager = TaxonomyManager()
    manager.load_from_files_and_store(taxonomy_dir)

    taxonomies = manager.get_active_taxonomies()
    print(f"\nLoaded {len(taxonomies)} active taxonomies:\n")

    for t in taxonomies:
        print(f"Group: {t['group']}")
        print(f"  Attributes: {len(t['attributes'])}")
        print(f"  Entries: {len(t['entries'])}")
        print("-" * 40)

@app.command()
def reset_taxonomies():
    """
    Completely clears the taxonomy collection in MongoDB.
    Use before reloading taxonomies after schema changes.
    """
    manager = TaxonomyManager()
    deleted = manager.reset_taxonomy_collection()
    print(f"Deleted {deleted} taxonomy entries.")


@app.command()
def batch_run(bundle_file: str = "data/bundles/bundles.jsonl"):
    """
    Submits the generated bundles to Google Batch API.
    """
    # safety check
    if not Path(bundle_file).exists():
        print(f"Error: Input file not found: {bundle_file}")
        sys.exit(1)

    print(f"Submitting Batch Job for: {bundle_file}")
    
    processor = TextBatchJob()

    processor.create_jsonl(bundle_file) 
    job = processor.submit_job()

    # Just print the ID and exit
    print(f"Job Submitted! Job Name: {job.name}")
    print(f"   You can close this terminal now.")
    print(f"   Check status later with: python -m agri_data_gen.cli.main check-batch --job-name {job.name}")

@app.command()
def check_batch(job_name: str):
    """
    Step 2: Checks status and downloads if ready.
    """
    print(f"Checking status for: {job_name}")
    processor = TextBatchJob()
    # You'll need to update TextBatchJob to accept an existing job_name
    processor.batch_job = type('obj', (object,), {'name': job_name}) # Mocking the job object with just name
    
    print(f"Checking status for: {job_name}...")
    processor.wait_for_completion() # This loops until done
    processor.download_and_parse_results()



@app.command()
def pipeline_run(
    bundle_dir: str = "data/bundles", 
    output_dir: str = "data/generated",
    bundle_filename: str = "bundles.jsonl",
    output_filename: str = "data.jsonl",
    limit: int = None
):
    """
    Run the full end-to-end pipeline:
    taxonomies → bundles → generation
    """

    print("Starting end-to-end pipeline...")

    # Build bundles
    print("Building bundles...")
    bundle_builder = BundleBuilder(out_dir=bundle_dir)
    bundle_builder.load_all()
    generated_bundles_path = bundle_builder.build_all(filename= bundle_filename)

    # Generate data from bundles
    print("Generating reasoning data...")
    generated_bundles_path = Path(bundle_dir) / bundle_filename
    output_file = Path(output_dir)/output_filename
    engine = GenerationEngine(
            bundle_file=generated_bundles_path, 
            out_file=output_file,        
            rpm_limit=4, 
            max_workers=1
        )
    engine.generate_all(limit=limit)

    print("Pipeline completed successfully.")


def main():

    app()

if __name__ == "__main__":
    main()
