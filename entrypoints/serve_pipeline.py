from pathlib import Path

from irsol_data_pipeline.orchestration.flows import process_unprocessed_measurements


def main():

    root_path = Path(__file__).parent.parent
    # Example usage: run the dataset scan flow
    process_unprocessed_measurements.serve(
        name="run-processing-pipeline",
        parameters={"root": str(root_path / "data")},
        description="Run the data processing pipeline on all unprocessed measurements.",
    )


if __name__ == "__main__":
    main()
