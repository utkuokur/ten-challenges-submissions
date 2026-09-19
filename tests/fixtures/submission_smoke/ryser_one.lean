import Challenges.challenge_08

namespace Submission

def r : ℕ := 1

theorem challenge_8 : statement_08.{u} r := by
  intro V _ H h
  exact (Nat.not_succ_le_self 1 h).elim

end Submission
