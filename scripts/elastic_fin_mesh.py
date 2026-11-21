"""Pure mesh arithmetic copied from pinned adapter; no native imports."""
def explicit_mesh(fixture, subdivisions):
    """Bisect original material intervals; retain the shared fin root once."""
    if type(subdivisions) is not int or subdivisions not in (1, 2, 4):
        raise ValueError('This draft supports only the declared 1/2/4 subdivisions.')
    branches = fixture['branches']
    original = {
        3: sorted(set(branches['lower']['stations'] + branches['upper']['stations'])),
        4: branches['boom']['stations'],
    }
    beams = {}
    for beam, stations in original.items():
        nodes = [a + (b-a)*j/subdivisions
                 for a, b in zip(stations[:-1], stations[1:])
                 for j in range(subdivisions)] + [stations[-1]]
        beams[str(beam)] = {'nodes': nodes}
    return {'default': 16, 'beams': beams}
