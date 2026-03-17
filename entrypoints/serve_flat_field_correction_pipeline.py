from pathlib import Path

from prefect import serve

from irsol_data_pipeline.orchestration.flows.flat_field_correction import (
    process_daily_unprocessed_measurements,
    process_unprocessed_measurements,
)


def main():

    root_path = Path(__file__).parent.parent

    process_unprocessed_measurment_deployment = process_unprocessed_measurements.to_deployment(
        name="run-flat-field-correction-pipeline",
        parameters={"root": str(root_path / "data")},
        description="Run the flat field correction pipeline on all unprocessed measurements.",
    )

    process_daily_unprocessed_measurement_deployment = process_daily_unprocessed_measurements.to_deployment(
        name="run-daily-flat-field-correction-pipeline",
        description="Run the flat field correction pipeline on a specific day folder.",
    )

    serve(
        process_unprocessed_measurment_deployment,
        process_daily_unprocessed_measurement_deployment,
    )


if __name__ == "__main__":
    main()
