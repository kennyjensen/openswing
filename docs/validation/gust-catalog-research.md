# Additional legacy gust catalog research

The five inspected command generators/examples are fingerprinted in
`gust-catalog-research.json`; original files remain in excluded
`.reference/legacy-gust-research`. Their Git blob identities were checked against
the pinned public repository trees. No external implementation was copied.

FBHALE's `ShearWallGustInputString.m` emits type 2 followed by
`-10, 0, chord*Width_Chord, 0, V_ms`. Its comment calls the gust DARPA, which
does not establish a velocity formula. `DARPAGustInputString.m` emits type 7
followed by `-10, 0, width_m, wavelength_2_m, magnitude_m_s`. These establish
the commands emitted by those wrappers, but not the complete Earth velocity
fields, slope signs or coordinate conventions needed for a reliable importer.

The ISAE FFWT-4-U script uses type 5 and four interactive parameters. Its
analysis script writes `[-lambda, 0, lambda, Vz]` with `lambda=V/Freq`.
That does not resolve the distinction between a full wavelength and the
gradient length used by all other variants. The `FFWT_Fixed-1.txt` header
also labels the configuration “FFWT Removed”; the filename alone must not be
used to identify a future validation case.

The public ASWING guide delegates full catalog definitions to the customizable
VGUSTE/VGINIT/VGMODI/VGPGET routines. Version notes give partial descriptions
for types 4, 5 and 8, but not complete positional/formula maps. The cached
Krengel dissertation describes additional gust fields, including author-added
lateral/radial variants; their names do not prove stock ASWING compatibility.

The implemented numeric importer therefore still supports only the previously
verified straight, zero-slope type-5 layouts. Nonzero slopes and remaining
catalog types remain required work. Reusing these wrapper parameter orders
without an authoritative field formula would not close that requirement.
