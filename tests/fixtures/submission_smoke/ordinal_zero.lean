import Challenges.challenge_10

namespace Submission

universe u v

def r : Ordinal.{v} := 0

theorem challenge_10 : statement_10.{u, v} r := by
  intro V _ G
  unfold PartitionerWins
  intro x β hβ
  exact (not_lt_of_ge (show 0 ≤ β from zero_le) hβ).elim

end Submission
