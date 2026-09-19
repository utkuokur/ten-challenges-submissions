import Challenges.challenge_01

open SimpleGraph

namespace Submission

def r : ℕ := 0

def singletonMinor {V : Type*} (G : SimpleGraph V) (v : V) :
    Minor (completeGraph (Fin 1)) G where
  branchSet := fun _ => {v}
  pairwise_disjoint_branchSet := by
    intro i j hij
    exact (hij (Subsingleton.elim i j)).elim
  connectedOn_branchSet := by
    intro _
    letI : Nonempty ({v} : Set V) := ⟨⟨v, Set.mem_singleton v⟩⟩
    refine ⟨?_⟩
    intro x y
    have hxy : x = y := Subtype.ext (x.property.trans y.property.symm)
    subst y
    exact ⟨Walk.nil⟩
  exists_mem_branchSet_of_adj := by
    intro i j hij
    exact (hij (Subsingleton.elim i j)).elim

theorem challenge_1 : statement_01 r := by
  intro V _ G h
  rw [show r = 0 by rfl, G.colorable_zero_iff]
  constructor
  intro v
  letI : Nonempty V := ⟨v⟩
  have h1 : 1 ≤ hadwigerNumber G := by
    classical
    exact Nat.le_findGreatest Fintype.card_pos ⟨singletonMinor G v⟩
  simp [r] at h
  omega

end Submission
