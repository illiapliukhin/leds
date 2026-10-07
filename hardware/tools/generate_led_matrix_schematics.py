from pathlib import Path
import subprocess

from kicad_sch_api import Schematic

from generate_led_driver_schematics import (
    MATRIX_VARIANTS,
    MHPA1010_FOOTPRINT,
    MHPA1010_LIBRARY_ID,
    MatrixVariant,
    add_component,
    add_pin_label,
    configure_symbol_cache,
    deterministic_uuid,
    generate_custom_symbol_library,
    write_project_library_tables,
)


SCHEMATIC_GRID_MM = 20.32
SCHEMATIC_ORIGIN_MM = 20.32


def get_led_reference(
    variant: MatrixVariant,
    row_number: int,
    column_number: int,
) -> str:
    reference_number = (
        (row_number - 1) * variant.matrix_size + column_number
    )
    return f"D{reference_number}"


def get_led_position(
    row_number: int,
    column_number: int,
) -> tuple[float, float]:
    return (
        SCHEMATIC_ORIGIN_MM + (column_number - 1) * SCHEMATIC_GRID_MM,
        SCHEMATIC_ORIGIN_MM + (row_number - 1) * SCHEMATIC_GRID_MM,
    )


def add_led_matrix(
    schematic: Schematic,
    generation_key: str,
    variant: MatrixVariant,
) -> None:
    for row_number in range(1, variant.matrix_size + 1):
        for column_number in range(1, variant.matrix_size + 1):
            reference = get_led_reference(
                variant,
                row_number,
                column_number,
            )
            add_component(
                schematic,
                generation_key=generation_key,
                library_id=MHPA1010_LIBRARY_ID,
                reference=reference,
                value="MHPA1010RGBDT",
                position=get_led_position(row_number, column_number),
                footprint=MHPA1010_FOOTPRINT,
            )
            add_pin_label(
                schematic,
                generation_key,
                reference,
                "1",
                f"ROW_{row_number:02d}_ANODE",
            )
            add_pin_label(
                schematic,
                generation_key,
                reference,
                "2",
                f"COL_R_{column_number:02d}",
            )
            add_pin_label(
                schematic,
                generation_key,
                reference,
                "3",
                f"COL_G_{column_number:02d}",
            )
            add_pin_label(
                schematic,
                generation_key,
                reference,
                "4",
                f"COL_B_{column_number:02d}",
            )


def generate_variant_matrix_schematic(
    repository_root: Path,
    variant: MatrixVariant,
) -> Path:
    generation_key = f"led-matrix:{variant.directory_name}"
    output_directory = repository_root / "hardware" / variant.directory_name
    output_path = output_directory / "led_matrix.kicad_sch"
    output_directory.mkdir(parents=True, exist_ok=True)
    write_project_library_tables(output_directory, project_name="led_matrix")

    schematic = Schematic.create(
        name=f"{variant.directory_name} LED matrix",
        uuid=deterministic_uuid(f"{generation_key}:schematic"),
        paper="A1",
    )
    schematic.set_title_block(
        title=f"{variant.matrix_size}x{variant.matrix_size} RGB LED matrix",
        date="2026-10-07",
        rev="A",
        company="Part Signal",
        comments={
            1: "MHPA1010RGBDT common-anode matrix",
            2: "Generated; edit hardware/tools/generate_led_matrix_schematics.py",
        },
    )
    add_led_matrix(schematic, generation_key, variant)
    schematic.save(output_path)

    subprocess.run(
        ("kicad-cli", "sch", "upgrade", "--force", str(output_path)),
        check=True,
        cwd=output_directory,
    )
    return output_path


def main() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    generate_custom_symbol_library()
    configure_symbol_cache()

    for variant in MATRIX_VARIANTS:
        generated_path = generate_variant_matrix_schematic(
            repository_root,
            variant,
        )
        print(f"Generated {generated_path}")


if __name__ == "__main__":
    main()
