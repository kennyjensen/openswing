# Chunked time-history archive, version 1

This is the storage implementation for retaining complete computed time states
without one large JSON string or an in-memory array of every physical state.
The workbench can open and save `.oswh` histories, plot scalar and distribution
histories, select complete physical states, play them, and continue from their
checkpoints. Existing JSON projects and the private worker wire format retain
their formats and limits. Large histories are portable archives; attaching them
durably to browser projects is still unfinished.

`web/time-history-archive.js` exports an asynchronous writer and random-access
reader. The writer accepts an asynchronous sink with `write(Uint8Array)`,
`close()` and `abort()` methods. A browser `FileSystemWritableFileStream` is one
such sink. The reader accepts a `File`/`Blob`, or an equivalent object exposing
`size` and `slice(start, end).arrayBuffer()`.

```js
const writer = await createTimeHistoryWriter(await handle.createWritable());
await writer.append(firstBatch); // Await every write; never omit physical fields.
await writer.append(nextBatch);  // The caller resolves repeated continuation joins.
await writer.finish(metadata);  // Complete result metadata, without snapshots.

const archive = await openTimeHistoryArchive(await handle.getFile());
const snapshot = await archive.readSnapshot(selectedIndex);
const context = snapshot.restart_context ?? archive.metadata().restart_context;
const checkpoint = checkpointRecord(snapshot.restart, context);
```

All root metadata supplied to `finish` is retained, including unknown fields.
It is the caller's responsibility to provide metadata describing the joined
result, preserve prior contexts and numerical provenance on retained ranges,
and commit the enclosing project only after the file is complete. The storage
layer does not infer internal solver states from adjacent public snapshots.

Each `append` writes its entire batch before resolving. The default chunk size
is 16 snapshots; configurable sizes are 1–128. Large chunks split recursively
until each record fits. An individual state that cannot fit fails explicitly.
Input objects are not mutated and can be released when `append` resolves.
Times must be finite and nondecreasing. Distinct states at the same time remain
distinct, in their supplied order.

The file layout is:

| Region | Encoding |
|---|---|
| Header | Eight ASCII bytes: `OSWHST01` |
| Snapshot records | Independent gzip members, each containing one compact JSON packet |
| Metadata record | One gzip member containing root metadata without snapshots |
| Index | UTF-8 JSON manifest |
| Footer | 56 bytes, described below |

The footer contains `OSWEND01` (8 bytes), the index offset (unsigned 64-bit little
endian), the index byte length (unsigned 64-bit little endian), then the 32-byte
SHA-256 digest of the exact index bytes. Offsets must also be safe JavaScript
integers. The index immediately precedes the footer, with no trailing bytes.
Files lacking a complete footer are rejected.

The index has `format: "openswing-time-history"`, `version: 1`, a total
`snapshots` count and a `records` array. Each record contains its `kind`, byte
`offset`, compressed `bytes`, uncompressed `plain_bytes`, and lowercase hex
`sha256` digest of its uncompressed bytes. Snapshot records additionally contain
`first` (zero-based snapshot index), `count`, and the exact `times` array.
Offsets must be contiguous; counts must cover the complete history; the last
record must be `metadata`. Unknown versions are rejected.

Snapshot records may also contain `preview_version: 1` and a `preview` array.
These are small display entries containing the exact time, step, event phase,
checkpoint/accuracy availability, internal-step count and ten scalar quantities
listed in `web/time-history-index.js`. They are not physical states or restart
data. A known-version entry must pass schema checks and must equal the entry
derived from its physical state when that chunk is read. Unknown preview
versions are ignored. Files without a complete usable preview are scanned once
to build the display index. The writer drops the entire optional cache if it
would exceed 4 MiB; it never drops physical states to make the cache fit.

Each snapshot record uses the existing `openswing-time-result` version-1
external-reference convention: `result`, `values`, and `references`. The result
contains `analysis: "time_response"` and the chunk's snapshots. Selected complete
checkpoint and descriptive fields can share an exactly equal pool entry. No
entry references another chunk. Equality includes object key order and signed
zero. A bounded key cache affects compression only; eviction never removes data.
Literal user dictionaries that resemble reference records are ordinary data.
No field is reconstructed, rounded, decimated or removed.

The JSON encoder preserves `-0`; standard `JSON.stringify` would normalize it
to `0`. It accepts finite JSON values, ordinary objects and dense arrays, and
rejects cycles, accessors, hidden properties, symbols and coercion hooks.
Property order survives. The reader rejects invalid UTF-8, nonfinite parsed
numbers, invalid reference paths and prototype writes before exposing a state.
Standalone checkpoint extraction retains its existing independent-copy rules.

Bounds are checked on both writing and reading:

| Quantity | Bound |
|---|---:|
| Uncompressed record | 16 MiB |
| Compressed record | 16 MiB + 64 KiB |
| Index | 16 MiB |
| Snapshot count | 2,000,000 |
| Record count | 65,536 |
| JSON depth | 80 |
| Values per encoded or expanded chunk tree | 2,000,000 |
| Expanded chunk strings and keys | 64 Mi UTF-16 code units |
| Pool lookup keys per chunk | 4 Mi UTF-16 code units |

Decompression stops if it exceeds the declared size; it does not first allocate
the claimed output. Checksums cover the index on opening and every record on
access. Opening checks root metadata but does not read all physical chunks.
`verify()` visits every physical record. These digests detect corruption; they
do not establish the scientific validity or origin of a computed result.

The reader caches one decoded chunk and serializes concurrent reads. Selected
snapshots and metadata are independent copies, so callers cannot corrupt the
cache. `times()` returns a small index, and `snapshots()` asynchronously yields
the full states in order. Callers must consume and release these states instead
of collecting the iterator into an unbounded array. `statistics` exposes bytes
read, largest read, records read and cache hits for storage validation.

Browser mechanisms follow the [WHATWG Compression Standard](https://compression.spec.whatwg.org/)
and [File System Standard](https://fs.spec.whatwg.org/). Unsupported compression
or checksum APIs produce explicit errors.

## Workbench use

`archiveTrajectory(reader)` attaches a reader to its root metadata. The
`timeHistory(result)` interface handles both ordinary arrays and archive-backed
histories. It keeps the selected full state pinned, independent of scans, and
retains only a small index and up to four additional scalar series. Rapid scrub
requests coalesce into the in-flight read and the latest requested selection;
an older read cannot replace a newer selection. Playback displays computed
states without interpolating physical fields. Other scalar quantities and
distribution overlays/envelopes read every state in order with progress updates.
Distribution caches retain plotted samples, not complete physical snapshots.

**Save complete history** writes batches of 16 states. Where a native save picker
is available, it streams directly to the chosen file. Otherwise it writes an
origin-private temporary file and downloads that `File`. Only files older than
24 hours in the disposable `openswing-temporary-exports` namespace are cleaned
up; recent downloads and project files are not removed. Failed writes are
aborted. Unsupported storage or quota failures are reported to the user.

Workbench archives include `openswing_workbench` with format
`openswing-workbench-history`, version 1, and the saved case configuration.
Opening verifies the configuration, matching source/numerical settings,
numerical fingerprint and first physical state before replacing the workspace.
Further physical chunks are checked on access. This does not establish
scientific validity or independent reference agreement. Raw codec fixtures
without workbench settings cannot be opened as complete workbench solutions.

Continuation retains the selected prefix through an immutable source reference
and adds the new segment. It preserves earlier contexts, same-time transitions
and numerical provenance. It does not materialize the archived prefix. The new
segment remains in memory until exported; automatic incremental durable storage
of successive solver segments is still unfinished.

Small archive-backed histories can be saved as ordinary computed solutions in
JSON projects. Materialization stops at the existing 64 MiB / 2,000,000-value
bounds and directs larger histories to **Save complete history**. Runtime
**Undo load** can retain an archive-backed source without cloning its full
history. Persistent archive attachments, transactional project references,
reload recovery, durable undo retention and orphan cleanup for those project
attachments remain unfinished. Exported archives must be kept as separate
files until that project storage work is complete.
