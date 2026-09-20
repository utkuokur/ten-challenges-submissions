"""Lean-side normalization of the usual ordinal arithmetic notation.

Only standard ordinal operations are interpreted. Mathlib's NONote supplies
the arithmetic and its correctness theorems; unsupported expressions retain
their original display and get no machine-comparable key.
"""

ORDINAL_PARAMETER_REPORT = r'''

open Lean Meta Elab Command in
elab "#export_verified_parameter" : command => do
  let (parameter, cnf) ← liftTermElabM do
    let r ← mkConstWithFreshMVarLevels `Submission.r
    let env ← getEnv
    let value ← deltaExpand r fun name =>
      (`Submission).isPrefixOf name || match env.getModuleIdxFor? name with
      | some i =>
        let moduleName := env.header.moduleNames[i]!
        (`Submission).isPrefixOf moduleName || moduleName == `%MODULE%
      | none => false
    -- Fuel and size limits only disable normalization; they do not restrict
    -- the mathematical parameter accepted by the signature checker.
    let rec bounded : Nat → ONote → Bool
      | 0, _ => false
      | _, .zero => true
      | fuel + 1, .oadd e n a =>
        (n : Nat).log2 ≤ 4096 && bounded fuel e && bounded fuel a
    let rec encode : ONote → Array Json
      | .zero => #[]
      | .oadd e n a =>
        #[Json.arr #[Json.arr (encode e), Json.str (Nat.repr (n : Nat))]] ++ encode a
    let rec nodes : ONote → Nat
      | .zero => 0
      | .oadd e _ a => 1 + nodes e + nodes a
    let rec read : Nat → Expr → MetaM (Option NONote)
      | 0, _ => pure none
      | fuel + 1, e => do
        let e := e.consumeMData
        let type ← withTransparency .reducible (whnf (← inferType e))
        let .const ``Ordinal [u] := type | return none
        let args := e.getAppArgs
        let head := e.getAppFn.constName?
        if e.isConstOf ``Ordinal.omega0 then
          return some (NONote.mk (ONote.oadd 1 1 0))
        if head == some ``OfNat.ofNat || head == some ``Nat.cast ||
            head == some ``NatCast.natCast then
          let index := if head == some ``OfNat.ofNat then 1 else args.size - 1
          let some arg := args[index]? | return none
          let some n ← getNatValue? (← withTransparency .all (whnf arg)) | return none
          if n.log2 > 4096 then return none
          let canonical ←
            if head == some ``OfNat.ofNat && n == 0 then
              mkAppOptM ``Zero.zero #[some type, some (mkConst ``Ordinal.zero [u])]
            else if head == some ``OfNat.ofNat && n == 1 then
              mkAppOptM ``One.one #[some type, some (mkConst ``Ordinal.one [u])]
            else do
              let cast ← mkAppOptM ``AddMonoidWithOne.toNatCast
                #[some type, some (mkConst ``Ordinal.addMonoidWithOne [u])]
              mkAppOptM ``Nat.cast #[some type, some cast, some (mkNatLit n)]
          -- Never interpret a custom OfNat instance just by its printed numeral.
          unless ← withTransparency .all (isDefEq e canonical) do return none
          return some (NONote.ofNat n)
        if args.size < 2 then return none
        let a := args[args.size - 2]!
        let b := args[args.size - 1]!
        let mut operation := 0
        let canonical ←
          if head == some ``HAdd.hAdd || head == some ``Add.add then do
            operation := 1
            mkAppOptM ``Add.add
              #[some type, some (mkConst ``Ordinal.add [u]), some a, some b]
          else if head == some ``HMul.hMul || head == some ``Mul.mul then do
            operation := 2
            let i ← mkAppOptM ``MonoidWithZero.toMulZeroOneClass
              #[some type, some (mkConst ``Ordinal.monoidWithZero [u])]
            let i ← mkAppOptM ``MulZeroOneClass.toMulZeroClass #[some type, some i]
            let i ← mkAppOptM ``MulZeroClass.toMul #[some type, some i]
            mkAppOptM ``Mul.mul #[some type, some i, some a, some b]
          else if head == some ``HPow.hPow || head == some ``Pow.pow then do
            if (← whnf (← inferType b)).isConstOf ``Nat then
              operation := 4
              let i ← mkAppOptM ``Monoid.toNPow
                #[some type, some (mkConst ``Ordinal.monoid [u])]
              mkAppOptM ``NPow.npow #[some type, some i, some b, some a]
            else
              operation := 3
              mkAppOptM ``Pow.pow
                #[some type, some type, some (mkConst ``Ordinal.instPow [u]), some a, some b]
          else return none
        -- This compares the actual elaborated operation, including its instance,
        -- against the standard Mathlib operation, not the pretty-printed symbol.
        unless ← withTransparency .all (isDefEq e canonical) do return none
        let some x ← read fuel a | return none
        let y ← if operation == 4 then do
            let some n ← getNatValue? (← withTransparency .all (whnf b)) | return none
            if n > 1024 then return none
            pure (NONote.ofNat n)
          else do
            let some y ← read fuel b | return none
            pure y
        -- A very large finite exponent can produce an impractically large
        -- normal form. Keep such expressions available for manual comparison.
        if operation ≥ 3 && (ONote.split y.1).2 > 1024 then return none
        let result := if operation == 1 then @Add.add NONote NONote.instAdd x y
          else if operation == 2 then @Mul.mul NONote NONote.instMul x y
          else NONote.opow x y
        if bounded 128 result.1 then return some result else return none
    let normalized ← try read 128 value catch _ => pure none
    if let some normal := normalized then
      if nodes normal.1 ≤ 4096 then
        return (ONote.toString normal.1, some (Json.arr (encode normal.1)))
    let display ← withOptions (fun opts =>
      opts.setBool `pp.fullNames true |>.setBool `pp.universes false
        |>.set `pp.maxDepth (10000 : Nat) |>.set `pp.maxSteps (100000 : Nat))
      (ppExpr value)
    return (display.pretty, none)
  let fields := [("problem_id", Json.str %PROBLEM%), ("parameter", Json.str parameter)]
  let fields := match cnf with
    | some value => fields ++ [("ordinal_cnf", value)]
    | none => fields
  IO.FS.writeFile ".lake/verified-parameter.json" <| (Json.mkObj fields).compress

set_option linter.hashCommand false in
#export_verified_parameter
'''
