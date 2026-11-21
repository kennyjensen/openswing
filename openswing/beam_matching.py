"""Deterministic finite augmenting paths for an optional beam reduction.

Stored CSR entries are graph edges, including any stored zero. Each search
visits each row/column at most once, and there are at most n_rows searches.
A failed search proves that its new row cannot augment the current matching.
No matrix weight, threshold, equation, or conditioning criterion is changed.
"""
import numpy as np


def row_matching(pattern, *, diagnostics=None):
    """Maximum-cardinality row-to-column matching, with -1 for unmatched rows.

    Iterative breadth-first augmenting paths use O(rows+columns) auxiliary
    storage and O(rows*(rows+columns+stored_edges)) bounded work. Adjacency
    order is retained, making the selected matching deterministic.
    """
    if getattr(pattern, 'format', None) != 'csr':
        raise ValueError('Beam matching requires CSR adjacency.')
    nr, nc = pattern.shape
    indptr, indices = pattern.indptr, pattern.indices
    if (indptr.shape != (nr+1,) or indptr[0] != 0
            or indptr[-1] != len(indices) or np.any(np.diff(indptr) < 0)
            or not np.issubdtype(indptr.dtype, np.integer)
            or not np.issubdtype(indices.dtype, np.integer)
            or np.any(indices < 0) or np.any(indices >= nc)):
        raise ValueError('Beam matching requires valid CSR adjacency indices.')
    row_match = [-1]*nr
    col_match = [-1]*nc
    row_seen, col_seen = [0]*nr, [0]*nc
    predecessor = [-1]*nc
    edge_visits = augmentations = searches = 0
    for root in range(nr):
        if row_match[root] >= 0:
            continue
        searches += 1
        stamp = root+1
        queue, cursor, free = [root], 0, -1
        row_seen[root] = stamp
        while cursor < len(queue) and free < 0:
            row = queue[cursor]
            cursor += 1
            for offset in range(int(indptr[row]), int(indptr[row+1])):
                column = int(indices[offset])
                edge_visits += 1
                if col_seen[column] == stamp:
                    continue
                col_seen[column] = stamp
                predecessor[column] = row
                owner = col_match[column]
                if owner < 0:
                    free = column
                    break
                if row_seen[owner] != stamp:
                    row_seen[owner] = stamp
                    queue.append(owner)
        if free < 0:
            continue
        augmentations += 1
        # Follow the alternating path back to the unmatched root. Existing
        # matched columns stay occupied as each preceding row takes them.
        while free >= 0:
            row = predecessor[free]
            old = row_match[row]
            row_match[row] = free
            col_match[free] = row
            free = old
    if diagnostics is not None:
        diagnostics.update(searches=searches, augmentations=augmentations,
                           edge_visits=edge_visits,
                           edge_visit_upper_bound=nr*len(indices))
    return np.asarray(row_match, dtype=np.intp)
