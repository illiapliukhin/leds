import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Variant:
    name: str
    matrix_size: int
    serialized_bits_per_row: int
    target_refresh_hz: float


@dataclass(frozen=True)
class ModelResult:
    variant: str
    peak_row_current_a: float
    led_rail_power_w: float
    pmos_drop_v: float
    aggregate_pmos_loss_w: float
    shift_time_per_frame_us: float
    blank_time_per_frame_us: float
    lsb_hold_time_us: float
    msb_hold_time_us: float
    battery_current_min_v_a: float
    converter_loss_w: float
    converter_open_board_rise_c: float
    brightness_limit_at_1w: float
    brightness_limit_at_1_2w: float


VARIANTS = (
    Variant(
        name="wearable_20x20",
        matrix_size=20,
        serialized_bits_per_row=96,
        target_refresh_hz=175.0,
    ),
    Variant(
        name="wearable_28x28",
        matrix_size=28,
        serialized_bits_per_row=96,
        target_refresh_hz=115.0,
    ),
)

OUTPUT_VOLTAGE_V = 4.099
DRIVER_REFERENCE_VOLTAGE_V = 1.23
DRIVER_CURRENT_GAIN = 15
DRIVER_REFERENCE_RESISTANCE_OHM = 1_910
CHANNEL_CURRENT_A = (
    DRIVER_REFERENCE_VOLTAGE_V
    * DRIVER_CURRENT_GAIN
    / DRIVER_REFERENCE_RESISTANCE_OHM
)
COLOR_CHANNELS_PER_PIXEL = 3
PHYSICAL_BIT_PLANES = 6
SPI_CLOCK_HZ = 20_000_000
ROW_DEAD_TIME_US = 1.5
PMOS_WORST_CASE_RESISTANCE_OHM = 0.200
MINIMUM_BATTERY_VOLTAGE_V = 3.15
NOMINAL_CONVERTER_EFFICIENCY = 0.90
TPS63802_THERMAL_RESISTANCE_C_PER_W = 81.0
WEARABLE_CONTINUOUS_LIMITS_W = (1.0, 1.2)


def validate_variant(variant: Variant) -> None:
    expected_serialized_bits = (
        (variant.matrix_size + 15)
        // 16
        * 16
        * COLOR_CHANNELS_PER_PIXEL
    )
    if variant.serialized_bits_per_row != expected_serialized_bits:
        raise ValueError(
            f"{variant.name}: expected {expected_serialized_bits} serialized "
            "bits for color-homogeneous 16-channel drivers"
        )


def calculate_model_result(variant: Variant) -> ModelResult:
    peak_row_current_a = (
        variant.matrix_size * COLOR_CHANNELS_PER_PIXEL * CHANNEL_CURRENT_A
    )
    led_rail_power_w = peak_row_current_a * OUTPUT_VOLTAGE_V
    pmos_drop_v = peak_row_current_a * PMOS_WORST_CASE_RESISTANCE_OHM
    aggregate_pmos_loss_w = (
        peak_row_current_a
        * peak_row_current_a
        * PMOS_WORST_CASE_RESISTANCE_OHM
    )

    frame_period_us = 1_000_000 / variant.target_refresh_hz
    shift_time_per_frame_us = (
        variant.serialized_bits_per_row
        * variant.matrix_size
        * PHYSICAL_BIT_PLANES
        / SPI_CLOCK_HZ
        * 1_000_000
    )
    blank_time_per_frame_us = (
        ROW_DEAD_TIME_US * variant.matrix_size * PHYSICAL_BIT_PLANES
    )
    hold_budget_us = (
        frame_period_us - shift_time_per_frame_us - blank_time_per_frame_us
    )
    weighted_bit_plane_sum = (2**PHYSICAL_BIT_PLANES) - 1
    lsb_hold_time_us = hold_budget_us / (
        variant.matrix_size * weighted_bit_plane_sum
    )
    msb_hold_time_us = lsb_hold_time_us * 2 ** (PHYSICAL_BIT_PLANES - 1)

    battery_current_min_v_a = led_rail_power_w / (
        MINIMUM_BATTERY_VOLTAGE_V * NOMINAL_CONVERTER_EFFICIENCY
    )
    converter_loss_w = led_rail_power_w * (
        (1 / NOMINAL_CONVERTER_EFFICIENCY) - 1
    )
    converter_open_board_rise_c = (
        converter_loss_w * TPS63802_THERMAL_RESISTANCE_C_PER_W
    )

    return ModelResult(
        variant=variant.name,
        peak_row_current_a=peak_row_current_a,
        led_rail_power_w=led_rail_power_w,
        pmos_drop_v=pmos_drop_v,
        aggregate_pmos_loss_w=aggregate_pmos_loss_w,
        shift_time_per_frame_us=shift_time_per_frame_us,
        blank_time_per_frame_us=blank_time_per_frame_us,
        lsb_hold_time_us=lsb_hold_time_us,
        msb_hold_time_us=msb_hold_time_us,
        battery_current_min_v_a=battery_current_min_v_a,
        converter_loss_w=converter_loss_w,
        converter_open_board_rise_c=converter_open_board_rise_c,
        brightness_limit_at_1w=min(
            1.0, WEARABLE_CONTINUOUS_LIMITS_W[0] / led_rail_power_w
        ),
        brightness_limit_at_1_2w=min(
            1.0, WEARABLE_CONTINUOUS_LIMITS_W[1] / led_rail_power_w
        ),
    )


def validate_result(result: ModelResult) -> None:
    if result.lsb_hold_time_us <= 0:
        raise ValueError(f"{result.variant}: scan timing budget is negative")

    if result.msb_hold_time_us <= ROW_DEAD_TIME_US:
        raise ValueError(f"{result.variant}: MSB hold time is below row dead time")

    if result.brightness_limit_at_1w <= 0 or result.brightness_limit_at_1w > 1:
        raise ValueError(f"{result.variant}: invalid 1 W brightness limit")


def write_csv(results: tuple[ModelResult, ...], output_path: Path) -> None:
    field_names = tuple(ModelResult.__dataclass_fields__.keys())

    with output_path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=field_names,
            lineterminator="\n",
        )
        writer.writeheader()

        for result in results:
            writer.writerow(
                {
                    field_name: getattr(result, field_name)
                    for field_name in field_names
                }
            )


def write_markdown(results: tuple[ModelResult, ...], output_path: Path) -> None:
    lines = [
        "# Wearable RGB power and scan model",
        "",
        "Generated by `hardware/tools/model_power_scan.py`.",
        "",
        "## Assumptions",
        "",
        f"- LED rail: {OUTPUT_VOLTAGE_V:.3f} V.",
        f"- Peak channel current: {CHANNEL_CURRENT_A * 1000:.2f} mA.",
        "- Six color-homogeneous drivers and 96 serialized bits per row.",
        f"- Physical PWM depth: {PHYSICAL_BIT_PLANES} bits.",
        f"- SPI clock: {SPI_CLOCK_HZ / 1_000_000:.1f} MHz.",
        f"- Row transition dead time: {ROW_DEAD_TIME_US:.1f} us per bit-plane row.",
        (
            "- AO3403 preliminary worst-case resistance: "
            f"{PMOS_WORST_CASE_RESISTANCE_OHM * 1000:.0f} mOhm."
        ),
        (
            "- Battery-current and converter-temperature calculations use "
            f"{NOMINAL_CONVERTER_EFFICIENCY * 100:.0f}% efficiency at "
            f"{MINIMUM_BATTERY_VOLTAGE_V:.2f} V."
        ),
        (
            "- TPS63802 open-board temperature rise uses datasheet "
            f"RthetaJA = {TPS63802_THERMAL_RESISTANCE_C_PER_W:.0f} C/W. "
            "It is not an enclosure prediction."
        ),
        "",
        "## Results",
        "",
        (
            "| Variant | Row current | LED rail power | PMOS drop | "
            "Battery current at 3.15 V | LSB / MSB hold | 1 W brightness cap |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|",
    ]

    for result in results:
        lines.append(
            f"| {result.variant} "
            f"| {result.peak_row_current_a:.3f} A "
            f"| {result.led_rail_power_w:.2f} W "
            f"| {result.pmos_drop_v * 1000:.0f} mV "
            f"| {result.battery_current_min_v_a:.2f} A "
            f"| {result.lsb_hold_time_us:.2f} / {result.msb_hold_time_us:.1f} us "
            f"| {result.brightness_limit_at_1w * 100:.0f}% |"
        )

    lines.extend(
        [
            "",
            "## Engineering conclusions",
            "",
            (
                "- Full-white operation exceeds the 1–1.2 W wearable continuous "
                "target on both variants. Global brightness and content-aware "
                "power limiting are mandatory."
            ),
            (
                "- The high-resolution variant needs roughly "
                f"{results[1].battery_current_min_v_a:.2f} A from a 3.15 V battery "
                "at the assumed efficiency. Battery, connector, charger power path, "
                "copper, and converter transients must support this pulse current."
            ),
            (
                "- The conservative AO3403 drop is large enough to affect LED "
                "headroom. Measure row voltage and color current at hot and cold "
                "temperature before freezing LED_4V1."
            ),
            (
                "- The 20 MHz scan timing budget remains positive with 1.5 us "
                "break-before-make dead time. Confirm the dead time from gate and "
                "row waveforms on EVT."
            ),
            (
                "- Converter junction-rise values are screening estimates only. "
                "Use enclosure thermal measurements to set firmware derating."
            ),
            "",
        ]
    )

    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    output_directory = repository_root / "hardware" / "analysis"
    output_directory.mkdir(parents=True, exist_ok=True)

    for variant in VARIANTS:
        validate_variant(variant)

    results = tuple(calculate_model_result(variant) for variant in VARIANTS)

    for result in results:
        validate_result(result)

    write_csv(results, output_directory / "power_scan_results.csv")
    write_markdown(results, output_directory / "POWER_SCAN_MODEL.md")

    for result in results:
        print(
            f"{result.variant}: {result.led_rail_power_w:.2f} W LED rail, "
            f"{result.battery_current_min_v_a:.2f} A at minimum battery, "
            f"{result.lsb_hold_time_us:.2f} us LSB hold"
        )


if __name__ == "__main__":
    main()
