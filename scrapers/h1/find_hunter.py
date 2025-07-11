from pathlib import Path
import json
import sys

from pydantic import BaseModel
from src.llm_models import openai_o3
from src.llm_provider import LMP

try:
    import tiktoken
except ImportError:  # pragma: no cover
    print("tiktoken is required. Install with `pip install tiktoken`.", file=sys.stderr)
    sys.exit(1)

o3 = openai_o3()

class HunterScore(BaseModel):
    english: int
    technical_depth: int
    reproducibility: int
    impact: int
    creativity: int
    professionalism: int
    presentation: int

class ClassifyHunter(LMP):
    prompt = """
### Candidate Evaluation Rubric (Bug-Bounty Write-up Review)

| #     | Criterion                                        | What to Look For in the Write-up                                                                        | Scoring Guide (1 = poor · 5 = excellent)                                                                                                                                                                                                                                                 |
| ----- | ------------------------------------------------ | ------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A** | **English Proficiency (Required Pass-Mark ≥ 3)** | Grammar, vocabulary, logical flow, absence of ambiguity.                                                | **1** = hard to follow; many errors.<br>**2** = meaning often clear but frequent mistakes.<br>**3** = generally clear; minor errors don’t impede understanding.<br>**4** = very clear, well-structured, almost no errors.<br>**5** = professional-quality, engaging, error-free writing. |
| **B** | **Technical Depth & Accuracy**                   | Correct vulnerability classification, root-cause analysis, accurate explanation of affected code/logic. | **1** = superficial; mislabels vuln.<br>**2** = partial analysis; some incorrect statements.<br>**3** = solid and mostly accurate; minor gaps.<br>**4** = deep, precise, well-supported by evidence.<br>**5** = expert-level reverse-engineering or code tracing with clear proofs.      |
| **C** | **Reproducibility & Methodology**                | Clear, step-by-step reproduction, prerequisites, scripts or commands provided.                          | **1** = cannot recreate from write-up.<br>**2** = significant steps missing.<br>**3** = all main steps present; may need minor inference.<br>**4** = fully reproducible; helper scripts or PoCs included.<br>**5** = turn-key demo, automation, and cleanup instructions.                |
| **D** | **Impact Assessment & Risk Communication**       | Real-world consequences quantified, affected user scope, business risk articulated.                     | **1** = impact hand-waved.<br>**2** = generic statements only.<br>**3** = specific but limited impact discussion.<br>**4** = quantifies data exposure, privilege level, or financial loss.<br>**5** = ties technical issue to strategic/brand risks and mitigation cost.                 |
| **E** | **Creativity & Problem-Solving**                 | Novel chaining of bugs, unconventional attack surface, bypass techniques.                               | **1** = common vulnerability, standard approach.<br>**2** = minor twist on known method.<br>**3** = clever use of standard technique.<br>**4** = original angle or multi-step chain.<br>**5** = ground-breaking vector or first-of-its-kind exploit.                                     |
| **F** | **Responsible Disclosure & Professionalism**     | Timelines, vendor coordination, tone, respect for policy scope.                                         | **1** = publicly drops exploit or shames vendor.<br>**2** = mentions responsible disclosure but with issues.<br>**3** = meets program rules; neutral tone.<br>**4** = timely reports, helpful patch guidance.<br>**5** = exemplary coordination, public education, no-drama tone.        |
| **G** | **Presentation Quality**                         | Use of diagrams, annotated screenshots, section headers, code formatting.                               | **1** = wall of text.<br>**2** = some formatting; cluttered.<br>**3** = readable; basic visuals.<br>**4** = well-formatted with helpful visuals.<br>**5** = polished report; visuals significantly enhance comprehension.                                                                |
| **H** | **Tooling & Automation Insight**                 | Evidence of custom scripts, fuzzers, or systematic recon methods.                                       | **1** = manual only, no tools shown.<br>**2** = mentions common tools without detail.<br>**3** = shows command snippets or simple scripts.<br>**4** = shares reusable tooling or pipelines.<br>**5** = advanced custom automation or open-sourced framework.                             |

---

#### How to Use the Rubric

1. **Score each criterion 1–5.**
2. **Fail-fast on English:** any score **< 3 in Criterion A** disqualifies the candidate.
3. **Compute Total Score:** sum of all criteria (max = 40).
4. **Optional Weighting:** if English and Technical Depth should dominate, double their scores when totaling.
5. **Interpretation Bands (example):**

   * 34 – 40 = Outstanding partner
   * 28 – 33 = Strong candidate
   * 22 – 27 = Promising but needs mentorship
   * ≤ 21 = Not a fit for this project

Tailor the cut-offs or add/remove criteria to match your project’s emphasis (e.g., add “Mobile Exploit Focus” or “Public Speaking Ability” if relevant).

Here is a report from a perfect candidate:

<golden_report>
I told Pete I would take a look at Spotify, hi Pete.
Summary
It's possible to take over any store account through partners given an employee email address. This is possible because I found a way to confirm arbitrary emails. I don't know the Shopify ecosystem well enough to know the other ramifications of such a bug.
On #270981 you wrote:
The intention was that, when a partner already had a valid user account on the store, their collaborator account request could be accepted automatically, with the user account converted into a collaborator account.
I tested that functionality and confirmed how it works. I realized that if you can somehow create a partner account with a business email that matched that of an employee, you would be able to take over their employee account, then convert it to a collaborator. The problem is that business accounts need emails to be validated, but this can be bypassed with a race condition.
The bug works by hitting the email validation endpoint for an email you own, at the same time as changing your email to a victim's. It might take a few tries, but eventually your email will be changed and be validated due to not (properly) using a DB transaction.
Steps to reproduce
Create a store account and invite an employee.
Accept the employee invite (maybe not necessary I didn't test).
Login to or create a partner account as the attacker.
Go to your partner settings page https://partners.shopify.com/[ID]/settings and change your email to something you own.
Check your email and grab the confirmation link, but don't visit it yet.
Go back to your partner account and change your email to that of the store employee from step 2, but intercept the request to not let it through yet.
Now the tricky part. The "change email" takes anywhere from 1,100 - 2,500 ms to load so you need to take that into account. But let the request go through, wait for some milliseconds, then in another tab visit that email confirmation link from step 5.
If done correctly you will now have confirmed an email you do not own.
Visit https://partners.shopify.com/[ID]/managed_stores, add the store, and you now have access.
As proof, look at the email for partner account 698396. It will be confirmed cache@hackerone.com, which I obviously would never be able to validate otherwise.
Thanks,
-- Tanner
Impact
Ability to take over stores, and possibly perform any other action that relies on a validated email as a security measure.
</golden_report>

This guy would get perfect scores. Everyone else less than this

Here is the report for the current candidate:
{candidate_reports}

Can you score this report according to the rubric
"""
    response_format = HunterScore


def classify_hunter(mapping_path: Path, encoding_name: str = "cl100k_base") -> int:
    """Count total tokens across all report files referenced in a mapping JSON.

    Args:
        mapping_path: Path to JSON file containing a dict {author: [file_paths]}.
        encoding_name: Name of tiktoken encoding to use.

    Returns:
        Total number of tokens across all unique files.
    """
    if not mapping_path.exists():
        raise FileNotFoundError(f"Mapping file not found: {mapping_path}")

    # Load mapping
    with open(mapping_path, "r", encoding="utf-8") as f:
        author_map = json.load(f)

    # Initialise encoder
    encoding = tiktoken.get_encoding(encoding_name)

    total_tokens = 0

    # Iterate by author instead
    for author, report_paths in list(author_map.items())[:10]:
        print(f"Processing reports for author: {author}")
        
        report_str = ""
        for i, path_str in enumerate(report_paths, start=1):
            path = Path(path_str)
            if not path.exists():
                print(f"Warning: File not found {path}", file=sys.stderr)
                continue
            try:
                report = json.loads(path.read_text())
                content = report["content"]

                report_str += f"========== Report {i} ==========\n{content}\n\n"
            except OSError:
                print(f"Error reading {path}", file=sys.stderr)
                continue

        res = ClassifyHunter().invoke(model=o3, prompt_args={"candidate_reports": report_str})
        print(res)
        print(report_str)

if __name__ == "__main__":
    classify_hunter(Path("scrapers/h1/hunter_map.json"))
