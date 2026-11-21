# Unresolved K/C wind-axis derivative convention

The current source audit rechecked the original ASWING user guide and the
[MIT-hosted extended manual](https://web.mit.edu/drela/Public/web/aswing/ASWING_Extended_User_Manual.pdf),
printed pages 24 and 84. Both give the same K/C menu label for option 2:
“wind axes: x windward, z up.” They provide no complete signed rotation or
example derivative matrix at nonzero sideslip.

The steady formulation's equations 146–148 instead define the wind-aligned
frame for Prandtl–Glauert influence evaluation. Its first basis vector points
with the relative flow. That definition alone does not prove the signed output
rotation, coefficient row signs or input-column convention of menu K/C.
The [AVL primer](https://web.mit.edu/drela/Public/web/avl/AVL_User_Primer.pdf)
also supplies a wind-axis transformation, but it is documentation for a different
program and uses its own angle/output conventions. It is not executable ASWING
parity evidence.

OpenSwing retains the implemented body, stability and reverse-stability outputs
with their explicit base rotations and coefficient signs. No guessed K/C=2
mapping was added. The remaining evidence needed is an authoritative signed
definition or original-ASWING comparison at nonzero alpha and beta, with force
and moment rows, speed/angle/rate columns, reference locations and normalization
held explicit. Testing only beta zero would not distinguish the complete map.
