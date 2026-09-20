#!/usr/bin/env python3
"""Exercise Challenge 2's data gate, independently of solving the challenge.

These are data fixtures, not proofs that their lists are excluded-minor lists.
The production signature and axiom gates still check that separate obligation.
All Lean modules live in temporary directories; no GitHub calls are made.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from generate_check import MATROID_DATA_CHECK

PRELUDE = """import Defs_and_Lems.MatroidRepresentability
namespace Submission
def sample : FinMatroid := ⟨{0, 1}, {∅, {0}, {1}}⟩
noncomputable def hidden {α : Type} (x : α) : α :=
  Classical.choose (show ∃ y, y = x from ⟨x, rfl⟩)
"""


def fixtures() -> list[tuple[str, str, bool]]:
    return [
        ("empty", "def L : Finset FinMatroid := ∅", True),
        ("literal", "def L : Finset FinMatroid := {sample}", True),
        ("computed_vertex", "def L : Finset FinMatroid := {⟨{Nat.succ (2 + 3)}, {∅}⟩}", True),
        ("computed", """def freeData (n : Nat) : FinMatroid :=
  ⟨Finset.range n, (Finset.range n).powerset⟩
def L : Finset FinMatroid := (List.range 4).map freeData |>.toFinset""", True),
        ("classical_proof", """noncomputable def L : Finset FinMatroid :=
  ⟨([sample] : List FinMatroid), by classical simp⟩""", True),
        ("logical_contents", """noncomputable def alternate : Finset FinMatroid := hidden {sample}
@[implemented_by alternate] def L : Finset FinMatroid := {sample}""", True),
        ("chosen_list", "noncomputable def L : Finset FinMatroid := hidden {sample}", False),
        ("chosen_matroid", "noncomputable def L : Finset FinMatroid := {hidden sample}", False),
        ("chosen_ground", "noncomputable def L : Finset FinMatroid := {⟨hidden {0, 1}, {∅}⟩}", False),
        ("chosen_independence_family", "noncomputable def L : Finset FinMatroid := {⟨{0, 1}, hidden {∅}⟩}", False),
        ("chosen_independent_set", "noncomputable def L : Finset FinMatroid := {⟨{0, 1}, {hidden ∅}⟩}", False),
        ("chosen_ground_vertex", "noncomputable def L : Finset FinMatroid := {⟨{hidden 0}, {∅}⟩}", False),
        ("chosen_independent_vertex", "noncomputable def L : Finset FinMatroid := {⟨{0}, {{hidden 0}}⟩}", False),
        ("chosen_numeral_instance", """noncomputable def vertex : Nat :=
  @OfNat.ofNat Nat 0 (hidden (inferInstance : OfNat Nat 0))
noncomputable def L : Finset FinMatroid := {⟨{vertex}, {∅}⟩}""", False),
        ("opaque_list", "opaque L : Finset FinMatroid := {sample}", False),
        ("compiled_substitute", """def alternate : Finset FinMatroid := {sample}
@[implemented_by alternate] noncomputable def L : Finset FinMatroid := hidden {sample}""", False),
    ]


def run_checks(project: Path) -> None:
    subprocess.run(["lake", "build", "Defs_and_Lems.MatroidRepresentability"],
                   cwd=project, check=True)
    lean_path = subprocess.check_output(
        ["lake", "env", "printenv", "LEAN_PATH"], cwd=project, text=True).strip()
    with tempfile.TemporaryDirectory(prefix="explicit-matroids-") as tmp:
        for name, declaration, accepted in fixtures():
            root = Path(tmp) / name
            root.mkdir()
            source = root / "Data.lean"
            source.write_text(PRELUDE + declaration + "\nend Submission\n")
            env = {**os.environ, "LEAN_PATH": str(root) + os.pathsep + lean_path}
            proc = subprocess.run(
                ["lean", f"--root={root}", "-o", str(source.with_suffix(".olean")), str(source)],
                cwd=project, env=env, capture_output=True, text=True, timeout=900)
            assert proc.returncode == 0, f"{name}: invalid fixture\n{proc.stdout}{proc.stderr}"
            check = root / "Check.lean"
            check.write_text("import Lean\nimport Data\n" + MATROID_DATA_CHECK)
            proc = subprocess.run(["lean", f"--root={root}", str(check)], cwd=project,
                                  env=env, capture_output=True, text=True, timeout=900)
            output = proc.stdout + proc.stderr
            assert (proc.returncode == 0) == accepted, f"{name}: wrong outcome\n{output}"
            if not accepted:
                assert "must reduce to explicit finite matroid data" in output, output
            print(f"PASS matroid_data_{name}: {'accepted' if accepted else 'rejected'}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    run_checks(parser.parse_args().project.resolve())
