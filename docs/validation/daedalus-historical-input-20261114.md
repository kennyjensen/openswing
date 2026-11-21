# Archived public Daedalus input and early technical descriptions

The public `dae.asw` captured on **10 October 2008** is byte-for-byte identical
to today's MIT download and to OpenSwing's literal input. All three are
9,555 bytes with SHA-256
`bb020c3bbcf049bef9f381c0242d9c4a5feaa0e60edbd2d363852885f7929386`.
The retrieved archived bytes also reproduce the archive's CDX SHA-1 digest.

This is stronger evidence against a later change to the **public aircraft
file** as the explanation for the Bode mismatch. It does not prove that the
June 2008 drawing used this exact file, exclude private edits, or recover its
operating point, discretization, controls or options. The current MIT response
reports a Last-Modified date of 2 June 2008; that header alone is not a
historical execution record.

## Retrieved sources

All downloads and derived text live in the visible
[reference directory](../../reference/daedalus-historical-input-20261114/).
The [source supplement](daedalus-historical-input-sources-20261114.json)
records checksums, sizes and download receipts without changing the existing
authoritative source catalog.

| Source | Archive capture | Printed version/date | Local copy |
| --- | --- | --- | --- |
| Public dae.asw | 2008-10-10 14:30:33 UTC | Input file, no run settings | [ASW](../../reference/daedalus-historical-input-20261114/dae-20081010.asw) |
| Steady Technical Description | 2007-03-16 20:17:01 UTC | ASWING 5.60, July 2005 | [PDF](../../reference/daedalus-historical-input-20261114/asw_theory-20070316.pdf), [text](../../reference/daedalus-historical-input-20261114/asw_theory-20070316.txt) |
| Unsteady Extension | 2007-03-16 20:35:26 UTC | ASWING 5.64, September 2006 | [PDF](../../reference/daedalus-historical-input-20261114/asw_uns_theory-20070316.pdf), [text](../../reference/daedalus-historical-input-20261114/asw_uns_theory-20070316.txt) |

The raw [model archive replay](https://web.archive.org/web/20081010143033id_/http://web.mit.edu/drela/Public/web/aswing/dae.asw)
and recorded CDX response are retained. The availability API timed out inside
its JSON response; the successful CDX query and checksum-verified replay
provided the evidence instead. Queries for the theory PDFs before January 2010
returned the listed 2007 captures. These are not exact ASWING 5.79 technical
descriptions and must not be labeled as such.

## Focused equation comparison

The archived unsteady PDF pages 5, 6, 8 and 9 were rendered and visually
inspected, alongside the searchable text. The following terms agree in form
with the current 5.99 description; their equation numbers changed:

| Term | Archived unsteady document | Current unsteady document |
| --- | --- | --- |
| Quarter-chord relative velocity and ordinary/rate lift, both lift contributions acting at quarter-chord | p. 5, Eqs. 30–37 | p. 8, Eqs. 29–36 |
| Distributed mass acceleration and gyroscopic moment | p. 6, Eqs. 38–41 | p. 9, Eqs. 37–40 |
| Mid-chord apparent force and moment, including rotation and angular acceleration | p. 6, Eqs. 42–46 | p. 9, Eqs. 41–45 |
| Local circulation-rate downwash with b=2/π | p. 8, Eqs. 55–56 | p. 10, Eqs. 48–49 |
| Implied lag function (1+2ik)/(1+4ik) | p. 9, Eq. 63 | p. 11, Eq. 56 |

This is a focused source comparison, not an audit of every historical equation
or a fresh implementation test. It supplies no new correction to these loads.

The old §7.1, pp. 7–8, also presents a convected vortex-ring wake. The next
§7.2 explicitly offers the local approximation. The current
[ASWING FAQ](../../reference/aswing_faq.txt), question about `M_wdot`, explains
that the implemented shed-vorticity effect acts locally on the shedding
surface and does not delay wing downwash seen by the tail. The
[user manual](../../reference/aswing_doc.txt), **Lag aero effects modeled — L**,
likewise describes the circulation-rate term and its enabled startup default.
The [version notes](../../reference/version_notes.txt) already record its
disable toggle under ASWING 5.61, 1 November 2005.

Thus a theoretical full-wake passage does not establish that the reference
Bode used that method. Substituting it into the production solver to obtain
a deeper dip would not be justified by the retrieved sources. The later
5.99 formulation remains the implementation target; its historical differences
must stay explicit when comparing older results.

The [current four-output comparison](daedalus-current-bode-20261114.md) remains
unmatched. No operating-point file or ASWING executable was recovered. No
aircraft property, physics equation, ISAE fraction or progress event changed.
No solver ran during this source review.
