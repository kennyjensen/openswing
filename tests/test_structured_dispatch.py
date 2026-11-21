"""Check eligibility and the nonrecursive fallback of the isolated dispatcher."""
from types import SimpleNamespace
import pytest
import openswing.network as network
import openswing.structured_static as structured


@pytest.mark.parametrize('case', ['mounted', 'vacuum', 'trim', 'seed', 'dynamic'])
def test_dispatch_and_fallback(monkeypatch, case):
    net = SimpleNamespace(condition=None if case == 'vacuum' else object(),
                          operating=SimpleNamespace(count=int(case == 'trim'), constraints=[]))
    calls = []
    def full(*args, **kwargs):
        calls.append(('full', args, kwargs))
        return 'full-result'
    def fast(*args, **kwargs):
        calls.append(('structured', args, kwargs))
        return 'structured-result'
    monkeypatch.setattr(network, '_equilibrate_full', full)
    monkeypatch.setattr(structured, 'equilibrate', fast)
    options = {'initial_state': {'format': 'test'}} if case == 'seed' else {'time': .2} if case == 'dynamic' else {}
    expected = 'structured' if case in ('mounted', 'vacuum') else 'full'
    assert network.equilibrate(net, 1e-10, 3, **options) == expected+'-result'
    assert len(calls) == 1 and calls[0][0] == expected
    assert calls[0][1] == (net, 1e-10, 3)
    for key, value in options.items():
        assert calls[0][2][key] == value


def test_direct_structured_fallback_uses_original_solver(monkeypatch):
    net = SimpleNamespace(operating=SimpleNamespace(count=1, constraints=[]))
    calls = []
    def full(*args, **kwargs):
        calls.append((args, kwargs))
        return 'original'
    monkeypatch.setattr(network, '_equilibrate_full', full)
    monkeypatch.setattr(network, 'equilibrate', lambda *args, **kwargs: pytest.fail('recursive fallback'))
    assert structured.equilibrate(net) == 'original'
    assert len(calls) == 1
