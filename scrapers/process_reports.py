from pathlib import Path

from .utils import convert_weakness, Weaknesses, process_reports_in_batches
from .lmp import DetectSimpleAuthNZ, DetectSimpleInjection

if __name__ == "__main__":
    pairs = [
        (
            DetectSimpleAuthNZ,
            lambda rpt: convert_weakness(rpt.get("weaknesses", [""])[0])
                        in {Weaknesses.AUTHZ_AUTHN}
        ),
        (
            DetectSimpleInjection,
            lambda rpt: convert_weakness(rpt.get("weaknesses", ["random"])[0])
                        in {Weaknesses.XSS, Weaknesses.OTHER_INJECTION}
        ),
    ]

    process_reports_in_batches(
        reports_dir=Path("scrapers/high_reports_cleaned"),
        lmp_filter_pairs=pairs,
        model_name="deepseek-reasoner",  # use one model for the whole run
        dry_run=False,                   # set to True if you only want a count
        batch_size=50,
        max_workers=20,
    )